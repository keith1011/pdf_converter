from ocr_pipeline.nup_label import guess_semantic, maybe_label_panels
from ocr_pipeline.nup_types import NupClass, NupDecision, NupPanel


def test_guess_semantic_zh_vs_en():
    assert guess_semantic("這是中文試題內容一二三") == "zh"
    assert guess_semantic("This is an English stem about algebra.") == "en"


def test_maybe_label_panels_sets_semantic():
    decision = NupDecision(
        page_index=0,
        nup_class=NupClass.TWO_LR,
        confidence=0.9,
        threshold=0.75,
        fallback=False,
        panels=[
            NupPanel("v0", (0.0, 0.0, 0.5, 1.0)),
            NupPanel("v1", (0.5, 0.0, 1.0, 1.0)),
        ],
    )
    out = maybe_label_panels(
        decision,
        {"v0": "這是中文試題內容一二三四五六", "v1": "This is an English exam stem here."},
    )
    assert out.panels[0].semantic == "zh"
    assert out.panels[1].semantic == "en"
