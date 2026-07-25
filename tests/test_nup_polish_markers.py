from unittest.mock import MagicMock

from ocr_pipeline.assemble import FinalPolisher


def test_polish_preserves_nup_markers():
    vlm = MagicMock()
    # Each generate call polishes one version chunk
    vlm.generate.side_effect = [
        "<<<TXT>>>\nQ16 polished\n<<<TEX>>>\n\\documentclass{ctexart}\\begin{document}Q16 polished\\end{document}",
        "<<<TXT>>>\nQ19 polished\n<<<TEX>>>\n\\documentclass{ctexart}\\begin{document}Q19 polished\\end{document}",
    ]
    polisher = FinalPolisher(vlm)
    draft = "<<<nup:v0>>>\n\nQ16 left\n\n<<<nup:v1>>>\n\nQ19 right"
    txt, tex, _ = polisher.polish(draft)
    assert "<<<nup:v0>>>" in txt
    assert "<<<nup:v1>>>" in txt
    assert txt.index("<<<nup:v0>>>") < txt.index("Q16")
    assert txt.index("Q16") < txt.index("<<<nup:v1>>>")
    assert "<<<nup:v0>>>" in tex or "Q16" in tex
    assert vlm.generate.call_count == 2
