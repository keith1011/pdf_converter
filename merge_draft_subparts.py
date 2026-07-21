"""
Merge split (a)/(b)/(i) draft rows that belong to the same main question.

Usage:
  ..\\AIbuliding\\venv-train\\Scripts\\python.exe merge_draft_subparts.py
  ..\\AIbuliding\\venv-train\\Scripts\\python.exe merge_draft_subparts.py --in data/draft.jsonl --out data/draft.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_jsonl(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def user_content(row: dict) -> str:
    for msg in row.get("messages") or []:
        if msg.get("role") == "user":
            return (msg.get("content") or "").strip()
    return ""


def set_user_content(row: dict, text: str) -> None:
    for msg in row.get("messages") or []:
        if msg.get("role") == "user":
            msg["content"] = text
            return
    row.setdefault("messages", []).append({"role": "user", "content": text})


def parse_qid(qid: str) -> tuple[str | None, str | None]:
    """Return (main_number, subpart) e.g. ('4','a'), (None,'a'), ('7', None)."""
    qid = (qid or "").strip()
    m = re.match(r"^(\d+)\s*[\(（]\s*([a-zA-Z0-9ivxIVX]+)[\)）]\s*$", qid)
    if m:
        return m.group(1), m.group(2).lower()
    m = re.match(r"^[\(（]\s*([a-zA-Z0-9ivxIVX]+)[\)）]\s*$", qid)
    if m:
        return None, m.group(1).lower()
    m = re.match(r"^(\d+)\s*$", qid)
    if m:
        return m.group(1), None
    return qid or None, None


def format_sub_label(sub: str | None, original_qid: str) -> str:
    if sub is None:
        return ""
    # keep roman / letter style
    if re.fullmatch(r"[ivx]+", sub):
        return f"({sub})"
    return f"({sub})"


def merge_question_text(parts: list[tuple[str | None, str]]) -> str:
    """parts: list of (sub_label_or_None, text)."""
    chunks: list[str] = []
    for sub, text in parts:
        text = text.strip()
        if not text:
            continue
        # Already labeled?
        if sub and not re.match(rf"^\s*[\(（]?{re.escape(sub)}[\)）]?", text, re.I):
            # Avoid double-prefix if text starts with (a)
            if not re.match(r"^\s*[\(（][a-z0-9ivx]+[\)）]", text, re.I):
                text = f"({sub}) {text}"
        chunks.append(text)
    return "\n\n".join(chunks)


def merge_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    # Active group: same page + main number
    group: list[dict] = []
    group_page: int | None = None
    group_main: str | None = None

    def flush() -> None:
        nonlocal group, group_page, group_main
        if not group:
            return
        if len(group) == 1:
            out.append(group[0])
        else:
            base = json.loads(json.dumps(group[0], ensure_ascii=False))  # deep copy
            parts: list[tuple[str | None, str]] = []
            fig_parts: list[str] = []
            has_figure = False
            for r in group:
                qid = str((r.get("source") or {}).get("question_id") or "")
                _main, sub = parse_qid(qid)
                parts.append((sub, user_content(r)))
                fd = (r.get("figure_description") or "").strip()
                if fd:
                    fig_parts.append(fd)
                has_figure = has_figure or bool(r.get("has_figure"))
            set_user_content(base, merge_question_text(parts))
            base["has_figure"] = has_figure
            if fig_parts:
                # unique preserve order
                seen = set()
                uniq = []
                for f in fig_parts:
                    if f not in seen:
                        seen.add(f)
                        uniq.append(f)
                base["figure_description"] = "；".join(uniq)
            src = dict(base.get("source") or {})
            src["question_id"] = group_main or src.get("question_id")
            base["source"] = src
            # Stable id: keep first id but drop trailing _qXX conflict → use page main
            page = src.get("page", 0)
            pdf = src.get("pdf") or "draft"
            stem = Path(str(pdf)).stem if pdf else "draft"
            base["id"] = f"{stem}_p{int(page):03d}_q{group_main or 'merged'}"
            note = (base.get("notes") or "").strip()
            merge_note = f"merged {len(group)} subparts"
            base["notes"] = f"{note} | {merge_note}".strip(" |")
            out.append(base)
            print(f"  merged page={page} q={group_main}: {len(group)} -> 1")
        group = []
        group_page = None
        group_main = None

    for row in rows:
        src = row.get("source") or {}
        page = src.get("page")
        qid = str(src.get("question_id") or "")
        main, sub = parse_qid(qid)

        # Orphan subpart: attach to current group on same page, else start after previous main
        if main is None and sub is not None:
            if group and group_page == page and group_main is not None:
                group.append(row)
                continue
            # Attach to last flushed item on same page if it has same context
            if out:
                prev = out[-1]
                prev_page = (prev.get("source") or {}).get("page")
                prev_main = str((prev.get("source") or {}).get("question_id") or "")
                pm, _ = parse_qid(prev_main)
                if prev_page == page and pm is not None:
                    # reopen: pop prev into group
                    group = [out.pop(), row]
                    group_page = page
                    group_main = pm
                    continue
            # Cannot attach — keep as-is
            flush()
            out.append(row)
            continue

        # Main with optional sub, or plain main
        if main is not None:
            if group and group_page == page and group_main == main:
                group.append(row)
                continue
            flush()
            group = [row]
            group_page = page
            group_main = main
            # If this row has no subpart yet, still open group in case next orphan subs arrive
            continue

        # Unparseable id
        flush()
        out.append(row)

    flush()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge split (a)/(b) draft rows")
    parser.add_argument("--in", dest="inp", type=Path, default=Path("data/draft.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/draft.jsonl"))
    args = parser.parse_args()

    rows = load_jsonl(args.inp)
    print(f"Before: {len(rows)} rows")
    merged = merge_rows(rows)
    print(f"After:  {len(merged)} rows")
    save_jsonl(merged, args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
