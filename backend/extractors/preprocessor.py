"""
ADIVA - Document Preprocessor

This module handles document preprocessing and analysis:
- File type detection
- Quality assessment
- Scanned vs digital PDF detection
- Page splitting and layout analysis
"""

import os
from pathlib import Path
from typing import Optional

import pdfplumber

try:
    from logger import log_error, logger
except ModuleNotFoundError:
    from backend.logger import log_error, logger

try:
    from PIL import Image, ImageStat

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    import numpy as np

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import PyPDF2

    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import pikepdf

    HAS_PIKEPDF = True
except ImportError:
    HAS_PIKEPDF = False
    logger.info("pikepdf not installed. Password-protected PDF detection limited.")

try:
    import magic

    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


class DocumentPreprocessor:
    """
    Preprocesses documents before extraction.
    """

    def __init__(self):
        self.supported_types = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".tiff"}
        logger.info("DocumentPreprocessor initialized")

    def detect_file_type(self, file_path: Path) -> str:
        try:
            extension = Path(file_path).suffix.lower()
            if extension == ".pdf":
                return "pdf"
            if extension in [".docx", ".doc"]:
                return "docx"
            if extension in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                return "image"
            logger.warning(f"Unknown file type: {extension}")
            return "unknown"
        except Exception as exc:
            log_error("FileTypeDetection", str(exc), f"File: {file_path}")
            return "unknown"

    def is_scanned_pdf(self, file_path: Path) -> bool:
        try:
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) == 0:
                    return False

                first_page = pdf.pages[0]
                text = first_page.extract_text()

                if not text or len(text.strip()) < 50:
                    logger.info(f"PDF appears to be scanned: {file_path.name}")
                    return True

                images = first_page.images
                if images and len(text.strip()) < 100:
                    logger.info(
                        f"PDF has images with minimal text, likely scanned: {file_path.name}"
                    )
                    return True

                logger.info(f"PDF appears to be digital: {file_path.name}")
                return False
        except Exception as exc:
            log_error("ScannedPDFDetection", str(exc), f"File: {file_path}")
            return False

    def assess_quality(self, file_path: Path) -> dict:
        try:
            file_type = self.detect_file_type(file_path)
            quality = {
                "file_type": file_type,
                "file_size": os.path.getsize(file_path),
                "readable": True,
                "quality_score": 1.0,
                "issues": [],
            }

            if file_type == "pdf":
                if HAS_PIKEPDF:
                    try:
                        pikepdf.open(file_path)
                    except pikepdf.PasswordError:
                        quality["readable"] = False
                        quality["quality_score"] = 0.0
                        quality["issues"].append("password_protected")
                        quality["error"] = (
                            "Document is password protected. Please provide an unlocked version."
                        )
                        logger.warning(f"Password-protected PDF: {file_path.name}")
                        return quality
                    except Exception:
                        pass

                with pdfplumber.open(file_path) as pdf:
                    quality["num_pages"] = len(pdf.pages)
                    quality["is_scanned"] = self.is_scanned_pdf(file_path)

                    if quality["is_scanned"]:
                        quality["document_difficulty"] = "moderate"
                        quality["issues"].append("scanned_pdf")
                        quality["quality_score"] = 0.85

                    try:
                        first_page = pdf.pages[0]
                        first_page_text = first_page.extract_text() or ""
                        quality["first_page_text_length"] = len(first_page_text.strip())
                        if first_page_text.strip() == "" and not quality["is_scanned"]:
                            quality["issues"].append("empty_digital_text_layer")
                            quality["quality_score"] = min(quality["quality_score"], 0.6)
                    except Exception:
                        quality["issues"].append("error_reading_pdf")
                        quality["readable"] = False
                        quality["quality_score"] = 0.5

            elif file_type == "docx":
                quality["num_pages"] = 1
                quality["document_difficulty"] = "easy"

            elif file_type == "image":
                if not HAS_PIL:
                    raise RuntimeError("Pillow is required for image quality assessment")
                with Image.open(file_path) as img:
                    image_quality = self._analyze_image_quality(img)
                    quality.update(image_quality)

            logger.info(
                f"Quality assessment complete: {file_path.name} - "
                f"Score: {quality['quality_score']}"
            )
            return quality
        except Exception as exc:
            log_error("QualityAssessment", str(exc), f"File: {file_path}")
            return {
                "file_type": "unknown",
                "readable": False,
                "quality_score": 0.0,
                "issues": [str(exc)],
            }

    def split_pages(self, file_path: Path) -> list:
        try:
            file_type = self.detect_file_type(file_path)
            pages = []

            if file_type == "pdf":
                with pdfplumber.open(file_path) as pdf:
                    pages = [{"page_num": index + 1, "page": page} for index, page in enumerate(pdf.pages)]
                    logger.info(f"Split PDF into {len(pages)} pages")
            elif file_type == "docx":
                pages = [{"page_num": 1, "type": "docx"}]
            elif file_type == "image":
                pages = [{"page_num": 1, "type": "image"}]

            return pages
        except Exception as exc:
            log_error("PageSplitting", str(exc), f"File: {file_path}")
            return []

    def analyze_layout(self, page_data: dict) -> dict:
        try:
            layout = {
                "has_tables": False,
                "has_images": False,
                "columns": 1,
                "text_regions": 0,
            }

            if "page" in page_data:
                page = page_data["page"]

                tables = page.extract_tables()
                if tables:
                    layout["has_tables"] = True
                    layout["num_tables"] = len(tables)

                images = page.images
                if images:
                    layout["has_images"] = True
                    layout["num_images"] = len(images)

                text = page.extract_text()
                if text:
                    lines = text.split("\n")
                    layout["text_regions"] = len(lines)

            return layout
        except Exception as exc:
            log_error("LayoutAnalysis", str(exc))
            return {"error": str(exc)}

    def _analyze_image_quality(self, image: "Image.Image") -> dict:
        working_image = self._flatten_image(image)
        width, height = working_image.size

        grayscale = working_image.convert("L")
        stats = ImageStat.Stat(grayscale)
        brightness_mean = round(float(stats.mean[0]), 2)
        contrast_stddev = round(float(stats.stddev[0]), 2)

        quality_score = 1.0
        issues: list[str] = []
        metrics = {
            "brightness_mean": brightness_mean,
            "contrast_stddev": contrast_stddev,
            "blur_variance": None,
            "noise_score": None,
            "edge_density": None,
            "estimated_skew_degrees": None,
            "foreground_ratio": None,
            "has_alpha": image.mode in {"RGBA", "LA", "P"},
        }

        if width < 1000 or height < 700:
            issues.append("low_resolution")
            quality_score -= 0.16
        elif width < 1400 or height < 1000:
            issues.append("medium_resolution")
            quality_score -= 0.06

        if brightness_mean < 75:
            issues.append("underexposed")
            quality_score -= 0.12
        elif brightness_mean > 220:
            issues.append("overexposed")
            quality_score -= 0.08

        if contrast_stddev < 28:
            issues.append("very_low_contrast")
            quality_score -= 0.16
        elif contrast_stddev < 42:
            issues.append("low_contrast")
            quality_score -= 0.08

        if metrics["has_alpha"]:
            issues.append("transparent_background")
            quality_score -= 0.04

        if HAS_CV2:
            gray = np.array(grayscale)
            blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            denoised = cv2.GaussianBlur(gray, (3, 3), 0)
            noise_score = float(
                np.mean(np.abs(gray.astype("float32") - denoised.astype("float32")))
            )
            edges = cv2.Canny(gray, 100, 200)
            edge_density = float(np.count_nonzero(edges)) / float(edges.size)
            foreground_ratio = self._estimate_foreground_ratio(gray)
            skew_degrees = self._estimate_skew_degrees(gray)

            metrics.update(
                {
                    "blur_variance": round(blur_variance, 2),
                    "noise_score": round(noise_score, 2),
                    "edge_density": round(edge_density, 4),
                    "estimated_skew_degrees": round(skew_degrees, 2),
                    "foreground_ratio": round(foreground_ratio, 4),
                }
            )

            if blur_variance < 70:
                issues.append("very_blurry")
                quality_score -= 0.2
            elif blur_variance < 130:
                issues.append("blurry")
                quality_score -= 0.1

            if noise_score > 18:
                issues.append("noisy_background")
                quality_score -= 0.08

            if edge_density < 0.01:
                issues.append("very_low_text_density")
                quality_score -= 0.08
            elif edge_density < 0.018:
                issues.append("low_text_density")
                quality_score -= 0.04

            if abs(skew_degrees) > 6:
                issues.append("heavily_skewed")
                quality_score -= 0.12
            elif abs(skew_degrees) > 2.5:
                issues.append("skewed")
                quality_score -= 0.06

        quality_score = max(0.0, min(1.0, round(quality_score, 2)))
        difficulty = self._difficulty_from_score(quality_score, issues)

        return {
            "dimensions": working_image.size,
            "mode": image.mode,
            "quality_score": quality_score,
            "issues": issues,
            "quality_metrics": metrics,
            "document_difficulty": difficulty,
        }

    def _flatten_image(self, image: "Image.Image") -> "Image.Image":
        if image.mode == "P":
            image = image.convert("RGBA")

        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            return background

        if image.mode != "RGB":
            return image.convert("RGB")

        return image.copy()

    def _estimate_foreground_ratio(self, gray_image: "np.ndarray") -> float:
        _, binary = cv2.threshold(
            gray_image,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
        return float(np.count_nonzero(binary)) / float(binary.size)

    def _estimate_skew_degrees(self, gray_image: "np.ndarray") -> float:
        edges = cv2.Canny(gray_image, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=100,
            minLineLength=max(40, gray_image.shape[1] // 8),
            maxLineGap=20,
        )
        if lines is None:
            return 0.0

        angles = []
        for group in lines[:60]:
            line = group[0]
            x1, y1, x2, y2 = line
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if -20 <= angle <= 20:
                angles.append(angle)

        if not angles:
            return 0.0

        return float(np.median(angles))

    def _difficulty_from_score(self, quality_score: float, issues: list[str]) -> str:
        if quality_score < 0.45:
            return "hard"
        if quality_score < 0.72 or len(issues) >= 3:
            return "moderate"
        return "easy"
