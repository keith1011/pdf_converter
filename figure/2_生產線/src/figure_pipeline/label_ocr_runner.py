from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ocr_pipeline.vlm_client import VlmClient

from .classification_models import ClassifiedFigureAsset
from .label_ocr_models import FigureLabelOcr, LabeledFigureAsset
from .label_ocr_parser import VisibleLabelParseError, parse_visible_label_response
from .label_ocr_prompt import VISIBLE_LABEL_PROMPT_VERSION, get_visible_label_prompt
from .models import resolve_bundle_path
from .proposal import sha256_file


def _verify_response_reference(
    source_dir: Path,
    *,
    response_path: str | None,
    response_sha256: str | None,
    label: str,
) -> None:
    if response_path is None and response_sha256 is None:
        return
    if response_path is None or response_sha256 is None:
        raise ValueError(f"{label} response reference is incomplete")
    resolved = resolve_bundle_path(source_dir, response_path)
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if sha256_file(resolved) != response_sha256:
        raise ValueError(f"{label} response hash mismatch")


def _load_b2_asset(source_dir: Path) -> tuple[ClassifiedFigureAsset, Path]:
    asset_path = source_dir / "figure_asset.json"
    asset = ClassifiedFigureAsset.model_validate_json(asset_path.read_text(encoding="utf-8"))
    crop_path = resolve_bundle_path(source_dir, asset.source.crop_path)
    if not crop_path.is_file():
        raise FileNotFoundError(crop_path)
    if sha256_file(crop_path) != asset.source.sha256:
        raise ValueError("B2 figure crop hash mismatch")
    _verify_response_reference(
        source_dir,
        response_path=asset.classification.response_path,
        response_sha256=asset.classification.response_sha256,
        label="B2 classification",
    )
    return asset, crop_path


def _client_metadata(client: VlmClient) -> tuple[str, str]:
    model_id = str(getattr(client, "model_name", "")).strip()
    if not model_id:
        raise ValueError("label OCR client must expose a non-empty model_name")
    if getattr(client, "load_in_4bit", None) is not True:
        raise ValueError("figure label OCR requires a 4-bit client")
    return model_id, "4-bit"


def _generate_unmodified(
    client: VlmClient,
    *,
    crop_path: Path,
    max_new_tokens: int,
    prompt_version: str,
) -> str:
    generate_raw: Any = getattr(client, "generate_raw", None)
    generator = generate_raw if callable(generate_raw) else client.generate
    raw = generator(
        get_visible_label_prompt(prompt_version),
        image_path=crop_path,
        max_new_tokens=max_new_tokens,
    )
    if not isinstance(raw, str):
        raise TypeError("label OCR client must return text")
    return raw


def _write_asset(path: Path, asset: LabeledFigureAsset) -> None:
    payload = json.dumps(
        asset.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    path.write_bytes((payload + chr(10)).encode("utf-8"))


def extract_visible_labels_bundle(
    source_dir: Path,
    destination: Path,
    *,
    client: VlmClient,
    max_new_tokens: int = 384,
    prompt_version: str = VISIBLE_LABEL_PROMPT_VERSION,
) -> LabeledFigureAsset:
    if destination.exists():
        raise FileExistsError(destination)
    get_visible_label_prompt(prompt_version)
    if max_new_tokens <= 0:
        raise ValueError("max_new_tokens must be positive")

    asset, crop_path = _load_b2_asset(source_dir)
    model_id, quantization = _client_metadata(client)
    stage = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"

    try:
        shutil.copytree(source_dir, stage, dirs_exist_ok=True)
        raw = _generate_unmodified(
            client,
            crop_path=crop_path,
            max_new_tokens=max_new_tokens,
            prompt_version=prompt_version,
        )
        try:
            proposal = parse_visible_label_response(
                raw,
                model_id=model_id,
                quantization=quantization,
                prompt_version=prompt_version,
            )
        except VisibleLabelParseError as exc:
            response_name = "visible_label_response.txt"
            response_path = stage / response_name
            response_path.write_bytes(raw.encode("utf-8"))
            label_ocr = FigureLabelOcr(
                status="failed",
                error=str(exc),
                response_path=response_name,
                response_sha256=sha256_file(response_path),
                model_id=model_id,
                quantization=quantization,
                prompt_version=prompt_version,
            )
        else:
            label_ocr = FigureLabelOcr(
                status="pending",
                proposed=proposal,
            )

        labeled = LabeledFigureAsset.from_b2(asset, label_ocr)
        json_path = stage / "figure_asset.json"
        _write_asset(json_path, labeled)

        copied_crop = resolve_bundle_path(stage, labeled.source.crop_path)
        if sha256_file(copied_crop) != labeled.source.sha256:
            raise RuntimeError("copied figure crop hash mismatch")
        round_trip = LabeledFigureAsset.model_validate_json(
            json_path.read_text(encoding="utf-8")
        )
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return round_trip
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def extract_visible_labels_many(
    jobs: Sequence[tuple[Path, Path]],
    *,
    client: VlmClient,
    max_new_tokens: int = 384,
    prompt_version: str = VISIBLE_LABEL_PROMPT_VERSION,
) -> list[LabeledFigureAsset]:
    return [
        extract_visible_labels_bundle(
            source_dir,
            destination,
            client=client,
            max_new_tokens=max_new_tokens,
            prompt_version=prompt_version,
        )
        for source_dir, destination in jobs
    ]
