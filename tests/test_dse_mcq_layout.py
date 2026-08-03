from pathlib import Path

from ocr_pipeline.dse_mcq_layout import select_mcq_page_images


def test_select_mcq_page_images_skips_candidate_instructions_first_page():
    images = [
        Path("page_001.png"),
        Path("page_002.png"),
        Path("page_003.png"),
    ]

    assert select_mcq_page_images(images, skip_first_page=True) == images[1:]
