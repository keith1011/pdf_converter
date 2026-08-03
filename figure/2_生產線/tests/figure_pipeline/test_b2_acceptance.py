from __future__ import annotations

from pathlib import Path

from figure_pipeline.classification_models import ClassifiedFigureAsset
from figure_pipeline.classification_prompt import FIGURE_CLASSIFICATION_PROMPT
from figure_pipeline.classification_runner import classify_bundle
from figure_pipeline.models import FigureAsset
from figure_pipeline.proposal import sha256_file

SOURCE = Path("3.分析結果/output/figure_pipeline/2015p2/q018")
FIXTURE = Path(__file__).parent / "fixtures/qwen_geometry_response.txt"


class FakeVlmClient:
    model_name = "Qwen/Qwen3-VL-8B-Instruct"
    load_in_4bit = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path, int]] = []

    def generate(
        self,
        prompt: str,
        image_path: Path | None = None,
        *,
        max_new_tokens: int | None = None,
    ) -> str:
        assert image_path is not None
        self.calls.append((prompt, image_path, int(max_new_tokens or 0)))
        return FIXTURE.read_text(encoding="utf-8")


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_q18_b2_acceptance_keeps_identity_and_hashes(tmp_path: Path) -> None:
    source_snapshot = snapshot_tree(SOURCE)
    original = FigureAsset.model_validate_json(
        (SOURCE / "figure_asset.json").read_text(encoding="utf-8")
    )
    fake = FakeVlmClient()

    asset = classify_bundle(
        SOURCE,
        tmp_path / "q018-b2",
        client=fake,
        max_new_tokens=256,
    )

    destination = tmp_path / "q018-b2"
    assert isinstance(asset, ClassifiedFigureAsset)
    assert asset.asset_id == original.asset_id
    assert asset.parent_question_id == original.parent_question_id
    assert asset.source.bbox == original.source.bbox
    assert asset.source.sha256 == original.source.sha256
    assert sha256_file(destination / asset.source.crop_path) == asset.source.sha256
    assert asset.classification.proposed is not None
    assert asset.classification.proposed.visual_family == "geometry"
    assert asset.classification.proposed.prompt_version == "figure-b2-v1"
    assert asset.classification.reviewed is None
    assert fake.calls == [(FIGURE_CLASSIFICATION_PROMPT, SOURCE.resolve() / asset.source.crop_path, 256)]
    assert snapshot_tree(SOURCE) == source_snapshot
