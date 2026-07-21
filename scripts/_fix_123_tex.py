import sys
from pathlib import Path
sys.path.insert(0, "src")
from ocr_pipeline.assemble import FinalPolisher
from ocr_pipeline.latex_math import sanitize_tex_document
p = Path("output/123.tex")
raw = p.read_text(encoding="utf-8")
ext = FinalPolisher._extract_tex_document(raw) or raw
p.write_text(sanitize_tex_document(ext), encoding="utf-8")
print("wrote", p, "chars", p.stat().st_size)
print(p.read_text(encoding="utf-8")[:200])