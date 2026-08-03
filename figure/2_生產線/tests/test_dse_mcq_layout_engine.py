from pathlib import Path

from PIL import Image

from ocr_pipeline.dse_mcq_layout_engine import DseMcqLayoutEngine
from ocr_pipeline.dse_mcq_profile import load_mcq_profile
from ocr_pipeline.dse_mcq_types import McqAnchors, McqRegion, OcrLine
from ocr_pipeline.factory import build_default_pipeline
from ocr_pipeline.models import BBox, BlockType, LayoutBlock


class _GenericLayout:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, int]] = []

    def analyze(self, image_path: Path, page: int) -> list[LayoutBlock]:
        self.calls.append((image_path, page))
        return [
            LayoutBlock(
                block_id=f"p{page:03d}_b000",
                block_type=BlockType.TEXT,
                bbox=BBox(0, 0, 10, 10),
                order=0,
                page=page,
                image_path=image_path,
            )
        ]

    def release(self) -> None:
        pass


def _region(question_id: int) -> McqRegion:
    return McqRegion(
        question_id=question_id,
        bbox=(10, 20, 90, 80),
        anchors=McqAnchors(A=True, B=True, C=True, D=True),
        incomplete=False,
    )


def test_dse_layout_engine_emits_question_block_metadata(tmp_path: Path) -> None:
    image_path = tmp_path / "page_002.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    generic = _GenericLayout()
    engine = DseMcqLayoutEngine(
        profile=load_mcq_profile(Path("2_生產線/config/profiles/math_cp_p2.yaml")),
        fallback_engine=generic,
        line_reader=lambda _path: [],
        region_detector=lambda _lines, _profile: [_region(1)],
    )

    blocks = engine.analyze(image_path, page=2)

    assert [block.block_id for block in blocks] == ["p002_q001"]
    assert blocks[0].meta["question_id"] == 1
    assert blocks[0].crop_path == tmp_path / "crops" / "p002_q001.png"
    assert generic.calls == []


def test_dse_layout_engine_uses_generic_fallback_when_no_question_is_found(tmp_path: Path) -> None:
    image_path = tmp_path / "page_002.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    generic = _GenericLayout()
    engine = DseMcqLayoutEngine(
        profile=load_mcq_profile(Path("2_生產線/config/profiles/math_cp_p2.yaml")),
        fallback_engine=generic,
        line_reader=lambda _path: [
            OcrLine("ordinary document", (0, 0, 50, 10), 100, 100)
        ],
    )

    blocks = engine.analyze(image_path, page=2)

    assert [block.block_id for block in blocks] == ["p002_b000"]
    assert generic.calls == [(image_path, 2)]


def test_factory_uses_dse_layout_engine_only_when_requested(tmp_path: Path) -> None:
    cfg = {"paths": {"pages_dir": str(tmp_path / "pages")}}

    generic = build_default_pipeline(cfg)
    dse = build_default_pipeline(cfg, dse_mcq=True)

    assert not isinstance(generic.layout_engine, DseMcqLayoutEngine)
    assert isinstance(dse.layout_engine, DseMcqLayoutEngine)
