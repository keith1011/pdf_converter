"""
將 DSE 數學 Q&A 整理成 fine-tune 用的 JSONL。

用法：
  1. 複製 data/train_example.jsonl → data/train.jsonl，手動追加題目
  2. python prepare_dataset.py --validate
  3. python prepare_dataset.py --split   # 切出 10% 當 eval

草稿流水線（不會自動污染 train.jsonl）：
  python prepare_dataset.py --validate-draft
  python prepare_dataset.py --promote-draft   # 只合併 status=approved
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SYSTEM_PROMPT = (
    "你是一位專業的香港 DSE 數學中學老師。"
    "用 Step 1、Step 2 逐步解釋，公式用 LaTeX（行內 $...$，區塊 $$...$$），繁體中文回覆。"
)

TRAIN_FILE = Path("data/train.jsonl")
EVAL_FILE = Path("data/eval.jsonl")
EXAMPLE_FILE = Path("data/train_example.jsonl")
DRAFT_FILE = Path("data/draft.jsonl")
REJECTED_FILE = Path("data/rejected.jsonl")

PLACEHOLDER_MARKERS = ("[待補解答]",)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 {path}，請先建立或複製 {EXAMPLE_FILE}")
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} 第 {i} 行 JSON 格式錯誤: {e}") from e
    return rows


def save_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def assistant_content(row: dict) -> str:
    for msg in row.get("messages") or []:
        if msg.get("role") == "assistant":
            return (msg.get("content") or "").strip()
    return ""


def is_placeholder_assistant(row: dict) -> bool:
    content = assistant_content(row)
    if not content:
        return True
    return any(marker in content for marker in PLACEHOLDER_MARKERS)


def validate_row(row: dict, index: int, *, require_real_answer: bool = False) -> list[str]:
    errors: list[str] = []
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        errors.append(f"#{index}: 需要 messages 陣列，且至少含 user + assistant")
        return errors

    roles = [m.get("role") for m in messages]
    if "user" not in roles or "assistant" not in roles:
        errors.append(f"#{index}: 缺少 user 或 assistant 角色")

    for j, msg in enumerate(messages):
        if not msg.get("content", "").strip():
            errors.append(f"#{index} message[{j}]: content 不可為空")

    if require_real_answer and is_placeholder_assistant(row):
        errors.append(f"#{index}: assistant 仍是待補解答，不可寫入 train.jsonl")

    return errors


def validate_dataset(path: Path = TRAIN_FILE) -> None:
    rows = load_jsonl(path)
    all_errors: list[str] = []
    for i, row in enumerate(rows, 1):
        all_errors.extend(validate_row(row, i, require_real_answer=True))

    print(f"檔案: {path}")
    print(f"筆數: {len(rows)}")
    if all_errors:
        print("\n驗證失敗:")
        for err in all_errors:
            print(f"  - {err}")
        raise SystemExit(1)
    print("格式驗證通過")


def validate_draft(path: Path = DRAFT_FILE) -> None:
    if not path.exists():
        raise FileNotFoundError(f"找不到 {path}。請先執行 extract_questions.py")

    rows = load_jsonl(path)
    all_errors: list[str] = []
    pending = 0
    approved = 0
    failed = 0
    placeholders = 0

    for i, row in enumerate(rows, 1):
        all_errors.extend(validate_row(row, i, require_real_answer=False))
        status = (row.get("status") or "draft").strip()
        if status == "approved":
            approved += 1
        elif status == "extract_failed":
            failed += 1
        else:
            pending += 1
        if is_placeholder_assistant(row):
            placeholders += 1

    print(f"檔案: {path}")
    print(f"筆數: {len(rows)}")
    print(f"  status=approved: {approved}")
    print(f"  status=draft/其他: {pending}")
    print(f"  status=extract_failed: {failed}")
    print(f"  待補解答: {placeholders}")

    if all_errors:
        print("\n驗證失敗:")
        for err in all_errors:
            print(f"  - {err}")
        raise SystemExit(1)

    print("草稿格式驗證通過")
    if approved == 0:
        print("提示: 審完後把該列 status 改成 approved，再執行 --promote-draft")


def to_train_row(row: dict) -> dict:
    """Strip draft metadata; keep only LoRA-ready messages."""
    messages = row.get("messages")
    if not isinstance(messages, list):
        raise ValueError("row missing messages")
    lang = (row.get("language") or row.get("source", {}).get("lang") or "zh").strip().lower()
    # DSE default: force Traditional Chinese system prompt.
    # English drafts keep their own system wording if still language=en.
    cleaned = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system" and lang != "en":
            cleaned.append({"role": "system", "content": SYSTEM_PROMPT})
        else:
            cleaned.append({"role": role, "content": content})
    return {"messages": cleaned}


def promote_draft(
    draft_path: Path = DRAFT_FILE,
    train_path: Path = TRAIN_FILE,
    rejected_path: Path = REJECTED_FILE,
) -> None:
    if not draft_path.exists():
        raise FileNotFoundError(f"找不到 {draft_path}")

    draft_rows = load_jsonl(draft_path)
    train_rows = load_jsonl(train_path) if train_path.exists() else []

    to_promote: list[dict] = []
    remain: list[dict] = []
    rejected: list[dict] = []
    skipped_placeholder = 0

    for row in draft_rows:
        status = (row.get("status") or "draft").strip()
        if status == "rejected":
            rejected.append(row)
            continue
        if status != "approved":
            remain.append(row)
            continue
        if is_placeholder_assistant(row):
            skipped_placeholder += 1
            remain.append(row)
            continue
        errors = validate_row(row, 0, require_real_answer=True)
        if errors:
            print(f"跳過不合格列 {row.get('id', '?')}: {errors}")
            remain.append(row)
            continue
        lang = (row.get("language") or row.get("source", {}).get("lang") or "").strip().lower()
        if lang == "en":
            print(
                f"警告: {row.get('id', '?')} 仍是英文草稿（language=en）。"
                "DSE 訓練建議先改寫成繁體中文再 promote；本次仍會合併（因 status=approved）。"
            )
        to_promote.append(to_train_row(row))

    if not to_promote and not rejected:
        print("沒有可合併的列。請將審過的列 status 改為 approved（且補上真實解答）。")
        return

    if to_promote:
        train_rows.extend(to_promote)
        save_jsonl(train_rows, train_path)
        print(f"已合併 {len(to_promote)} 筆 → {train_path}（現共 {len(train_rows)} 筆）")

    if rejected:
        append_jsonl(rejected, rejected_path)
        print(f"已移出 rejected {len(rejected)} 筆 → {rejected_path}")

    save_jsonl(remain, draft_path)
    print(f"草稿剩餘 {len(remain)} 筆 → {draft_path}")
    if skipped_placeholder:
        print(f"警告: {skipped_placeholder} 筆 status=approved 但仍是待補解答，已留在 draft")


def split_eval(ratio: float = 0.1, seed: int = 42) -> None:
    rows = load_jsonl(TRAIN_FILE)
    if len(rows) < 10:
        print(f"警告：目前只有 {len(rows)} 筆，建議至少 50 筆再正式訓練。")

    rng = random.Random(seed)
    shuffled = rows.copy()
    rng.shuffle(shuffled)

    eval_count = max(1, int(len(shuffled) * ratio))
    eval_rows = shuffled[:eval_count]
    train_rows = shuffled[eval_count:]

    save_jsonl(train_rows, TRAIN_FILE)
    save_jsonl(eval_rows, EVAL_FILE)
    print(f"已切分：train {len(train_rows)} 筆 → {TRAIN_FILE}")
    print(f"         eval  {len(eval_rows)} 筆 → {EVAL_FILE}")


def bootstrap_from_example() -> None:
    if TRAIN_FILE.exists():
        print(f"{TRAIN_FILE} 已存在，跳過複製。")
        return
    if not EXAMPLE_FILE.exists():
        raise FileNotFoundError(f"找不到範例檔 {EXAMPLE_FILE}")
    rows = load_jsonl(EXAMPLE_FILE)
    save_jsonl(rows, TRAIN_FILE)
    print(f"已從範例建立 {TRAIN_FILE}（{len(rows)} 筆），請繼續手動追加。")


def main() -> None:
    parser = argparse.ArgumentParser(description="DSE 數學訓練資料工具")
    parser.add_argument("--validate", action="store_true", help="檢查 train.jsonl 格式")
    parser.add_argument("--validate-draft", action="store_true", help="檢查 draft.jsonl 格式")
    parser.add_argument(
        "--promote-draft",
        action="store_true",
        help="將 draft 中 status=approved 且有真實解答的列合併進 train.jsonl",
    )
    parser.add_argument("--split", action="store_true", help="切 10% 到 eval.jsonl")
    parser.add_argument("--bootstrap", action="store_true", help="從範例建立 train.jsonl")
    args = parser.parse_args()

    if args.bootstrap:
        bootstrap_from_example()
    if args.validate:
        validate_dataset()
    if args.validate_draft:
        validate_draft()
    if args.promote_draft:
        promote_draft()
    if args.split:
        split_eval()

    if not any(
        [
            args.validate,
            args.validate_draft,
            args.promote_draft,
            args.split,
            args.bootstrap,
        ]
    ):
        parser.print_help()


if __name__ == "__main__":
    main()
