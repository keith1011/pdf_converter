"""
從 draft/train JSONL 只抽出題目，寫成可編輯文字稿。

用法：
  ..\\AIbuliding\\venv-train\\Scripts\\python.exe jsonl_to_latex.py
  ..\\AIbuliding\\venv-train\\Scripts\\python.exe jsonl_to_latex.py --in data/draft.jsonl --out data/sources/2015p1_questions.tex
  ..\\AIbuliding\\venv-train\\Scripts\\python.exe jsonl_to_latex.py --all
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

JUNK_PATTERNS = (
    "寫於邊界以外",
    "請在此貼上電腦條碼",
    "考生須知",
    "Time is up",
)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def user_content(row: dict) -> str:
    for msg in row.get("messages") or []:
        if msg.get("role") == "user":
            return (msg.get("content") or "").strip()
    return ""


def normalize_math(text: str) -> str:
    """\\(...\\) / \\[...\\] → $...$ / $$...$$"""
    text = re.sub(r"\\\((.+?)\\\)", r"$\1$", text, flags=re.DOTALL)
    text = re.sub(r"\\\[(.+?)\\\]", r"$$\1$$", text, flags=re.DOTALL)
    return text


def is_junk(question: str) -> bool:
    q = question.strip()
    if len(q) < 8:
        return True
    return any(p in q for p in JUNK_PATTERNS)


def row_to_block(row: dict) -> str:
    qid = row.get("id") or "unknown"
    source = row.get("source") or {}
    page = source.get("page", "?")
    qno = source.get("question_id", "")
    image = source.get("image", "")
    has_figure = bool(row.get("has_figure"))
    fig = (row.get("figure_description") or "").strip()

    question = normalize_math(user_content(row))
    if has_figure and fig and "[圖]" not in question and "[Figure]" not in question:
        question = f"{question}\n\n[圖] {normalize_math(fig)}"

    meta = f"% id={qid}  page={page}  exam_q={qno}  has_figure={has_figure}"
    if image:
        meta += f"  image={image}"

    return f"{meta}\n題目：\n{question}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="JSONL -> 只抽題目（題目：）")
    parser.add_argument("--in", dest="inp", type=Path, default=Path("data/draft.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/sources/draft_questions.tex"))
    parser.add_argument("--all", action="store_true", help="保留條碼／邊界說明等 junk 列")
    args = parser.parse_args()

    rows = load_jsonl(args.inp)
    blocks: list[str] = []
    skipped = 0
    for row in rows:
        q = user_content(row)
        if not args.all and is_junk(q):
            skipped += 1
            continue
        if not q:
            skipped += 1
            continue
        blocks.append(row_to_block(row))

    doc = (
        "% 由 jsonl_to_latex.py 匯出（只含題目）\n"
        "% 請自行補：Step 1： / Step 2： / **答案：** / **常見錯誤：**\n"
        f"% 題數: {len(blocks)}  （略過: {skipped}）\n\n"
        + "\n".join(blocks)
        + "\n% ===== END =====\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(doc, encoding="utf-8")
    print(f"Wrote {len(blocks)} question(s) -> {args.out} (skipped: {skipped})")


if __name__ == "__main__":
    main()
