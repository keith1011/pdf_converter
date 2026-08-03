"""Stage OCR artifacts for publication as a homelab job."""

from __future__ import annotations

import shutil
from pathlib import Path


def stage_job_dir(*, doc_id: str, output_dir: Path, staging_dir: Path) -> Path:
    """Copy one document's publishable artifacts into a clean staging directory."""
    output_dir = output_dir.resolve()
    staging_dir = staging_dir.resolve()
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    text = output_dir / f"{doc_id}.txt"
    if not text.is_file():
        raise FileNotFoundError(text)
    shutil.copy2(text, staging_dir / text.name)

    for name in (f"{doc_id}.tex", f"{doc_id}.pageir.json", f"{doc_id}.quality.json"):
        source = output_dir / name
        if source.is_file():
            shutil.copy2(source, staging_dir / name)

    figures_source = output_dir / doc_id / "figures"
    if figures_source.is_dir():
        figures_destination = staging_dir / "figures"
        for png in sorted(figures_source.glob("*.png")):
            figures_destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(png, figures_destination / png.name)

    return staging_dir
