from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ocr_pipeline.vlm_client import VlmClient

from .classification_models import ClassifiedFigureAsset, FigureClassification
from .classification_parser import (
    ClassificationParseError,
    parse_classification_response,
)
from .classification_prompt import (
    FIGURE_CLASSIFICATION_PROMPT,
    FIGURE_CLASSIFICATION_PROMPT_VERSION,
)
from .models import FigureAsset
from .proposal import sha256_file


def _load_b1_asset(source_dir: Path) -> tuple[FigureAsset, Path]:
    asset_path = source_dir / "figure_asset.json"
    asset = FigureAsset.model_validate_json(asset_path.read_text(encoding="utf-8"))
    crop_path = source_dir / asset.source.crop_path
    if not crop_path.is_file():
        raise FileNotFoundError(crop_path)
    if sha256_file(crop_path) != asset.source.sha256:
        raise ValueError("B1 figure crop hash mismatch")
    return asset, crop_path


def _client_metadata(client: VlmClient) -> tuple[str, str]:
    model_id = str(getattr(client, "model_name", "")).strip()
    if not model_id:
        raise ValueError("classification client must expose a non-empty model_name")
    if getattr(client, "load_in_4bit", None) is not True:
        raise ValueError("figure classification requires a 4-bit client")
    return model_id, "4-bit"


def _generate_unmodified(
    client: VlmClient,
    *,
    crop_path: Path,
    max_new_tokens: int,
) -> str:
    generate_raw: Any = getattr(client, "generate_raw", None)
    generator = generate_raw if callable(generate_raw) else client.generate
    raw = generator(
        FIGURE_CLASSIFICATION_PROMPT,
        image_path=crop_path,
        max_new_tokens=max_new_tokens,
    )
    if not isinstance(raw, str):
        raise TypeError("classification client must return text")
    return raw


def _write_asset(path: Path, asset: ClassifiedFigureAsset) -> None:
    payload = json.dumps(
        asset.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    path.write_bytes((payload + chr(10)).encode("utf-8"))


def classify_bundle(
    source_dir: Path,
    destination: Path,
    *,
    client: VlmClient,
    max_new_tokens: int = 256,
    prompt_version: str = FIGURE_CLASSIFICATION_PROMPT_VERSION,
) -> ClassifiedFigureAsset:
    if destination.exists():
        raise FileExistsError(destination)
    if prompt_version != FIGURE_CLASSIFICATION_PROMPT_VERSION:
        raise ValueError(f"unsupported prompt_version: {prompt_version}")
    if max_new_tokens <= 0:
        raise ValueError("max_new_tokens must be positive")

    asset, crop_path = _load_b1_asset(source_dir)
    model_id, quantization = _client_metadata(client)
    stage = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"

    try:
        shutil.copytree(source_dir, stage, dirs_exist_ok=True)
        raw = _generate_unmodified(
            client,
            crop_path=crop_path,
            max_new_tokens=max_new_tokens,
        )
        try:
            proposal = parse_classification_response(
                raw,
                model_id=model_id,
                quantization=quantization,
                prompt_version=prompt_version,
            )
        except ClassificationParseError as exc:
            response_name = "classification_response.txt"
            response_path = stage / response_name
            response_path.write_bytes(raw.encode("utf-8"))
            classification = FigureClassification(
                status="failed",
                error=str(exc),
                response_path=response_name,
                response_sha256=sha256_file(response_path),
                model_id=model_id,
                quantization=quantization,
                prompt_version=prompt_version,
            )
        else:
            classification = FigureClassification(
                status="pending",
                proposed=proposal,
            )

        classified = ClassifiedFigureAsset.from_b1(asset, classification)
        json_path = stage / "figure_asset.json"
        _write_asset(json_path, classified)

        copied_crop = stage / classified.source.crop_path
        if sha256_file(copied_crop) != classified.source.sha256:
            raise RuntimeError("copied figure crop hash mismatch")
        round_trip = ClassifiedFigureAsset.model_validate_json(
            json_path.read_text(encoding="utf-8")
        )
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return round_trip
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def classify_many(
    jobs: Sequence[tuple[Path, Path]],
    *,
    client: VlmClient,
    max_new_tokens: int = 256,
    prompt_version: str = FIGURE_CLASSIFICATION_PROMPT_VERSION,
) -> list[ClassifiedFigureAsset]:
    return [
        classify_bundle(
            source_dir,
            destination,
            client=client,
            max_new_tokens=max_new_tokens,
            prompt_version=prompt_version,
        )
        for source_dir, destination in jobs
    ]
