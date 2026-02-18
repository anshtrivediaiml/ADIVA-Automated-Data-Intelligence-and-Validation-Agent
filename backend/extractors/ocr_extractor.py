"""
ADIVA - OCR Extractor (Scanned Documents)

Extracts text from scanned PDFs and images using Tesseract OCR.
"""

from pathlib import Path
from typing import Dict, Any
import platform # Added for platform detection
from extractors.base_extractor import BaseExtractor
from logger import logger, log_extraction, log_error
import time

# Optional OCR dependencies
try:
    import pytesseract
    # Configure Tesseract path for Windows
    if platform.system() == 'Windows':
        # Set Tesseract executable path
        # IMPORTANT: Update this path to your Tesseract installation directory
        # Example: r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        # Or for common user appdata install: r'C:\Users\YOUR_USERNAME\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        pytesseract.pytesseract.tesseract_cmd = r'C:\Users\AnshTrivedi\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    
    from pdf2image import convert_from_path
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    logger.warning("OCR dependencies not available. Install pytesseract and pdf2image for OCR support.")

# Optional language detection
try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    logger.info("Language detection not available. Install with: pip install langdetect")



class OCRExtractor(BaseExtractor):
    """
    Extracts text from scanned documents using OCR
    """
    
    def __init__(self):
        """Initialize OCR extractor"""
        super().__init__()
        self.supported_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'}
        self.ocr_available = HAS_OCR
        
        # Multi-language support
        self.supported_languages = {
            'eng': 'English',
            'hin': 'Hindi',
            'guj': 'Gujarati'
        }
        self.default_language = 'eng'
        
        if not HAS_OCR:
            logger.warning("OCR dependencies not installed. OCR extraction will not work.")
            logger.warning("To enable OCR: pip install pytesseract pdf2image")
            return
        
        # Try to verify Tesseract is installed
        try:
            pytesseract.get_tesseract_version()
            logger.info("Tesseract OCR is available")
            
            # Check available languages
            available_langs = self._get_available_languages()
            logger.info(f"Available OCR languages: {', '.join(available_langs)}")
            
            # Warn if Hindi or Gujarati not available
            if 'hin' not in available_langs:
                logger.warning("Hindi language pack not installed. Install with: see LANGUAGE_SETUP.md")
            if 'guj' not in available_langs:
                logger.warning("Gujarati language pack not installed. Install with: see LANGUAGE_SETUP.md")
                
        except:
            self.ocr_available = False
            logger.warning("Tesseract OCR may not be installed. OCR functionality may not work.")
    
    def _get_available_languages(self) -> list:
        """Get list of available Tesseract languages"""
        try:
            langs = pytesseract.get_languages()
            return langs
        except:
            return ['eng']  # Default to English


    
    def can_extract(self, file_path: Path) -> bool:
        """Check if this can extract from the file"""
        return file_path.suffix.lower() in self.supported_extensions
    
    def _detect_language(self, sample_text: str) -> str:
        """
        Detect language from sample text
        
        Args:
            sample_text: Text sample for detection
            
        Returns:
            Language code (eng, hin, guj)
        """
        if not sample_text or not HAS_LANGDETECT:
            return self.default_language
        
        try:
            detected = detect(sample_text)
            
            # Map detected language to Tesseract codes
            lang_map = {
                'en': 'eng',
                'hi': 'hin',
                'gu': 'guj'
            }
            
            return lang_map.get(detected, self.default_language)
        except:
            return self.default_language
    
    def extract_text_from_image(self, image, language: str = None) -> tuple:
        """
        Extract text from a single image using OCR
        
        Args:
            image: PIL Image object
            language: Language code (eng, hin, guj) or None for auto-detect
            
        Returns:
            Tuple of (text, confidence_data, detected_language)
        """
        if not HAS_OCR:
            return "", 0, 'eng'
        
        try:
            # First pass with English to detect language if not specified
            if language is None:
                initial_text = pytesseract.image_to_string(image, lang='eng')
                language = self._detect_language(initial_text)
                logger.info(f"Detected language: {self.supported_languages.get(language, language)}")
            
            # Extract text with detected/specified language
            # Try multiple languages if available
            lang_string = language
            if language in ['hin', 'guj']:
                # Use combination: language+eng for better results
                lang_string = f"{language}+eng"
            
            text = pytesseract.image_to_string(image, lang=lang_string)
            
            # Get detailed confidence data
            try:
                data = pytesseract.image_to_data(image, lang=lang_string, output_type=pytesseract.Output.DICT)
                # Calculate average confidence
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            except:
                avg_confidence = 0
            
            return text, avg_confidence, language
            
        except Exception as e:
            log_error("OCRImageExtraction", str(e))
            return "", 0, 'eng'
    
    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from scanned document or image
        
        Args:
            file_path: Path to scanned document
            
        Returns:
            Extracted text
        """
        if not HAS_OCR:
            raise ImportError("OCR dependencies not installed. Install: pip install pytesseract pdf2image Pillow")
        
        start_time = time.time()
        
        try:
            extension = file_path.suffix.lower()
            full_text = []
            
            if extension == '.pdf':
                # Convert PDF pages to images
                logger.info(f"Converting PDF to images for OCR: {file_path.name}")
                images = convert_from_path(file_path)
                
                detected_lang = None
                for page_num, image in enumerate(images, 1):
                    logger.info(f"Processing page {page_num}/{len(images)} with OCR")
                    text, confidence, lang = self.extract_text_from_image(image, language=detected_lang)
                    
                    # Use same language for subsequent pages
                    if detected_lang is None:
                        detected_lang = lang
                    
                    if text.strip():
                        full_text.append(f"\n--- Page {page_num} (Language: {self.supported_languages.get(lang, lang)}, OCR Confidence: {confidence:.1f}%) ---\n")
                        full_text.append(text)
                    else:
                        logger.warning(f"No text extracted from page {page_num}")
            
            else:
                # Single image file
                logger.info(f"Processing image with OCR: {file_path.name}")
                image = Image.open(file_path)
                text, confidence, lang = self.extract_text_from_image(image)
                
                full_text.append(f"[Language: {self.supported_languages.get(lang, lang)}, OCR Confidence: {confidence:.1f}%]\n")
                full_text.append(text)
            
            result = "\n".join(full_text)
            
            # Log extraction
            extraction_time = time.time() - start_time
            log_extraction(file_path.name, len(result), extraction_time)
            
            return result
            
        except Exception as e:
            log_error("OCRExtraction", str(e), f"File: {file_path}")
            raise
    
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from scanned document
        
        Args:
            file_path: Path to scanned document
            
        Returns:
            Metadata dictionary
        """
        try:
            metadata = {
                'extraction_method': 'ocr',
                'ocr_engine': 'tesseract'
            }
            
            extension = file_path.suffix.lower()
            
            if extension == '.pdf':
                # Get page count
                images = convert_from_path(file_path)
                metadata['num_pages'] = len(images)
            else:
                # Image file
                with Image.open(file_path) as img:
                    metadata['num_pages'] = 1
                    metadata['dimensions'] = img.size
                    metadata['mode'] = img.mode
            
            return metadata
            
        except Exception as e:
            log_error("OCRMetadataExtraction", str(e), f"File: {file_path}")
            return {}
    
    def get_page_count(self, file_path: Path) -> int:
        """Get number of pages"""
        try:
            extension = file_path.suffix.lower()
            if extension == '.pdf':
                images = convert_from_path(file_path)
                return len(images)
            else:
                return 1
        except:
            return 1
