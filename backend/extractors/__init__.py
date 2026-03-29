"""
ADIVA - Extractors Package

This package contains all document extractors.
"""

try:
    from extractors.base_extractor import BaseExtractor
    from extractors.pdf_extractor import PDFExtractor
    from extractors.docx_extractor import DOCXExtractor
    from extractors.ocr_extractor import OCRExtractor
    from extractors.preprocessor import DocumentPreprocessor
except ModuleNotFoundError:
    from backend.extractors.base_extractor import BaseExtractor
    from backend.extractors.pdf_extractor import PDFExtractor
    from backend.extractors.docx_extractor import DOCXExtractor
    from backend.extractors.ocr_extractor import OCRExtractor
    from backend.extractors.preprocessor import DocumentPreprocessor

__all__ = [
    'BaseExtractor',
    'PDFExtractor',
    'DOCXExtractor',
    'OCRExtractor',
    'DocumentPreprocessor'
]

