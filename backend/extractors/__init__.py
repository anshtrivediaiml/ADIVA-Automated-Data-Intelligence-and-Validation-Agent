"""
ADIVA - Extractors Package

This package contains all document extractors.
"""

from extractors.base_extractor import BaseExtractor
from extractors.pdf_extractor import PDFExtractor
from extractors.docx_extractor import DOCXExtractor
from extractors.ocr_extractor import OCRExtractor
from extractors.preprocessor import DocumentPreprocessor

__all__ = [
    'BaseExtractor',
    'PDFExtractor',
    'DOCXExtractor',
    'OCRExtractor',
    'DocumentPreprocessor'
]

