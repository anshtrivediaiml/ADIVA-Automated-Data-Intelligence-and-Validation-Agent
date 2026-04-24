from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from extractors.ocr_extractor import OCRExtractor


def test_infer_financial_table_profile_from_text():
    extractor = OCRExtractor()

    profile = extractor._infer_preprocessing_profile(
        "Bank Statement\nDate Amount Balance\nOpening Balance 45,230.00\nClosing Balance 72,980.00",
        58.0,
    )

    assert profile == "financial_table"


def test_infer_academic_table_profile_from_text():
    extractor = OCRExtractor()

    profile = extractor._infer_preprocessing_profile(
        "Semester Marksheet\nSubject Marks Grade Result Total Marks",
        62.0,
    )

    assert profile == "academic_table"


def test_profile_options_preserve_grid_lines_for_table_docs():
    extractor = OCRExtractor()

    financial = extractor._preprocessing_profile_options("financial_table", aggressive=True)
    academic = extractor._preprocessing_profile_options("academic_table", aggressive=True)
    balanced = extractor._preprocessing_profile_options("balanced", aggressive=True)

    assert financial["preserve_grid_lines"] is True
    assert academic["preserve_grid_lines"] is True
    assert balanced["preserve_grid_lines"] is False
    assert financial["cleanup_background"] is False


def test_enhance_image_accepts_profile_parameter():
    extractor = OCRExtractor()
    image = Image.new("RGB", (900, 1400), "white")

    enhanced = extractor._enhance_image(image, aggressive=True, profile="financial_table")

    assert enhanced is not None
    assert enhanced.size[0] > 0
    assert enhanced.size[1] > 0
