"""
ADIVA - OCR Extractor (Scanned Documents)

Extracts text from scanned PDFs and images using Tesseract OCR with
PaddleOCR/EasyOCR fallback for difficult low-confidence cases.

Handles:
- Printed documents (Tesseract, fast)
- Handwritten documents (EasyOCR fallback when confidence < 60%)
- Low quality scans (aggressive CLAHE + morphological enhancement)
- Rotated/upside-down scans (Tesseract OSD auto-correction)
- Tables in scanned images (img2table)
- Multi-page PDFs with per-page language detection
- English, Hindi (Devanagari), Gujarati scripts
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import os
import platform
import re
import unicodedata
try:
    import config
    from extractors.base_extractor import BaseExtractor
    from logger import logger, log_extraction, log_error
except ModuleNotFoundError:
    from backend import config
    from backend.extractors.base_extractor import BaseExtractor
    from backend.logger import logger, log_extraction, log_error
import time

# ── Core OCR dependencies ────────────────────────────────────────────────────
try:
    import pytesseract

    if config.TESSERACT_CMD_PATH:
        pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD_PATH
    elif platform.system() == "Windows":
        common_windows_path = Path(os.environ.get("ProgramFiles", "")) / "Tesseract-OCR" / "tesseract.exe"
        if common_windows_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(common_windows_path)
    from pdf2image import convert_from_path, pdfinfo_from_path
    from PIL import Image, ImageFilter, ImageEnhance

    HAS_OCR = True
    HAS_PDFINFO = True
except ImportError:
    HAS_OCR = False
    HAS_PDFINFO = False
    logger.warning("OCR dependencies not available. Install pytesseract and pdf2image.")

# ── OpenCV for advanced preprocessing ───────────────────────────────────────
try:
    import cv2
    import numpy as np

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.info("OpenCV not available. Basic PIL preprocessing will be used.")

# ── EasyOCR for compatibility fallback ─────────────────────────────────────
try:
    import easyocr

    HAS_EASYOCR = True
    logger.info("EasyOCR available as compatibility fallback.")
except ImportError:
    HAS_EASYOCR = False
    logger.info("EasyOCR not installed.")

# ── PaddleOCR preferred fallback ────────────────────────────────────────────
_PADDLE_RUNTIME_HOME = config.OUTPUTS_DIR / "paddle_runtime"
_PADDLE_RUNTIME_HOME.mkdir(parents=True, exist_ok=True)
_PADDLE_TEMP_HOME = _PADDLE_RUNTIME_HOME / "temp"
_PADDLE_TEMP_HOME.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PADDLE_HOME", str(_PADDLE_RUNTIME_HOME))
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ["USERPROFILE"] = str(_PADDLE_RUNTIME_HOME)
os.environ["HOME"] = str(_PADDLE_RUNTIME_HOME)
os.environ["TEMP"] = str(_PADDLE_TEMP_HOME)
os.environ["TMP"] = str(_PADDLE_TEMP_HOME)
os.environ["TMPDIR"] = str(_PADDLE_TEMP_HOME)

try:
    from paddleocr import PaddleOCR

    HAS_PADDLEOCR = True
    logger.info("PaddleOCR available as preferred fallback.")
except ImportError:
    HAS_PADDLEOCR = False
    logger.info("PaddleOCR not installed.")

# ── img2table for table extraction from images ───────────────────────────────
try:
    from img2table.document import Image as Img2TableImage
    from img2table.ocr import TesseractOCR

    HAS_IMG2TABLE = True
    logger.info("img2table available for scanned table extraction.")
except ImportError:
    HAS_IMG2TABLE = False
    logger.info("img2table not installed. Table extraction from images disabled.")


# ── Unicode script ranges ────────────────────────────────────────────────────
DEVANAGARI_RANGE = (0x0900, 0x097F)
GUJARATI_RANGE = (0x0A80, 0x0AFF)
LATIN_RANGE = (0x0041, 0x007A)

# Ratio threshold: if Indian script chars > 15% of total → that language
INDIAN_SCRIPT_RATIO_THRESHOLD = 0.15

# Confidence threshold below which EasyOCR fallback is triggered
EASYOCR_FALLBACK_THRESHOLD = 60.0
TESSERACT_TIMEOUT_SEC = 25
MAX_ENHANCED_PIXELS = 16_000_000
HIGH_CONFIDENCE_EARLY_EXIT = 85.0
MIN_TEXT_CHARS_FOR_EARLY_EXIT = 250
TARGETED_LANG_RETRY_MAX_CONF = 80.0
EASYOCR_MAX_PIXELS = 2_000_000
# Minimum short-side resolution before any OCR pipeline runs
MIN_SHORT_SIDE_PX = 1200
SPARSE_TEXT_RETRY_CHAR_THRESHOLD = 120
PSM_11_RETRY_CONFIDENCE_THRESHOLD = 72.0
LAYOUT_OCR_TRIGGER_CONFIDENCE = 72.0
LAYOUT_OCR_MIN_REGIONS = 1
LAYOUT_OCR_MAX_REGIONS = 10


def _detect_script_from_text(text: str) -> str:
    """
    Detect dominant script using Unicode character RATIO (not absolute count).
    Ratio approach correctly handles bilingual docs (Hindi-English contracts).
    Returns: 'hin', 'guj', or 'eng'
    """
    if not text:
        return "eng"

    # Normalize Unicode to NFC to handle different encodings of same character
    text = unicodedata.normalize("NFC", text)

    devanagari_count = 0
    gujarati_count = 0
    latin_count = 0

    for ch in text:
        cp = ord(ch)
        if DEVANAGARI_RANGE[0] <= cp <= DEVANAGARI_RANGE[1]:
            devanagari_count += 1
        elif GUJARATI_RANGE[0] <= cp <= GUJARATI_RANGE[1]:
            gujarati_count += 1
        elif LATIN_RANGE[0] <= cp <= LATIN_RANGE[1]:
            latin_count += 1

    total_alpha = devanagari_count + gujarati_count + latin_count
    if total_alpha == 0:
        return "eng"

    hin_ratio = devanagari_count / total_alpha
    guj_ratio = gujarati_count / total_alpha

    if (
        hin_ratio >= INDIAN_SCRIPT_RATIO_THRESHOLD
        or guj_ratio >= INDIAN_SCRIPT_RATIO_THRESHOLD
    ):
        return "hin" if hin_ratio >= guj_ratio else "guj"

    return "eng"


def _clean_text_for_language(text: str, lang_code: str) -> str:
    """Remove isolated stray characters from non-dominant scripts."""
    if lang_code == "eng":
        return text
    if lang_code == "hin":
        text = re.sub(r"(?<!\S)[\u0A80-\u0AFF](?!\S)", "", text)
    elif lang_code == "guj":
        text = re.sub(r"(?<!\S)[\u0900-\u097F](?!\S)", "", text)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _is_garbage_text(text: str) -> bool:
    """
    Heuristic to detect garbage embedded text in digital PDFs.
    Returns True if the text looks like bad OCR output embedded in the PDF.
    """
    if not text or len(text.strip()) < 20:
        return True

    # Count real word-like tokens (3+ alphanumeric chars)
    tokens = text.split()
    if not tokens:
        return True

    real_words = sum(
        1 for t in tokens if re.search(r"[a-zA-Z\u0900-\u097F\u0A80-\u0AFF]{3,}", t)
    )
    word_ratio = real_words / len(tokens)

    # Count non-alphanumeric characters
    alpha_chars = sum(1 for c in text if c.isalnum())
    total_chars = len(text.replace("\n", "").replace(" ", ""))
    symbol_ratio = 1 - (alpha_chars / total_chars) if total_chars > 0 else 1.0

    # Garbage if: less than 40% real words OR more than 35% symbols
    return word_ratio < 0.40 or symbol_ratio > 0.35


def _looks_like_business_document(text: str) -> bool:
    """Detect dense business-style text where PaddleOCR often helps."""
    stripped = (text or "").strip().lower()
    if not stripped:
        return False

    marker_patterns = [
        r"\binvoice\b",
        r"\btax invoice\b",
        r"\binvoice\s*(no|number)\b",
        r"\baccount statement\b",
        r"\bbank statement\b",
        r"\bdate\b",
        r"\btotal\b",
        r"\bamount\b",
        r"\bbalance\b",
        r"\bgst\b",
        r"\bsubtotal\b",
        r"\bqty\b",
    ]
    marker_hits = sum(1 for pattern in marker_patterns if re.search(pattern, stripped))
    number_hits = len(re.findall(r"\b\d[\d,./:-]{2,}\b", stripped))
    structured_lines = sum(
        1 for line in stripped.splitlines() if len(re.findall(r"\d", line)) >= 3
    )

    return marker_hits >= 2 or (marker_hits >= 1 and number_hits >= 4) or structured_lines >= 6


def _looks_like_marksheet(text: str) -> bool:
    """Avoid over-trusting business-document heuristics on academic records."""
    stripped = (text or "").strip().lower()
    if not stripped:
        return False

    marker_patterns = [
        r"\bmarksheet\b",
        r"\bmark sheet\b",
        r"\bsubject\b",
        r"\bgrade\b",
        r"\bsemester\b",
        r"\broll\s*(no|number)\b",
        r"\bresult\b",
        r"\btotal marks\b",
    ]
    marker_hits = sum(1 for pattern in marker_patterns if re.search(pattern, stripped))
    return marker_hits >= 2


# ── Singleton EasyOCR reader (lazy-loaded) ───────────────────────────────────
_easyocr_reader = None
_paddleocr_readers = {}


def _get_easyocr_reader():
    """Lazy-load EasyOCR reader (downloads models on first call, ~200MB)."""
    global _easyocr_reader
    if _easyocr_reader is None and HAS_EASYOCR:
        logger.info("Loading EasyOCR models (first time may take a moment)...")
        # 'en' = English, 'hi' = Hindi (Devanagari), 'gu' = Gujarati
        _easyocr_reader = easyocr.Reader(["en", "hi"], gpu=False, verbose=False)
        logger.info("EasyOCR models loaded.")
    return _easyocr_reader


def _get_paddleocr_reader(detected_lang: str):
    """
    Lazy-load PaddleOCR reader and cache by effective lang key.
    Uses a safe fallback sequence to avoid runtime breakage across versions.
    """
    if not HAS_PADDLEOCR:
        return None

    lang_candidates = {
        "eng": ["en"],
        "hin": ["hi", "devanagari", "en"],
    }.get(detected_lang, ["en"])

    for lang_key in lang_candidates:
        if lang_key in _paddleocr_readers:
            return _paddleocr_readers[lang_key]
        try:
            logger.info(f"Loading PaddleOCR model (lang={lang_key})...")
            reader = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang=lang_key,
            )
            _paddleocr_readers[lang_key] = reader
            logger.info(f"PaddleOCR model loaded (lang={lang_key}).")
            return reader
        except Exception as e:
            logger.warning(f"PaddleOCR init failed for lang={lang_key}: {e}")
            continue

    return None


class OCRExtractor(BaseExtractor):
    """
    Extracts text from scanned documents using a 2-tier OCR pipeline:
      Tier 1: Tesseract (fast, printed text)
      Tier 2: PaddleOCR/EasyOCR fallback for difficult low-confidence cases

    Also handles: rotation correction, aggressive enhancement for low quality,
    table extraction from images, per-page language detection.
    """

    def __init__(self):
        super().__init__()
        self.supported_extensions = {
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".bmp",
            ".webp",
        }
        self.ocr_available = HAS_OCR

        self.supported_languages = {
            "eng": "English",
            "hin": "Hindi",
            "guj": "Gujarati",
        }
        self.default_language = "eng"
        self._available_langs: list = []
        self._last_run_summary: Dict[str, Any] = {}
        self._last_run_source: Optional[str] = None
        self._active_quality_assessment: Dict[str, Any] = {}

        if not HAS_OCR:
            logger.warning("OCR dependencies not installed.")
            return

        try:
            pytesseract.get_tesseract_version()
            self._available_langs = self._get_available_languages()
            logger.info(
                f"Tesseract ready. Languages: {', '.join(self._available_langs)}"
            )
        except Exception:
            self.ocr_available = False
            logger.warning("Tesseract may not be installed correctly.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_available_languages(self) -> list:
        try:
            return pytesseract.get_languages()
        except Exception:
            return ["eng"]

    def _build_lang_string(self) -> str:
        """Always use all available Indian language packs together."""
        langs = ["eng"]
        for code in ["hin", "guj"]:
            if code in self._available_langs:
                langs.append(code)
        return "+".join(langs)

    def _build_targeted_lang_string(self, detected_lang: str) -> str:
        """
        Build a smaller language set from detected script to improve OCR precision
        and avoid unnecessary script confusion in uncertain cases.
        """
        langs = ["eng"]
        if detected_lang in {"hin", "guj"} and detected_lang in self._available_langs:
            langs.append(detected_lang)
        return "+".join(langs)

    def _should_try_aggressive_preprocessing(self, confidence: float, text: str) -> bool:
        """
        Trigger aggressive preprocessing only when low confidence is paired with
        weak/garbled text, not merely on confidence alone.
        Threshold raised to 65% so borderline-quality images always get the
        full CLAHE + shadow-removal + background-cleanup treatment.
        """
        _trigger_threshold = 65.0
        if confidence >= _trigger_threshold:
            return False
        stripped = (text or "").strip()
        if not stripped:
            return True
        if len(stripped) < 120:
            return True
        if _is_garbage_text(stripped):
            return True
        if confidence < 45.0:
            return True
        word_count = len(stripped.split())
        return word_count < 80 and len(stripped) < 500

    def _should_run_easyocr(self, confidence: float, text: str) -> bool:
        """
        Run EasyOCR only when it is likely to help. For long, moderately confident
        printed OCR output, EasyOCR is usually slower and lower quality.
        """
        if confidence >= EASYOCR_FALLBACK_THRESHOLD:
            return False
        stripped = (text or "").strip()
        text_len = len(stripped)
        if confidence >= 50.0 and text_len >= 500:
            return False
        if text_len >= 1000:
            return False
        return True

    def _should_run_paddleocr(self, confidence: float, text: str, detected_lang: str) -> bool:
        """
        PaddleOCR policy: keep it available for low-confidence recovery, and
        also try it on dense English business documents where it frequently
        recovers cleaner text than Tesseract.
        """
        if detected_lang == "guj":
            return False

        stripped = (text or "").strip()
        if not stripped:
            return True

        if self._should_run_easyocr(confidence, text):
            return True

        quality_assessment = self._active_quality_assessment or {}
        quality_score = float(quality_assessment.get("quality_score", 1.0) or 0.0)
        difficulty = quality_assessment.get("document_difficulty")

        if detected_lang == "eng" and _looks_like_business_document(stripped):
            return confidence < 96.0 or len(stripped) < 1500

        if difficulty == "hard" and len(stripped) < 450:
            return True

        if quality_score >= 0.8 and detected_lang == "eng" and len(stripped) < 500:
            return True

        return False

    def _score_ocr_candidate(
        self,
        text: str,
        confidence: float,
        detected_lang: str,
    ) -> float:
        """
        Score OCR output by usefulness, not only reported confidence.
        This helps compare outputs across different OCR engines.
        """
        stripped = (text or "").strip()
        if not stripped:
            return -1000.0

        text_len = len(stripped)
        tokens = re.findall(r"[A-Za-z0-9\u0900-\u097F\u0A80-\u0AFF]{2,}", stripped)
        token_count = len(tokens)
        digit_count = sum(1 for ch in stripped if ch.isdigit())
        line_count = max(1, len([line for line in stripped.splitlines() if line.strip()]))
        garbage_penalty = 18.0 if _is_garbage_text(stripped) else 0.0
        business_bonus = 6.0 if detected_lang == "eng" and _looks_like_business_document(stripped) else 0.0
        marksheet_penalty = 4.0 if detected_lang == "eng" and _looks_like_marksheet(stripped) else 0.0
        quality_assessment = self._active_quality_assessment or {}
        quality_score = float(quality_assessment.get("quality_score", 1.0) or 0.0)

        return (
            float(confidence)
            + min(text_len / 110.0, 12.0)
            + min(token_count / 45.0, 8.0)
            + min(digit_count / 35.0, 4.0)
            + min(line_count / 18.0, 3.0)
            + business_bonus
            - marksheet_penalty
            - garbage_penalty
            + max(0.0, (quality_score - 0.7) * 4.0)
        )

    def _should_replace_ocr_result(
        self,
        current_text: str,
        current_confidence: float,
        current_lang: str,
        candidate_text: str,
        candidate_confidence: float,
        candidate_lang: str,
    ) -> bool:
        """Choose the better OCR output using cross-engine heuristics."""
        if not (candidate_text or "").strip():
            return False
        if not (current_text or "").strip():
            return True

        current_score = self._score_ocr_candidate(
            current_text,
            current_confidence,
            current_lang,
        )
        candidate_score = self._score_ocr_candidate(
            candidate_text,
            candidate_confidence,
            candidate_lang,
        )

        if candidate_score >= current_score + 1.5:
            return True

        return (
            candidate_confidence >= current_confidence + 3.0
            and len(candidate_text.strip()) >= max(100, int(len(current_text.strip()) * 0.75))
        )

    def _should_try_layout_ocr(self, confidence: float, text: str) -> bool:
        """
        Run region-based OCR on hard pages where full-page OCR still looks weak.
        """
        if not HAS_CV2:
            return False
        if confidence >= LAYOUT_OCR_TRIGGER_CONFIDENCE:
            return False
        if confidence < 60.0:
            return True

        stripped = (text or "").strip()
        quality_assessment = self._active_quality_assessment or {}
        quality_score = float(quality_assessment.get("quality_score", 1.0) or 0.0)
        difficulty = quality_assessment.get("document_difficulty")
        quality_issues = set(quality_assessment.get("issues", []))

        if not stripped or len(stripped) < 180:
            return True
        if _is_garbage_text(stripped):
            return True
        if difficulty == "hard":
            return True
        if quality_score < 0.65:
            return True
        if {"blurry", "very_blurry", "skewed", "heavily_skewed", "low_text_density"} & quality_issues:
            return True
        return False

    def _merge_region_boxes(self, boxes: List[Tuple[int, int, int, int]]) -> List[Tuple[int, int, int, int]]:
        if not boxes:
            return []

        boxes = sorted(boxes, key=lambda box: (box[1], box[0]))
        merged = [boxes[0]]
        for x1, y1, x2, y2 in boxes[1:]:
            last_x1, last_y1, last_x2, last_y2 = merged[-1]
            overlaps_vertically = y1 <= last_y2 + 30 and y2 >= last_y1 - 30
            close_horizontally = x1 <= last_x2 + 40
            if overlaps_vertically and close_horizontally:
                merged[-1] = (
                    min(last_x1, x1),
                    min(last_y1, y1),
                    max(last_x2, x2),
                    max(last_y2, y2),
                )
            else:
                merged.append((x1, y1, x2, y2))
        return merged[:LAYOUT_OCR_MAX_REGIONS]

    def _extract_text_regions(self, image: "Image.Image") -> List[Tuple[int, int, int, int]]:
        """
        Detect likely text blocks for hard forms, tables, and mixed-layout scans.
        """
        if not HAS_CV2:
            return []

        gray = np.array(image.convert("L"))
        height, width = gray.shape
        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
        kernel_width = max(25, width // 28)
        kernel_height = max(7, height // 90)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, kernel_height))
        dilated = cv2.dilate(binary, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = max(5000, int(width * height * 0.003))
        raw_boxes: List[Tuple[int, int, int, int]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area < min_area:
                continue
            if w < width * 0.08 or h < 25:
                continue
            pad_x = max(12, int(w * 0.02))
            pad_y = max(12, int(h * 0.12))
            raw_boxes.append(
                (
                    max(0, x - pad_x),
                    max(0, y - pad_y),
                    min(width, x + w + pad_x),
                    min(height, y + h + pad_y),
                )
            )

        return self._merge_region_boxes(raw_boxes)

    def _select_region_psm(self, region_box: Tuple[int, int, int, int]) -> int:
        x1, y1, x2, y2 = region_box
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        aspect_ratio = width / height
        if aspect_ratio >= 4.0:
            return 6
        if aspect_ratio <= 1.1:
            return 11
        return 4

    def _run_layout_ocr(
        self,
        image: "Image.Image",
        current_text: str,
        current_confidence: float,
        lang_string: str,
    ) -> Tuple[str, float]:
        """
        OCR each detected text region separately and keep the combined result if it is better.
        """
        boxes = self._extract_text_regions(image)
        if len(boxes) < LAYOUT_OCR_MIN_REGIONS:
            return current_text, current_confidence

        logger.info(f"Trying layout OCR with {len(boxes)} text region(s)")

        region_texts: List[str] = []
        region_confidences: List[float] = []

        for box in boxes:
            crop = image.crop(box)
            crop = self._normalize_input_image(crop)
            crop = self._cap_large_image_for_ocr(crop)
            crop = self._enhance_image(
                crop,
                aggressive=True,
                enable_deskew=True,
                enable_shadow_removal=True,
            )
            psm = self._select_region_psm(box)
            text, confidence = self._ocr_with_config(crop, lang_string, psm)

            detected_lang = _detect_script_from_text(text)
            if self._should_run_paddleocr(confidence, text, detected_lang) and HAS_PADDLEOCR:
                paddle_text, paddle_conf = self._run_paddleocr(crop, detected_lang)
                paddle_lang = _detect_script_from_text(paddle_text)
                if self._should_replace_ocr_result(
                    text,
                    confidence,
                    detected_lang,
                    paddle_text,
                    paddle_conf,
                    paddle_lang,
                ):
                    text, confidence = paddle_text, paddle_conf
                    detected_lang = paddle_lang

            cleaned = (text or "").strip()
            if cleaned:
                region_texts.append(cleaned)
                region_confidences.append(confidence)

        if not region_texts:
            return current_text, current_confidence

        combined_text = "\n\n".join(region_texts)
        weighted_confidence = sum(region_confidences) / len(region_confidences)
        combined_lang = _detect_script_from_text(combined_text)
        if self._should_replace_ocr_result(
            current_text,
            current_confidence,
            _detect_script_from_text(current_text),
            combined_text,
            weighted_confidence,
            combined_lang,
        ):
            logger.info(
                f"Layout OCR improved result to confidence={weighted_confidence:.1f}% "
                f"with {len(combined_text)} chars"
            )
            return combined_text, weighted_confidence

        logger.info("Layout OCR did not improve results")
        return current_text, current_confidence

    def _should_try_targeted_language_retry(
        self,
        confidence: float,
        text: str,
        lang_string: str,
        targeted_lang_string: str,
    ) -> bool:
        """
        Targeted-language retry is useful for uncertain short outputs, but it is
        expensive on already-dense pages and rarely helps there.
        """
        if targeted_lang_string == lang_string:
            return False
        stripped = (text or "").strip()
        if len(stripped) < 80:
            return False
        if confidence >= TARGETED_LANG_RETRY_MAX_CONF:
            return False
        if confidence < 60.0 and len(stripped) >= 500 and not _is_garbage_text(stripped):
            return False
        return True

    def _should_try_psm_11(self, confidence: float, text: str) -> bool:
        """
        Only use sparse-text mode when the faster dense-text passes still look weak.
        """
        stripped = (text or "").strip()
        if (
            confidence >= HIGH_CONFIDENCE_EARLY_EXIT
            and len(stripped) >= MIN_TEXT_CHARS_FOR_EARLY_EXIT
        ):
            return False
        if not stripped:
            return True
        if len(stripped) < SPARSE_TEXT_RETRY_CHAR_THRESHOLD:
            return True
        if _is_garbage_text(stripped):
            return True
        return confidence < PSM_11_RETRY_CONFIDENCE_THRESHOLD

    def _get_aggressive_psm_candidates(self, best_psm: int, text: str) -> List[int]:
        """
        Limit aggressive retries to the current best PSM and one targeted alternative.
        """
        candidates = [best_psm]
        stripped = (text or "").strip()
        if len(stripped) < SPARSE_TEXT_RETRY_CHAR_THRESHOLD or _is_garbage_text(stripped):
            alternate = 11
        elif best_psm == 6:
            alternate = 3
        else:
            alternate = 6

        if alternate not in candidates:
            candidates.append(alternate)
        return candidates

    def _store_run_summary(self, file_path: Path, summary: Dict[str, Any]) -> None:
        """Cache the latest OCR summary so metadata extraction can reuse it."""
        self._last_run_source = str(file_path.resolve())
        self._last_run_summary = summary

    def _build_run_summary(
        self,
        *,
        extension: str,
        page_results: List[Dict[str, Any]],
        pdf_render_threads: Optional[int] = None,
        page_workers_used: int = 1,
    ) -> Dict[str, Any]:
        """Summarize OCR execution for downstream metrics and debugging."""
        confidences = [float(page["confidence"]) for page in page_results if page["confidence"] > 0]
        engine_usage: Dict[str, int] = {}
        language_usage: Dict[str, int] = {}
        page_timings: List[float] = []

        for page in page_results:
            engine_usage[page["engine"]] = engine_usage.get(page["engine"], 0) + 1
            language_usage[page["language"]] = language_usage.get(page["language"], 0) + 1
            page_timings.append(round(float(page["elapsed_seconds"]), 3))

        summary: Dict[str, Any] = {
            "num_pages": len(page_results),
            "ocr_run_summary": {
                "page_count": len(page_results),
                "average_page_confidence": round(sum(confidences) / len(confidences), 2)
                if confidences
                else 0.0,
                "engine_usage": engine_usage,
                "language_usage": language_usage,
                "page_processing_seconds": page_timings,
                "page_workers_used": page_workers_used,
            },
        }

        if extension == ".pdf":
            summary["ocr_run_summary"]["pdf_render_dpi"] = config.OCR_PDF_RENDER_DPI
            summary["ocr_run_summary"]["pdf_render_threads"] = pdf_render_threads or 1

        return summary

    def _cap_large_image_for_ocr(self, image: "Image.Image") -> "Image.Image":
        """
        Bound very large images before OCR so oversized RGBA inputs do not force
        Tesseract through needlessly expensive passes.
        """
        w, h = image.size
        pixels = w * h
        max_pixels = max(1, config.MAX_OCR_IMAGE_PIXELS)
        if pixels <= max_pixels:
            return image

        scale = (max_pixels / pixels) ** 0.5
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        logger.info(
            f"Capping OCR input size {w}×{h} -> {new_size[0]}×{new_size[1]} "
            f"(max_pixels={max_pixels})"
        )
        return image.resize(new_size, Image.LANCZOS)

    def _process_pdf_page(
        self,
        image: "Image.Image",
        page_num: int,
        total_pages: int,
    ) -> Dict[str, Any]:
        """Run OCR for a single PDF page and keep timing/engine diagnostics."""
        started = time.perf_counter()
        logger.info(f"OCR processing page {page_num}/{total_pages}")
        text, confidence, lang, engine = self.extract_text_from_image(image)
        return {
            "page_num": page_num,
            "text": text,
            "confidence": confidence,
            "language": lang,
            "engine": engine,
            "elapsed_seconds": time.perf_counter() - started,
        }

    def _normalize_input_image(self, image: "Image.Image") -> "Image.Image":
        """
        Universal normalisation — runs BEFORE auto-orient and enhance_image.

        Guarantees every image entering the OCR pipeline is:
          1. RGB (RGBA/P/L/palette → RGB with white background)
          2. Minimum MIN_SHORT_SIDE_PX on its short side (LANCZOS upscale)
          3. Not inverted (dark-bg white-text images are flipped)
          4. Contrast-normalised (extreme over/under-exposure corrected)

        This ensures that even 640×640, washed-out, or phone-photo images
        are readable before Tesseract OSD tries to detect orientation.
        """
        try:
            # ── 1. Colour mode normalisation ─────────────────────────────────
            if image.mode == "P":
                image = image.convert("RGBA")
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
                logger.debug("Normalisation: converted RGBA → RGB (white background)")
            elif image.mode == "L":
                image = image.convert("RGB")
                logger.debug("Normalisation: converted L → RGB")
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # ── 2. Minimum resolution guarantee ──────────────────────────────
            w, h = image.size
            short_side = min(w, h)
            if short_side < MIN_SHORT_SIDE_PX:
                scale = MIN_SHORT_SIDE_PX / short_side
                # Cap at 16MP to avoid memory issues
                max_scale = (MAX_ENHANCED_PIXELS / (w * h)) ** 0.5
                scale = min(scale, max_scale)
                if scale > 1.0:
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    logger.info(
                        f"Normalisation: upscaling {w}×{h} → {new_w}×{new_h} "
                        f"(short-side {short_side}px < {MIN_SHORT_SIDE_PX}px minimum)"
                    )
                    image = image.resize((new_w, new_h), Image.LANCZOS)

            # ── 3. Inversion detection (white-on-black → black-on-white) ─────
            if HAS_CV2:
                import numpy as np
                gray = np.array(image.convert("L"))
                mean_brightness = gray.mean()
                # If mean pixel < 100 → likely dark background, invert
                if mean_brightness < 100:
                    logger.info(
                        f"Normalisation: detected dark background (mean={mean_brightness:.0f}), "
                        "inverting image for OCR"
                    )
                    image = Image.fromarray(255 - np.array(image))

            # ── 4. Contrast normalisation ─────────────────────────────────────
            # If global std-dev is very low → washed-out/faded image → boost contrast
            if HAS_CV2:
                import numpy as np
                gray = np.array(image.convert("L"))
                std_dev = gray.std()
                if std_dev < 25:
                    logger.info(
                        f"Normalisation: very low contrast (std={std_dev:.1f}), "
                        "applying histogram equalisation"
                    )
                    equalized = cv2.equalizeHist(gray)
                    # Merge back to RGB
                    eq_rgb = cv2.cvtColor(equalized, cv2.COLOR_GRAY2RGB)
                    image = Image.fromarray(eq_rgb)
            else:
                # PIL fallback contrast boost for washed-out images
                from PIL import ImageStat
                stat = ImageStat.Stat(image.convert("L"))
                if stat.stddev[0] < 25:
                    enhancer = ImageEnhance.Contrast(image)
                    image = enhancer.enhance(3.0)
                    logger.info("Normalisation: PIL contrast boost applied (low contrast image)")

        except Exception as e:
            logger.warning(f"Input normalisation failed (using original): {e}")

        return image

    def _auto_orient_image(self, image: "Image.Image") -> "Image.Image":
        """
        Case 4: Auto-correct rotation using Tesseract OSD.
        Detects 0°, 90°, 180°, 270° rotation and corrects it.
        Note: call _normalize_input_image first so the image is large enough
        for OSD to work reliably.
        """
        try:
            osd_output = pytesseract.image_to_osd(
                image, config="--psm 0 -c min_characters_to_try=5"
            )
            # Parse "Rotate: 90" from OSD output
            match = re.search(r"Rotate:\s*(\d+)", osd_output)
            if match:
                angle = int(match.group(1))
                if angle != 0:
                    logger.info(f"OSD detected rotation: {angle}°. Auto-correcting.")
                    # PIL rotate: positive = counter-clockwise, so negate
                    image = image.rotate(-angle, expand=True)
        except Exception as e:
            # OSD can fail on low-text images — silently continue
            logger.debug(f"OSD orientation detection skipped: {e}")
        return image

    def _deskew_image(self, image: "Image.Image") -> "Image.Image":
        """
        Fine deskew using Hough Line Transform.
        Corrects small skew angles (1-15°) that OSD misses.
        Uses line detection to find dominant text angle.
        """
        if not HAS_CV2:
            return image

        try:
            import numpy as np

            gray = np.array(image.convert("L"))

            _, binary = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
            dilated = cv2.dilate(binary, kernel, iterations=1)

            edges = cv2.Canny(dilated, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=100,
                minLineLength=100,
                maxLineGap=10,
            )

            if lines is None or len(lines) < 5:
                return image

            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 - x1 != 0:
                    angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                    if abs(angle) < 45:
                        angles.append(angle)

            if not angles:
                return image

            median_angle = np.median(angles)

            if abs(median_angle) < 0.5:
                return image

            if abs(median_angle) > 15:
                logger.debug(
                    f"Skew angle {median_angle:.2f}° too large, skipping deskew"
                )
                return image

            logger.info(f"Deskewing image by {median_angle:.2f}°")

            (h, w) = gray.shape
            center = (w // 2, h // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)

            cos = np.abs(rotation_matrix[0, 0])
            sin = np.abs(rotation_matrix[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))

            rotation_matrix[0, 2] += (new_w / 2) - center[0]
            rotation_matrix[1, 2] += (new_h / 2) - center[1]

            rotated = cv2.warpAffine(
                np.array(image.convert("RGB")),
                rotation_matrix,
                (new_w, new_h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

            return Image.fromarray(rotated)

        except Exception as e:
            logger.debug(f"Deskew failed: {e}")
            return image

    def _remove_shadows(self, image: "Image.Image") -> "Image.Image":
        """
        Remove shadows from phone photos and scanned documents.
        Uses morphological operations to separate foreground from uneven background.
        """
        if not HAS_CV2:
            return image

        try:
            import numpy as np

            img_array = np.array(image.convert("RGB"))

            lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
            l_channel, a, b = cv2.split(lab)

            kernel_size = max(21, min(img_array.shape[:2]) // 20)
            if kernel_size % 2 == 0:
                kernel_size += 1

            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, (kernel_size, kernel_size)
            )

            background = cv2.morphologyEx(
                l_channel, cv2.MORPH_CLOSE, kernel, iterations=2
            )
            background = cv2.GaussianBlur(background, (kernel_size, kernel_size), 0)

            normalized = cv2.divide(l_channel, background, scale=255)

            lab_merged = cv2.merge([normalized, a, b])
            result = cv2.cvtColor(lab_merged, cv2.COLOR_LAB2RGB)

            logger.info("Shadow removal applied")
            return Image.fromarray(result)

        except Exception as e:
            logger.debug(f"Shadow removal failed: {e}")
            return image

    def _cleanup_background(self, image: "Image.Image") -> "Image.Image":
        """
        Remove background noise and artifacts.
        Uses adaptive thresholding and morphological cleaning.
        """
        if not HAS_CV2:
            return image

        try:
            import numpy as np

            gray = np.array(image.convert("L"))

            blur = cv2.GaussianBlur(gray, (3, 3), 0)

            thresh = cv2.adaptiveThreshold(
                blur,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=11,
                C=2,
            )

            kernel_small = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_small)

            kernel_close = np.ones((1, 3), np.uint8)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)

            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                cleaned, connectivity=8
            )

            sizes = stats[1:, -1]
            min_size = max(10, gray.size // 50000)

            mask = np.zeros(gray.shape, dtype=np.uint8)
            for i, size in enumerate(sizes):
                if size >= min_size:
                    mask[labels == i + 1] = 255

            result = cv2.bitwise_and(cleaned, cleaned, mask=mask)

            logger.info("Background cleanup applied")
            return Image.fromarray(result)

        except Exception as e:
            logger.debug(f"Background cleanup failed: {e}")
            return image

    def _detect_dpi(self, image: "Image.Image") -> int:
        """
        Detect approximate DPI of the image.
        Uses EXIF data if available, otherwise estimates from text density.
        """
        try:
            dpi = image.info.get("dpi", (72, 72))
            if isinstance(dpi, tuple):
                dpi = dpi[0]

            if dpi and dpi > 72:
                return dpi

            if HAS_CV2:
                import numpy as np

                gray = np.array(image.convert("L"))
                _, binary = cv2.threshold(
                    gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
                )

                contours, _ = cv2.findContours(
                    binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                if contours:
                    char_heights = []
                    for cnt in contours[:100]:
                        x, y, w, h = cv2.boundingRect(cnt)
                        if 5 < h < 100 and 2 < w < 100:
                            char_heights.append(h)

                    if char_heights:
                        avg_char_height = np.mean(char_heights)
                        if avg_char_height > 20:
                            estimated_dpi = int(72 * (12 / (avg_char_height / 2)))
                            return max(150, min(600, estimated_dpi))

            return 150

        except Exception as e:
            logger.debug(f"DPI detection failed: {e}")
            return 150

    def _enhance_image(
        self,
        image: "Image.Image",
        aggressive: bool = False,
        enable_deskew: bool = True,
        enable_shadow_removal: bool = True,
    ) -> "Image.Image":
        """
        Enhanced image preprocessing pipeline.

        Steps:
        1. RGBA → RGB conversion
        2. Fine deskew (Hough transform)
        3. Shadow removal (phone photos, scans)
        4. DPI detection + adaptive upscaling
        5. Background cleanup (aggressive mode)
        6. CLAHE + denoising + adaptive threshold
        """
        try:
            # Step 1: RGBA → RGB
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                if image.mode in ("RGBA", "LA"):
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
                logger.info("Converted RGBA/palette image to RGB")
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # Step 2: Fine deskew (Hough transform for 1-15° corrections)
            if enable_deskew and HAS_CV2:
                image = self._deskew_image(image)

            # Step 3: Shadow removal for phone photos/scans
            if enable_shadow_removal and HAS_CV2 and aggressive:
                image = self._remove_shadows(image)

            # Step 4: DPI detection + adaptive upscaling
            detected_dpi = self._detect_dpi(image)
            w, h = image.size
            min_dim = min(w, h)

            target_dpi = 300
            if detected_dpi < 150:
                target_dpi = 400
                aggressive = True
                logger.info(
                    f"Low DPI detected ({detected_dpi}), using aggressive enhancement"
                )

            scale = 1
            if min_dim < 1000:
                scale = max(2, 1500 // min_dim)
            elif detected_dpi < 150:
                scale = max(2, target_dpi // detected_dpi)

            if aggressive and min_dim < 1200 and scale < 2:
                scale = 2

            max_scale_by_pixels = int((MAX_ENHANCED_PIXELS / (w * h)) ** 0.5)
            max_scale_by_pixels = max(1, max_scale_by_pixels)
            if scale > max_scale_by_pixels:
                logger.info(
                    f"Capping upscale factor from {scale}x to {max_scale_by_pixels}x to keep preprocessing bounded"
                )
                scale = max_scale_by_pixels

            if scale > 1:
                new_w, new_h = w * scale, h * scale
                logger.info(
                    f"Upscaling {w}×{h} → {new_w}×{new_h} (scale={scale}×, DPI: {detected_dpi}→{target_dpi})"
                )
                image = image.resize((new_w, new_h), Image.LANCZOS)

            # Step 5: Background cleanup (aggressive mode)
            if aggressive and HAS_CV2:
                image = self._cleanup_background(image)

            # Step 6: Grayscale + CLAHE + threshold
            gray = image.convert("L")

            if HAS_CV2:
                img_array = np.array(gray)

                if aggressive:
                    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                    img_array = clahe.apply(img_array)

                    blurred = cv2.GaussianBlur(img_array, (0, 0), 3)
                    img_array = cv2.addWeighted(img_array, 1.5, blurred, -0.5, 0)

                    img_array = cv2.fastNlMeansDenoising(img_array, h=15)

                    thresh = cv2.adaptiveThreshold(
                        img_array,
                        255,
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY,
                        blockSize=15,
                        C=4,
                    )

                    kernel = np.ones((2, 2), np.uint8)
                    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
                else:
                    denoised = cv2.fastNlMeansDenoising(img_array, h=10)
                    thresh = cv2.adaptiveThreshold(
                        denoised,
                        255,
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY,
                        blockSize=15,
                        C=4,
                    )

                return Image.fromarray(thresh)
            else:
                if aggressive:
                    gray = gray.filter(
                        ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3)
                    )
                sharpened = gray.filter(ImageFilter.SHARPEN)
                enhancer = ImageEnhance.Contrast(sharpened)
                return enhancer.enhance(2.5 if aggressive else 2.0)

        except Exception as e:
            logger.warning(f"Image enhancement failed, using original: {e}")
            return image

    def _ocr_with_config(
        self, image: "Image.Image", lang_string: str, psm: int
    ) -> Tuple[str, float]:
        """Run Tesseract with a specific PSM and return (text, avg_confidence)."""
        try:
            config = f"--oem 3 --psm {psm}"
            text = pytesseract.image_to_string(
                image,
                lang=lang_string,
                config=config,
                timeout=TESSERACT_TIMEOUT_SEC,
            )
            data = pytesseract.image_to_data(
                image,
                lang=lang_string,
                output_type=pytesseract.Output.DICT,
                config=config,
                timeout=TESSERACT_TIMEOUT_SEC,
            )
            confs = [
                int(c)
                for c in data["conf"]
                if str(c).lstrip("-").isdigit() and int(c) > 0
            ]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            return text, avg_conf
        except RuntimeError as e:
            logger.warning(f"Tesseract timeout/error at PSM {psm}: {e}")
            return "", 0.0
        except Exception:
            return "", 0.0

    def _run_easyocr(self, image: "Image.Image") -> Tuple[str, float]:
        """
        Case 1 Tier 2: Run EasyOCR for handwriting / low confidence documents.
        Returns (text, avg_confidence_percent).
        """
        reader = _get_easyocr_reader()
        if reader is None:
            return "", 0.0

        try:
            import numpy as np

            # Bound EasyOCR runtime on large images.
            w, h = image.size
            pixels = w * h
            if pixels > EASYOCR_MAX_PIXELS:
                scale = (EASYOCR_MAX_PIXELS / pixels) ** 0.5
                new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                logger.info(
                    f"Downscaling for EasyOCR {w}x{h} -> {new_size[0]}x{new_size[1]}"
                )
                image = image.resize(new_size, Image.LANCZOS)

            img_array = np.array(image.convert("RGB"))
            results = reader.readtext(img_array, detail=1, paragraph=False)

            if not results:
                return "", 0.0

            lines = []
            confidences = []
            for _, text, conf in results:
                if text.strip():
                    lines.append(text.strip())
                    confidences.append(conf * 100)  # EasyOCR returns 0-1

            full_text = "\n".join(lines)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            logger.info(
                f"EasyOCR: extracted {len(full_text)} chars, confidence={avg_conf:.1f}%"
            )
            return full_text, avg_conf

        except Exception as e:
            log_error("EasyOCR", str(e))
            return "", 0.0

    def _run_paddleocr(self, image: "Image.Image", detected_lang: str) -> Tuple[str, float]:
        """
        Tier 2 fallback using PaddleOCR. Returns (text, avg_confidence_percent).
        """
        reader = _get_paddleocr_reader(detected_lang)
        if reader is None:
            return "", 0.0

        try:
            import numpy as np

            w, h = image.size
            pixels = w * h
            if pixels > EASYOCR_MAX_PIXELS:
                scale = (EASYOCR_MAX_PIXELS / pixels) ** 0.5
                new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                logger.info(
                    f"Downscaling for PaddleOCR {w}x{h} -> {new_size[0]}x{new_size[1]}"
                )
                image = image.resize(new_size, Image.LANCZOS)

            img_array = np.array(image.convert("RGB"))
            predict_method = getattr(reader, "predict", None)
            if callable(predict_method):
                results = predict_method(img_array)
            else:
                results = reader.ocr(img_array)
            if not results:
                return "", 0.0

            lines = []
            confidences = []
            for block in results:
                if not block:
                    continue

                if isinstance(block, dict):
                    texts = block.get("rec_texts") or []
                    scores = block.get("rec_scores") or []
                    for index, text in enumerate(texts):
                        cleaned = str(text).strip()
                        if not cleaned:
                            continue
                        lines.append(cleaned)
                        if index < len(scores):
                            try:
                                confidences.append(float(scores[index]) * 100.0)
                            except Exception:
                                pass
                    continue

                for item in block:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        continue
                    rec = item[1]
                    if not isinstance(rec, (list, tuple)) or len(rec) < 2:
                        continue
                    text = str(rec[0]).strip()
                    conf = rec[1]
                    if text:
                        lines.append(text)
                        try:
                            confidences.append(float(conf) * 100.0)
                        except Exception:
                            pass

            full_text = "\n".join(lines)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            logger.info(
                f"PaddleOCR: extracted {len(full_text)} chars, confidence={avg_conf:.1f}%"
            )
            return full_text, avg_conf

        except Exception as e:
            log_error("PaddleOCR", str(e))
            return "", 0.0

    def extract_tables_from_image(self, image: "Image.Image") -> List[Dict]:
        """
        Case 3: Extract tables from scanned images using img2table.
        Returns list of table dicts with headers and rows.
        """
        if not HAS_IMG2TABLE:
            return []

        try:
            import tempfile, os
            import numpy as np

            # Save image to temp file (img2table needs a file path)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
                image.save(tmp_path)

            try:
                doc = Img2TableImage(src=tmp_path, detect_rotation=False)
                ocr = TesseractOCR(
                    n_threads=1, lang=self._build_lang_string().replace("+", "-")
                )
                tables = doc.extract_tables(
                    ocr=ocr,
                    implicit_rows=True,
                    borderless_tables=True,
                    min_confidence=50,
                )

                result = []
                for table in tables:
                    df = table.df
                    if df is not None and not df.empty:
                        headers = list(df.columns)
                        rows = df.values.tolist()
                        result.append(
                            {
                                "headers": [str(h) for h in headers],
                                "rows": [
                                    [str(c) if c is not None else "" for c in row]
                                    for row in rows
                                ],
                            }
                        )

                logger.info(f"img2table found {len(result)} table(s) in image")
                return result

            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.warning(f"Table extraction from image failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def can_extract(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions

    def extract_text_from_image(
        self,
        image: "Image.Image",
    ) -> Tuple[str, float, str, str]:
        """
        Extract text from a single PIL image using 2-tier OCR pipeline.

        Preprocessing:
        1. Auto-orient (OSD for 0°/90°/180°/270°)
        2. Fine deskew (Hough transform for 1-15°)
        3. Shadow removal (aggressive mode)
        4. DPI detection + adaptive scaling
        5. Background cleanup (aggressive mode)

        OCR:
        Tier 1: Tesseract with adaptive PSM selection (PSM 3, 6, 11)
        Tier 2: EasyOCR fallback if confidence is low

        Returns:
            (text, avg_confidence_percent, detected_language_code, engine_used)
        """
        if not HAS_OCR:
            return "", 0.0, "eng", "none"

        try:
            # Step 0: Universal normalisation — must run FIRST
            # Guarantees: RGB, min 1200px short-side, correct polarity, baseline contrast
            image = self._normalize_input_image(image)
            image = self._cap_large_image_for_ocr(image)

            # Step 1: Auto-orient (fix rotated/upside-down scans)
            # OSD is now reliable because min resolution is guaranteed
            image = self._auto_orient_image(image)

            # Step 2: Normal enhancement (includes deskew, DPI detection)
            processed = self._enhance_image(
                image, aggressive=False, enable_deskew=True, enable_shadow_removal=False
            )

            lang_string = self._build_lang_string()
            logger.info(f"Tier 1 — Tesseract OCR with: {lang_string}")

            # Try dense-text modes first and only use sparse-text mode when
            # the faster passes still look uncertain.
            best_text, best_conf, best_psm = "", -1.0, 3
            for psm in [3, 6]:
                t, c = self._ocr_with_config(processed, lang_string, psm)
                logger.info(f"  PSM {psm}: conf={c:.1f}%, chars={len(t.strip())}")
                if c > best_conf:
                    best_conf, best_text, best_psm = c, t, psm
                if (
                    best_conf >= HIGH_CONFIDENCE_EARLY_EXIT
                    and len((best_text or "").strip()) >= MIN_TEXT_CHARS_FOR_EARLY_EXIT
                ):
                    logger.info(
                        f"Early-exit OCR at PSM {best_psm}: conf={best_conf:.1f}%"
                    )
                    break

            if self._should_try_psm_11(best_conf, best_text):
                t, c = self._ocr_with_config(processed, lang_string, 11)
                logger.info(f"  PSM 11: conf={c:.1f}%, chars={len(t.strip())}")
                if c > best_conf:
                    best_conf, best_text, best_psm = c, t, 11

            logger.info(f"Tier 1 best: PSM {best_psm}, confidence={best_conf:.1f}%")

            # Script-targeted retry for uncertain outputs (single extra pass)
            detected_from_t1 = _detect_script_from_text(best_text)
            targeted_lang_string = self._build_targeted_lang_string(detected_from_t1)
            if self._should_try_targeted_language_retry(
                best_conf,
                best_text,
                lang_string,
                targeted_lang_string,
            ):
                t_targeted, c_targeted = self._ocr_with_config(
                    processed, targeted_lang_string, best_psm
                )
                logger.info(
                    f"  Targeted retry ({targeted_lang_string}, PSM {best_psm}): conf={c_targeted:.1f}%, chars={len(t_targeted.strip())}"
                )
                if c_targeted > best_conf:
                    best_text, best_conf = t_targeted, c_targeted
                    logger.info(
                        f"Targeted language retry improved confidence to {best_conf:.1f}%"
                    )

            # Step 3: If still low confidence, try aggressive enhancement
            if self._should_try_aggressive_preprocessing(best_conf, best_text) and HAS_CV2:
                logger.info(
                    "Low confidence — trying aggressive preprocessing (deskew + shadow removal + cleanup)"
                )
                processed_agg = self._enhance_image(
                    image,
                    aggressive=True,
                    enable_deskew=True,
                    enable_shadow_removal=True,
                )
                for psm in self._get_aggressive_psm_candidates(best_psm, best_text):
                    t, c = self._ocr_with_config(processed_agg, lang_string, psm)
                    logger.info(
                        f"  Aggressive PSM {psm}: conf={c:.1f}%, chars={len(t.strip())}"
                    )
                    if c > best_conf:
                        best_conf, best_text, best_psm = c, t, psm
                logger.info(
                    f"After aggressive enhancement: confidence={best_conf:.1f}%"
                )

            engine_used = "tesseract"
            detected_lang = _detect_script_from_text(best_text)

            if self._should_try_layout_ocr(best_conf, best_text):
                layout_text, layout_conf = self._run_layout_ocr(
                    image,
                    best_text,
                    best_conf,
                    lang_string,
                )
                layout_lang = _detect_script_from_text(layout_text)
                if self._should_replace_ocr_result(
                    best_text,
                    best_conf,
                    detected_lang,
                    layout_text,
                    layout_conf,
                    layout_lang,
                ):
                    best_text = layout_text
                    best_conf = layout_conf
                    engine_used = "tesseract_layout"
                    detected_lang = layout_lang

            if self._should_run_paddleocr(best_conf, best_text, detected_lang) and HAS_PADDLEOCR:
                logger.info(
                    f"Trying PaddleOCR on {detected_lang} output at {best_conf:.1f}% confidence"
                )
                paddle_text, paddle_conf = self._run_paddleocr(image, detected_lang)
                paddle_lang = _detect_script_from_text(paddle_text)
                if self._should_replace_ocr_result(
                    best_text,
                    best_conf,
                    detected_lang,
                    paddle_text,
                    paddle_conf,
                    paddle_lang,
                ):
                    best_text = paddle_text
                    best_conf = paddle_conf
                    engine_used = "paddleocr"
                    detected_lang = paddle_lang
                    logger.info(f"PaddleOCR selected with confidence={paddle_conf:.1f}%")
                else:
                    logger.info("PaddleOCR did not improve results, keeping current output")

            # Tier 2: EasyOCR fallback
            if self._should_run_easyocr(best_conf, best_text) and HAS_EASYOCR:
                logger.info(
                    f"Confidence {best_conf:.1f}% < {EASYOCR_FALLBACK_THRESHOLD}% — switching to EasyOCR fallback"
                )
                easy_text, easy_conf = self._run_easyocr(image)
                easy_lang = _detect_script_from_text(easy_text)
                if self._should_replace_ocr_result(
                    best_text,
                    best_conf,
                    detected_lang,
                    easy_text,
                    easy_conf,
                    easy_lang,
                ):
                    best_text = easy_text
                    best_conf = easy_conf
                    engine_used = "easyocr"
                    detected_lang = easy_lang
                    logger.info(f"EasyOCR improved confidence to {easy_conf:.1f}%")
                else:
                    logger.info(
                        "EasyOCR did not improve results, keeping Tesseract output"
                    )
            elif (
                best_conf < EASYOCR_FALLBACK_THRESHOLD
                and HAS_EASYOCR
            ):
                logger.info(
                    f"Skipping OCR fallback at conf={best_conf:.1f}% (policy gate)"
                )

            # Detect language and clean output
            detected_lang = _detect_script_from_text(best_text)
            best_text = _clean_text_for_language(best_text, detected_lang)

            lang_display = self.supported_languages.get(detected_lang, detected_lang)
            logger.info(
                f"Detected language: {lang_display}, Engine: {engine_used}, Final confidence: {best_conf:.1f}%"
            )

            return best_text, best_conf, detected_lang, engine_used

        except Exception as e:
            log_error("OCRImageExtraction", str(e))
            return "", 0.0, "eng", "none"

    def extract_text(
        self,
        file_path: Path,
        language: Optional[str] = None,
        quality_assessment: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Extract text from a scanned document or image file.
        Language is always auto-detected per-page (Case 5).
        """
        if not HAS_OCR:
            raise ImportError("OCR dependencies not installed.")

        start_time = time.time()
        extension = file_path.suffix.lower()
        full_text = []
        self._active_quality_assessment = quality_assessment or {}

        try:
            if extension == ".pdf":
                logger.info(f"Converting scanned PDF to images: {file_path.name}")
                render_threads = max(1, config.OCR_PDF_RENDER_THREADS)
                images = convert_from_path(
                    str(file_path),
                    dpi=config.OCR_PDF_RENDER_DPI,
                    thread_count=render_threads,
                )
                logger.info(f"PDF has {len(images)} page(s)")
                total_pages = len(images)
                page_workers = max(1, min(config.OCR_PAGE_WORKERS, total_pages))

                if page_workers > 1 and total_pages > 1:
                    logger.info(
                        f"Parallel OCR enabled for {total_pages} PDF pages with {page_workers} workers"
                    )
                    with ThreadPoolExecutor(max_workers=page_workers) as executor:
                        page_results = list(
                            executor.map(
                                lambda args: self._process_pdf_page(args[0], args[1], total_pages),
                                [(image, page_num) for page_num, image in enumerate(images, 1)],
                            )
                        )
                else:
                    page_results = [
                        self._process_pdf_page(image, page_num, total_pages)
                        for page_num, image in enumerate(images, 1)
                    ]

                page_results.sort(key=lambda item: item["page_num"])
                for page in page_results:
                    lang_display = self.supported_languages.get(page["language"], page["language"])
                    if page["text"].strip():
                        full_text.append(
                            f"\n--- Page {page['page_num']} "
                            f"(Language: {lang_display}, "
                            f"OCR Confidence: {page['confidence']:.1f}%, "
                            f"Engine: {page['engine']}) ---\n"
                        )
                        full_text.append(page["text"])
                    else:
                        logger.warning(f"No text extracted from page {page['page_num']}")

                self._store_run_summary(
                    file_path,
                    self._build_run_summary(
                        extension=extension,
                        page_results=page_results,
                        pdf_render_threads=render_threads,
                        page_workers_used=page_workers,
                    ),
                )

            else:
                logger.info(f"OCR processing image: {file_path.name}")
                image = Image.open(file_path)
                text, confidence, lang, engine = self.extract_text_from_image(image)

                lang_display = self.supported_languages.get(lang, lang)
                full_text.append(
                    f"[Language: {lang_display}, OCR Confidence: {confidence:.1f}%, Engine: {engine}]\n"
                )
                full_text.append(text)
                self._store_run_summary(
                    file_path,
                    self._build_run_summary(
                        extension=extension,
                        page_results=[
                            {
                                "page_num": 1,
                                "text": text,
                                "confidence": confidence,
                                "language": lang,
                                "engine": engine,
                                "elapsed_seconds": time.time() - start_time,
                            }
                        ],
                        page_workers_used=1,
                    ),
                )

            result = "\n".join(full_text)
            extraction_time = time.time() - start_time
            log_extraction(file_path.name, len(result), extraction_time)
            return result

        except Exception as e:
            log_error("OCRExtraction", str(e), f"File: {file_path}")
            raise
        finally:
            self._active_quality_assessment = {}

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from scanned document."""
        try:
            metadata: Dict[str, Any] = {
                "extraction_method": "ocr",
                "ocr_engine": "tesseract+paddleocr+easyocr"
                if HAS_PADDLEOCR and HAS_EASYOCR
                else "tesseract+easyocr"
                if HAS_EASYOCR
                else "tesseract+paddleocr"
                if HAS_PADDLEOCR
                else "tesseract",
                "available_languages": self._available_langs,
                "easyocr_available": HAS_EASYOCR,
                "paddleocr_available": HAS_PADDLEOCR,
            }

            extension = file_path.suffix.lower()
            resolved_path = str(file_path.resolve())
            if self._last_run_source == resolved_path and self._last_run_summary:
                metadata.update(self._last_run_summary)
                if extension != ".pdf":
                    with Image.open(file_path) as img:
                        metadata["dimensions"] = img.size
                        metadata["mode"] = img.mode
                return metadata

            if extension == ".pdf":
                if HAS_PDFINFO:
                    info = pdfinfo_from_path(str(file_path))
                    metadata["num_pages"] = int(info.get("Pages", 0))
                else:
                    images = convert_from_path(str(file_path), dpi=72)
                    metadata["num_pages"] = len(images)
            else:
                with Image.open(file_path) as img:
                    metadata["num_pages"] = 1
                    metadata["dimensions"] = img.size
                    metadata["mode"] = img.mode

            return metadata

        except Exception as e:
            log_error("OCRMetadataExtraction", str(e), f"File: {file_path}")
            return {}

    def get_page_count(self, file_path: Path) -> int:
        try:
            if file_path.suffix.lower() == ".pdf":
                if HAS_PDFINFO:
                    info = pdfinfo_from_path(str(file_path))
                    return int(info.get("Pages", 0))
                images = convert_from_path(str(file_path), dpi=72)
                return len(images)
            return 1
        except Exception:
            return 1
