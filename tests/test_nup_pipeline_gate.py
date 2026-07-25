from pathlib import Path

from PIL import Image

from ocr_pipeline.models import BBox, BlockType, LayoutBlock
from ocr_pipeline.nup_router import analyze_page_with_nup
from ocr_pipeline.nup_types import NupClass, NupDecision, NupPanel


def test_analyze_page_with_nup_splits_when_confident(tmp_path: Path, monkeypatch):
    page = tmp_path / "page.png"
    Image.new("RGB", (200, 100), (255, 255, 255)).save(page)
    panels_dir = tmp_path / "panels"
    panels_dir.mkdir()
    v0 = panels_dir / "v0.png"
    v1 = panels_dir / "v1.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(v0)
    Image.new("RGB", (100, 100), (255, 255, 255)).save(v1)

    decision = NupDecision(
        page_index=1,
        nup_class=NupClass.TWO_LR,
        confidence=0.9,
        threshold=0.75,
        fallback=False,
        panels=[
            NupPanel("v0", (0.0, 0.0, 0.5, 1.0), path=v0),
            NupPanel("v1", (0.5, 0.0, 1.0, 1.0), path=v1),
        ],
    )

    def fake_decide(*_a, **_k):
        return decision

    monkeypatch.setattr("ocr_pipeline.nup_router.decide_nup", fake_decide)

    calls: list[Path] = []

    def analyze_fn(image_path: Path, page: int) -> list[LayoutBlock]:
        calls.append(image_path)
        return [
            LayoutBlock(
                block_id="x",
                block_type=BlockType.TEXT,
                bbox=BBox(1, 1, 10, 10),
                order=0,
                page=page,
                image_path=image_path,
                raw_text=image_path.stem,
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
    assert calls == [v0, v1]
    assert [b.meta["version_id"] for b in blocks] == ["v0", "v1"]
    assert blocks[1].bbox.x1 == 101.0  # 1 + 100 offset


def test_analyze_page_with_nup_fallback_calls_once(tmp_path: Path, monkeypatch):
    page = tmp_path / "page.png"
    Image.new("RGB", (40, 40), (255, 255, 255)).save(page)

    monkeypatch.setattr(
        "ocr_pipeline.nup_router.decide_nup",
        lambda *_a, **_k: NupDecision(
            page_index=2,
            nup_class=NupClass.UNCERTAIN,
            confidence=0.5,
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
