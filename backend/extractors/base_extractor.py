"""
ADIVA - Base Extractor Class

Abstract base class that all document extractors inherit from.
Defines the common interface for all extractors.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any
from logger import logger


class BaseExtractor(ABC):
    """
    Abstract base class for all document extractors
    """
    
    def __init__(self):
        """Initialize the extractor"""
        self.name = self.__class__.__name__
        logger.info(f"{self.name} initialized")
    
    @abstractmethod
    def can_extract(self, file_path: Path) -> bool:
        """
        Check if this extractor can handle the given file
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if this extractor can handle the file
        """
        pass
    
    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """
        Extract raw text from the document
        
        Args:
            file_path: Path to the document
            
        Returns:
            Extracted text content
        """
        pass
    
    @abstractmethod
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from the document
        
        Args:
            file_path: Path to the document
            
        Returns:
            Dictionary of metadata
        """
        pass
    
    def extract_tables(self, file_path: Path) -> list:
        """
        Extract tables from the document (optional, can be overridden)
        
        Args:
            file_path: Path to the document
            
        Returns:
            List of tables
        """
        return []
    
    def extract_images(self, file_path: Path) -> list:
        """
        Extract images from the document (optional, can be overridden)
        
        Args:
            file_path: Path to the document
            
        Returns:
            List of image data
        """
        return []
    
    def get_page_count(self, file_path: Path) -> int:
        """
        Get the number of pages in the document
        
        Args:
            file_path: Path to the document
            
        Returns:
            Number of pages
        """
        return 1
