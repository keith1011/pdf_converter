"""Build a tiny second Wave-1 doc (different doc_id) from a slice of an existing PageIR."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "output" / "123.pageir.json"
OUT = ROOT / "output" / "wave1demo"
DOC_ID = "wave1demo"


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    pages = data.get("pages") or []
    # Keep first page only, first ~8 segments — enough for gate, not a clone of 123
    slim_pages = []
    if pages:
        p0 = dict(pages[0])
        segs = list(p0.get("segments") or [])[:8]
        # Tag text so it is distinguishable from doc 123
        for i, s in enumerate(segs):
            s = dict(s)
            t = (s.get("text") or "").strip()
            s["text"] = f"[wave1demo p0 s{i}] {t}"[:500]
            segs[i] = s
        p0["segments"] = segs
        p0["page_index"] = 0
        slim_pages.append(p0)
    out = {"doc_id": DOC_ID, "pages": slim_pages, "note": "synthetic wave1 second doc"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{DOC_ID}.pageir.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = []
    for p in slim_pages:
        for s in p.get("segments") or []:
            lines.append(s.get("text") or "")
    (OUT / f"{DOC_ID}.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    (OUT / f"{DOC_ID}.tex").write_text(
        "\\documentclass{article}\\begin{document}\n"
        + "\n\n".join(lines)
        + "\n\\end{document}\n",
        encoding="utf-8",
    )
    # optional pdf placeholder: copy tiny existing if present
    pdf_src = ROOT / "output" / "123.pdf"
    if pdf_src.is_file():
        shutil.copy2(pdf_src, OUT / f"{DOC_ID}.pdf")
    print(f"OK wrote {OUT} segments={sum(len(p.get('segments') or []) for p in slim_pages)}")


if __name__ == "__main__":
    main()
