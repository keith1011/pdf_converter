from pathlib import Path

from PIL import Image

from ocr_pipeline.assemble import DraftAssembler
from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.nup_router import analyze_page_with_nup
from ocr_pipeline.nup_types import NupClass, NupDecision, NupPanel


def test_dual_panels_do_not_interleave_question_order(tmp_path: Path, monkeypatch):
    page = tmp_path / "page.png"
    Image.new("RGB", (200, 100), (255, 255, 255)).save(page)
    panels = tmp_path / "panels"
    panels.mkdir()
    v0 = panels / "v0.png"
    v1 = panels / "v1.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(v0)
    Image.new("RGB", (100, 100), (255, 255, 255)).save(v1)

    monkeypatch.setattr(
        "ocr_pipeline.nup_router.decide_nup",
        lambda *_a, **_k: NupDecision(
            page_index=1,
            nup_class=NupClass.TWO_LR,
            confidence=0.95,
            threshold=0.75,
            fallback=False,
            panels=[
                NupPanel("v0", (0.0, 0.0, 0.5, 1.0), path=v0),
                NupPanel("v1", (0.5, 0.0, 1.0, 1.0), path=v1),
            ],
        ),
    )

    def analyze_fn(image_path: Path, page: int) -> list[LayoutBlock]:
        label = "Q16 left" if image_path.stem == "v0" else "Q19 right"
        return [
            LayoutBlock(
                block_id="x",
                block_type=BlockType.TEXT,
                bbox=BBox(0, 0, 10, 10),
                order=0,
                page=page,
                image_path=image_path,
                raw_text=label,
            )
        ]

    blocks = analyze_page_with_nup(
        analyze_fn,
        page,
        page=1,
        page_dir=tmp_path,
        enabled=True,
        threshold=0.75,
        margin_norm=0.0,
    )
    draft = DraftAssembler().stitch(blocks)
    assert draft.index("Q16") < draft.index("Q19")


def test_uncertain_uses_whole_page_once(tmp_path: Path, monkeypatch):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), (255, 255, 255)).save(page)
    monkeypatch.setattr(
        "ocr_pipeline.nup_router.decide_nup",
        lambda *_a, **_k: NupDecision(
            page_index=2,
            nup_class=NupClass.UNCERTAIN,
            confidence=0.4,
            threshold=0.75,
            fallback=True,
            panels=[],
        ),
    )
    calls: list[Path] = []

    def analyze_fn(image_path: Path, page: int) -> list[LayoutBlock]:
        calls.append(image_path)
        return []

    analyze_page_with_nup(
        analyze_fn,
        page,
        page=2,
        page_dir=tmp_path,
        enabled=True,
        threshold=0.75,
        margin_norm=0.0,
    )
    assert calls == [page]
