"""
ADIVA - OCR Extractor (Scanned Documents)

Extracts text from scanned PDFs and images using Tesseract OCR with
EasyOCR fallback for handwritten documents.

Handles:
- Printed documents (Tesseract, fast)
- Handwritten documents (EasyOCR fallback when confidence < 60%)
- Low quality scans (aggressive CLAHE + morphological enhancement)
- Rotated/upside-down scans (Tesseract OSD auto-correction)
- Tables in scanned images (img2table)
- Multi-page PDFs with per-page language detection
- English, Hindi (Devanagari), Gujarati scripts
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import platform
import re
import unicodedata
from extractors.base_extractor import BaseExtractor
from logger import logger, log_extraction, log_error
import time

# ── Core OCR dependencies ────────────────────────────────────────────────────
try:
    import pytesseract

    if platform.system() == "Windows":
        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Users\AnshTrivedi\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        )
    from pdf2image import convert_from_path
    from PIL import Image, ImageFilter, ImageEnhance

    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    logger.warning("OCR dependencies not available. Install pytesseract and pdf2image.")

# ── OpenCV for advanced preprocessing ───────────────────────────────────────
try:
    import cv2
    import numpy as np

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    logger.info("OpenCV not available. Basic PIL preprocessing will be used.")

# ── EasyOCR for handwriting fallback ────────────────────────────────────────
try:
    import easyocr

    HAS_EASYOCR = True
    logger.info("EasyOCR available for handwriting fallback.")
except ImportError:
    HAS_EASYOCR = False
    logger.info("EasyOCR not installed. Handwriting fallback disabled.")

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


# ── Singleton EasyOCR reader (lazy-loaded) ───────────────────────────────────
_easyocr_reader = None


def _get_easyocr_reader():
    """Lazy-load EasyOCR reader (downloads models on first call, ~200MB)."""
    global _easyocr_reader
    if _easyocr_reader is None and HAS_EASYOCR:
        logger.info("Loading EasyOCR models (first time may take a moment)...")
        # 'en' = English, 'hi' = Hindi (Devanagari), 'gu' = Gujarati
        _easyocr_reader = easyocr.Reader(["en", "hi"], gpu=False, verbose=False)
        logger.info("EasyOCR models loaded.")
    return _easyocr_reader


class OCRExtractor(BaseExtractor):
    """
    Extracts text from scanned documents using a 2-tier OCR pipeline:
      Tier 1: Tesseract (fast, printed text)
      Tier 2: EasyOCR (deep learning, handwriting fallback)

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

    def _auto_orient_image(self, image: "Image.Image") -> "Image.Image":
        """
        Case 4: Auto-correct rotation using Tesseract OSD.
        Detects 0°, 90°, 180°, 270° rotation and corrects it.
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

            if aggressive and scale < 3:
                scale = max(scale, 3)

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
            text = pytesseract.image_to_string(image, lang=lang_string, config=config)
            data = pytesseract.image_to_data(
                image,
                lang=lang_string,
                output_type=pytesseract.Output.DICT,
                config=config,
            )
            confs = [
                int(c)
                for c in data["conf"]
                if str(c).lstrip("-").isdigit() and int(c) > 0
            ]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            return text, avg_conf
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
        Tier 2: EasyOCR if Tesseract confidence < 60% (handles handwriting)

        Returns:
            (text, avg_confidence_percent, detected_language_code, engine_used)
        """
        if not HAS_OCR:
            return "", 0.0, "eng", "none"

        try:
            # Step 1: Auto-orient (fix rotated/upside-down scans)
            image = self._auto_orient_image(image)

            # Step 2: Normal enhancement (includes deskew, DPI detection)
            processed = self._enhance_image(
                image, aggressive=False, enable_deskew=True, enable_shadow_removal=False
            )

            lang_string = self._build_lang_string()
            logger.info(f"Tier 1 — Tesseract OCR with: {lang_string}")

            # Adaptive PSM: try 3, 6, 11 — pick highest confidence
            best_text, best_conf, best_psm = "", -1.0, 3
            for psm in [3, 6, 11]:
                t, c = self._ocr_with_config(processed, lang_string, psm)
                logger.info(f"  PSM {psm}: conf={c:.1f}%, chars={len(t.strip())}")
                if c > best_conf:
                    best_conf, best_text, best_psm = c, t, psm

            logger.info(f"Tier 1 best: PSM {best_psm}, confidence={best_conf:.1f}%")

            # Step 3: If still low confidence, try aggressive enhancement
            if best_conf < EASYOCR_FALLBACK_THRESHOLD and HAS_CV2:
                logger.info(
                    "Low confidence — trying aggressive preprocessing (deskew + shadow removal + cleanup)"
                )
                processed_agg = self._enhance_image(
                    image,
                    aggressive=True,
                    enable_deskew=True,
                    enable_shadow_removal=True,
                )
                for psm in [3, 6, 11]:
                    t, c = self._ocr_with_config(processed_agg, lang_string, psm)
                    if c > best_conf:
                        best_conf, best_text, best_psm = c, t, psm
                logger.info(
                    f"After aggressive enhancement: confidence={best_conf:.1f}%"
                )

            engine_used = "tesseract"

            # Tier 2: EasyOCR fallback for handwriting
            if best_conf < EASYOCR_FALLBACK_THRESHOLD and HAS_EASYOCR:
                logger.info(
                    f"Confidence {best_conf:.1f}% < {EASYOCR_FALLBACK_THRESHOLD}% — switching to EasyOCR (handwriting mode)"
                )
                easy_text, easy_conf = self._run_easyocr(image)
                if easy_conf > best_conf and easy_text.strip():
                    best_text = easy_text
                    best_conf = easy_conf
                    engine_used = "easyocr"
                    logger.info(f"EasyOCR improved confidence to {easy_conf:.1f}%")
                else:
                    logger.info(
                        "EasyOCR did not improve results, keeping Tesseract output"
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

    def extract_text(self, file_path: Path, language: Optional[str] = None) -> str:
        """
        Extract text from a scanned document or image file.
        Language is always auto-detected per-page (Case 5).
        """
        if not HAS_OCR:
            raise ImportError("OCR dependencies not installed.")

        start_time = time.time()
        extension = file_path.suffix.lower()
        full_text = []

        try:
            if extension == ".pdf":
                logger.info(f"Converting scanned PDF to images: {file_path.name}")
                images = convert_from_path(str(file_path), dpi=300)
                logger.info(f"PDF has {len(images)} page(s)")

                for page_num, image in enumerate(images, 1):
                    logger.info(f"OCR processing page {page_num}/{len(images)}")
                    # Case 5: Detect language independently per page (no lock)
                    text, confidence, lang, engine = self.extract_text_from_image(image)

                    lang_display = self.supported_languages.get(lang, lang)
                    if text.strip():
                        full_text.append(
                            f"\n--- Page {page_num} "
                            f"(Language: {lang_display}, "
                            f"OCR Confidence: {confidence:.1f}%, "
                            f"Engine: {engine}) ---\n"
                        )
                        full_text.append(text)
                    else:
                        logger.warning(f"No text extracted from page {page_num}")

            else:
                logger.info(f"OCR processing image: {file_path.name}")
                image = Image.open(file_path)
                text, confidence, lang, engine = self.extract_text_from_image(image)

                lang_display = self.supported_languages.get(lang, lang)
                full_text.append(
                    f"[Language: {lang_display}, OCR Confidence: {confidence:.1f}%, Engine: {engine}]\n"
                )
                full_text.append(text)

            result = "\n".join(full_text)
            extraction_time = time.time() - start_time
            log_extraction(file_path.name, len(result), extraction_time)
            return result

        except Exception as e:
            log_error("OCRExtraction", str(e), f"File: {file_path}")
            raise

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract metadata from scanned document."""
        try:
            metadata: Dict[str, Any] = {
                "extraction_method": "ocr",
                "ocr_engine": "tesseract+easyocr" if HAS_EASYOCR else "tesseract",
                "available_languages": self._available_langs,
                "easyocr_available": HAS_EASYOCR,
                "img2table_available": HAS_IMG2TABLE,
            }

            extension = file_path.suffix.lower()
            if extension == ".pdf":
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
                images = convert_from_path(str(file_path), dpi=72)
                return len(images)
            return 1
        except Exception:
            return 1
