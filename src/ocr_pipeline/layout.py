"""Stage 1: PDF -> images + Surya layout/reading-order."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from .models import BBox, BlockType, LayoutBlock

_LABEL_MAP = {
    "text": BlockType.TEXT,
    "sectionheader": BlockType.TITLE,
    "title": BlockType.TITLE,
    "listgroup": BlockType.LIST,
    "list": BlockType.LIST,
    "equation": BlockType.EQUATION,
    "formula": BlockType.FORMULA,
    "table": BlockType.TABLE,
    "figure": BlockType.FIGURE,
    "picture": BlockType.FIGURE,
    "caption": BlockType.TEXT,
    "footnote": BlockType.TEXT,
    "pageheader": BlockType.OTHER,
    "pagefooter": BlockType.OTHER,
    "code": BlockType.TEXT,
    "form": BlockType.OTHER,
    "tableofcontents": BlockType.OTHER,
    "chemicalblock": BlockType.OTHER,
    "diagram": BlockType.FIGURE,
    "bibliography": BlockType.TEXT,
    "blankpage": BlockType.OTHER,
}


def map_surya_label(label: str | None) -> BlockType:
    if not label:
        return BlockType.OTHER
    key = re.sub(r"[^a-z]", "", label.lower())
    return _LABEL_MAP.get(key, BlockType.OTHER)


def _stop_surya_docker_vlms() -> list[str]:
    """
    Stop leftover ``surya-vllm-*`` containers.

    Surya's ``VllmBackend.stop()`` only clears Python handles; Docker cleanup is
    registered for atexit, which is too late for Stage3 in the same process.
    """
    if shutil.which("docker") is None:
        return []
    try:
        listed = subprocess.run(
            ["docker", "ps", "--filter", "name=surya-vllm", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        return []
    names = [line.strip() for line in (listed.stdout or "").splitlines() if line.strip()]
    stopped: list[str] = []
    for name in names:
        try:
            subprocess.run(
                ["docker", "stop", name],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            stopped.append(name)
        except Exception:
            continue
    return stopped


def _wait_for_gpu_headroom(*, min_free_mib: int = 4096, timeout_s: float = 30.0) -> None:
    """Best-effort wait after docker stop so nvidia-smi free memory recovers."""
    if shutil.which("nvidia-smi") is None:
        return
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.free",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                timeout=10,
            )
            free = float(out.strip().splitlines()[0])
            if free >= min_free_mib:
                return
        except Exception:
            return
        time.sleep(1.0)


class LayoutAnalyzer:
    """PDF render + Surya layout (order included in v2; legacy ordering fallback)."""

    def __init__(self, dpi: int = 200, device: str = "cuda", force_backend: str = ""):
        self.dpi = dpi
        self.device = device
        self.force_backend = (force_backend or "").strip().lower()
        self._layout_predictor = None
        self._inference_manager = None  # Surya v2: must stop() to free Docker/vLLM VRAM
        self._backend = None  # "v2" | "legacy" | "fullpage"

    def pdf_to_images(self, pdf_path: Path, out_dir: Path, *, limit: int = 0) -> list[Path]:
        try:
            import fitz
        except ImportError as e:
            raise SystemExit("Missing pymupdf. pip install pymupdf") from e

        out_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(pdf_path)
        zoom = self.dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        saved: list[Path] = []
        try:
            total = len(doc)
            n = total if limit <= 0 else min(limit, total)
            for i in range(1, n + 1):
                page = doc[i - 1]
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                path = out_dir / f"page_{i:03d}.png"
                pix.save(str(path))
                saved.append(path)
                print(f"  page {i:03d}/{total:03d} -> {path}")
        finally:
            doc.close()
        return saved

    def _fullpage_block(self, image_path: Path, page: int, width: int, height: int) -> list[LayoutBlock]:
        """Fallback when Surya backend (Docker/vLLM) is unavailable."""
        print("[Layout] Fallback: single full-page TEXT block (no Surya boxes)")
        return [
            LayoutBlock(
                block_id=f"p{page:03d}_b000",
                block_type=BlockType.TEXT,
                bbox=BBox(0, 0, float(width), float(height)),
                order=0,
                page=page,
                image_path=image_path,
                meta={"label": "FullPageFallback"},
            )
        ]

    def release(self) -> None:
        """Free layout / Surya Docker-vLLM so the VLM can use VRAM (12GB cards)."""
        print("[Layout] Releasing layout weights before VLM")
        if self._inference_manager is not None:
            try:
                self._inference_manager.stop()
                print("[Layout] Stopped SuryaInferenceManager handles")
            except Exception as e:
                print(f"[Layout] SuryaInferenceManager.stop failed: {e}")
            self._inference_manager = None
        self._layout_predictor = None

        # Surya atexit-only docker cleanup is too late for same-process Stage3.
        stopped = _stop_surya_docker_vlms()
        if stopped:
            print(f"[Layout] Stopped docker VLM: {', '.join(stopped)}")
            _wait_for_gpu_headroom()

        # Keep _backend so we know if golden used fullpage; do not re-load mid-run
        try:
            import gc

            import torch

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _ensure_model(self) -> None:
        if self._layout_predictor is not None or self._backend == "fullpage":
            return

        if self.force_backend in {"fullpage", "fallback"}:
            self._backend = "fullpage"
            print("[Layout] force_backend=fullpage")
            return

        e_v2: Exception | None = None
        e_legacy: Exception | None = None

        # Prefer Surya 2 (needs Docker+vLLM or llama.cpp at runtime)
        try:
            from surya.inference import SuryaInferenceManager
            from surya.layout import LayoutPredictor

            print("[Surya] Using v2 LayoutPredictor (layout + order)")
            print("[Surya] Note: v2 usually needs Docker+vLLM; will fallback if runtime fails")
            self._inference_manager = SuryaInferenceManager()
            self._layout_predictor = LayoutPredictor(self._inference_manager)
            self._backend = "v2"
            return
        except Exception as e:
            e_v2 = e
            self._inference_manager = None
            print(f"[Surya] v2 unavailable ({e_v2}); trying legacy...")

        try:
            from surya.layout import batch_layout_detection
            from surya.model.layout.model import load_model as load_layout_model
            from surya.model.layout.processor import load_processor as load_layout_processor
            from surya.model.ordering.model import load_model as load_order_model
            from surya.model.ordering.processor import load_processor as load_order_processor
            from surya.ordering import batch_ordering

            print("[Surya] Using legacy layout + ordering")
            self._layout_predictor = {
                "layout_model": load_layout_model(device=self.device),
                "layout_processor": load_layout_processor(),
                "order_model": load_order_model(device=self.device),
                "order_processor": load_order_processor(),
                "batch_layout_detection": batch_layout_detection,
                "batch_ordering": batch_ordering,
            }
            self._backend = "legacy"
            return
        except Exception as e:
            e_legacy = e
            print(
                f"[Surya] legacy unavailable (v2={e_v2}; legacy={e_legacy}); "
                "using full-page fallback"
            )
            self._backend = "fullpage"
            self._layout_predictor = None

    def detect_layout(self, image_path: Path, page: int) -> list[LayoutBlock]:
        self._ensure_model()
        from PIL import Image

        with Image.open(image_path) as im:
            image = im.convert("RGB")
            image.load()
            width, height = image.size

        if self._backend == "fullpage":
            return self._fullpage_block(image_path, page, width, height)

        if self._backend == "v2":
            try:
                preds = self._layout_predictor([image])
            except Exception as e:
                print(f"[Surya] v2 runtime failed: {e}")
                print("[Surya] Tip: install Docker Desktop, or use full-page fallback")
                self._backend = "fullpage"
                self._layout_predictor = None
                return self._fullpage_block(image_path, page, width, height)

            page_pred = preds[0]
            bboxes = getattr(page_pred, "bboxes", None) or []
            blocks: list[LayoutBlock] = []
            for idx, box in enumerate(bboxes):
                label = getattr(box, "label", None) or getattr(box, "raw_label", "")
                bb = getattr(box, "bbox", None)
                if bb is None and hasattr(box, "polygon"):
                    xs = [p[0] for p in box.polygon]
                    ys = [p[1] for p in box.polygon]
                    bb = [min(xs), min(ys), max(xs), max(ys)]
                if not bb or len(bb) < 4:
                    continue
                order = int(getattr(box, "position", idx))
                bbox = BBox(float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])).clamp(
                    width, height
                )
                blocks.append(
                    LayoutBlock(
                        block_id=f"p{page:03d}_b{idx:03d}",
                        block_type=map_surya_label(str(label)),
                        bbox=bbox,
                        order=order,
                        page=page,
                        image_path=image_path,
                        meta={"label": str(label)},
                    )
                )
            if not blocks:
                return self._fullpage_block(image_path, page, width, height)
            return blocks

        # legacy
        assert isinstance(self._layout_predictor, dict)
        pack = self._layout_predictor
        try:
            layout_preds = pack["batch_layout_detection"](
                [image], pack["layout_model"], pack["layout_processor"]
            )
        except Exception as e:
            print(f"[Surya] legacy runtime failed: {e}; full-page fallback")
            self._backend = "fullpage"
            return self._fullpage_block(image_path, page, width, height)

        layout = layout_preds[0]
        raw_boxes = []
        blocks = []
        for idx, box in enumerate(getattr(layout, "bboxes", []) or []):
            label = getattr(box, "label", "")
            bb = getattr(box, "bbox", None)
            if not bb:
                continue
            bbox = BBox(float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])).clamp(
                width, height
            )
            raw_boxes.append(bb)
            blocks.append(
                LayoutBlock(
                    block_id=f"p{page:03d}_b{idx:03d}",
                    block_type=map_surya_label(str(label)),
                    bbox=bbox,
                    order=idx,
                    page=page,
                    image_path=image_path,
                    meta={"label": str(label)},
                )
            )
        if blocks and raw_boxes:
            order_preds = pack["batch_ordering"](
                [image], [raw_boxes], pack["order_model"], pack["order_processor"]
            )
            order_list = getattr(order_preds[0], "bboxes", None) or order_preds[0]
            for i, block in enumerate(blocks):
                if i < len(order_list):
                    pos = getattr(order_list[i], "position", i)
                    block.order = int(pos)
        if not blocks:
            return self._fullpage_block(image_path, page, width, height)
        return blocks

    def order_blocks(self, blocks: list[LayoutBlock], image_path: Path) -> list[LayoutBlock]:
        # v2 already has position; legacy filled in detect_layout
        return sorted(blocks, key=lambda b: b.order)

    def analyze_page(self, image_path: Path, page: int) -> list[LayoutBlock]:
        blocks = self.detect_layout(image_path, page)
        return self.order_blocks(blocks, image_path)
