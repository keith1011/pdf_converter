"""Layout release must stop Surya Docker/vLLM so Stage3 has VRAM."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ocr_pipeline.layout import LayoutAnalyzer, _stop_surya_docker_vlms


def test_release_stops_surya_inference_manager_and_docker():
    layout = LayoutAnalyzer()
    manager = MagicMock()
    layout._backend = "v2"
    layout._layout_predictor = object()
    layout._inference_manager = manager

    with (
        patch("ocr_pipeline.layout._stop_surya_docker_vlms", return_value=["surya-vllm-1"]) as docker_stop,
        patch("ocr_pipeline.layout._wait_for_gpu_headroom") as wait_gpu,
    ):
        layout.release()

    manager.stop.assert_called_once()
    docker_stop.assert_called_once()
    wait_gpu.assert_called_once()
    assert layout._inference_manager is None
    assert layout._layout_predictor is None


def test_release_is_safe_without_manager():
    layout = LayoutAnalyzer()
    layout._backend = "fullpage"
    layout._layout_predictor = None
    layout._inference_manager = None
    with (
        patch("ocr_pipeline.layout._stop_surya_docker_vlms", return_value=[]),
        patch("ocr_pipeline.layout._wait_for_gpu_headroom"),
    ):
        layout.release()  # must not raise


def test_ensure_model_v2_keeps_manager_reference(monkeypatch):
    layout = LayoutAnalyzer()
    fake_manager = MagicMock()

    monkeypatch.setattr(
        "surya.inference.SuryaInferenceManager",
        MagicMock(return_value=fake_manager),
    )

    class _Pred:
        def __init__(self, manager=None):
            self.manager = manager

    monkeypatch.setattr("surya.layout.LayoutPredictor", _Pred)

    layout._ensure_model()
    assert layout._backend == "v2"
    assert layout._inference_manager is fake_manager
    assert layout._layout_predictor.manager is fake_manager


def test_stop_surya_docker_vlms_stops_named_containers():
    with patch("ocr_pipeline.layout.shutil.which", return_value="docker"), patch(
        "ocr_pipeline.layout.subprocess.run"
    ) as run:
        run.side_effect = [
            MagicMock(returncode=0, stdout="surya-vllm-123\nsurya-vllm-456\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        stopped = _stop_surya_docker_vlms()
    assert stopped == ["surya-vllm-123", "surya-vllm-456"]
    assert run.call_count == 3
    assert run.call_args_list[1].args[0][:3] == ["docker", "stop", "surya-vllm-123"]
