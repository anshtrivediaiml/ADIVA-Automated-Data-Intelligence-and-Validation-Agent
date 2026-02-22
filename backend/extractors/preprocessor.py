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
import pdfplumber
from logger import logger, log_error

# Optional dependencies
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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
    Preprocesses documents before extraction
    """
    
    def __init__(self):
        """Initialize the preprocessor"""
        self.supported_types = {'.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg', '.tiff'}
        logger.info("DocumentPreprocessor initialized")
    
    def detect_file_type(self, file_path: Path) -> str:
        """
        Detect the file type
        
        Args:
            file_path: Path to the file
            
        Returns:
            File type: 'pdf', 'docx', 'image', 'unknown'
        """
        try:
            extension = Path(file_path).suffix.lower()
            
            if extension == '.pdf':
                return 'pdf'
            elif extension in ['.docx', '.doc']:
                return 'docx'
            elif extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                return 'image'
            else:
                logger.warning(f"Unknown file type: {extension}")
                return 'unknown'
                
        except Exception as e:
            log_error("FileTypeDetection", str(e), f"File: {file_path}")
            return 'unknown'
    
    def is_scanned_pdf(self, file_path: Path) -> bool:
        """
        Determine if a PDF is scanned (image-based) or digital (text-based)
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            True if scanned, False if digital
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) == 0:
                    return False
                
                # Check first page
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                
                # If very little text extracted, likely scanned
                if not text or len(text.strip()) < 50:
                    logger.info(f"PDF appears to be scanned: {file_path.name}")
                    return True
                
                # Check if there are images covering most of the page
                images = first_page.images
                if len(images) > 0:
                    # If large images present and little text, likely scanned
                    if len(text.strip()) < 100:
                        logger.info(f"PDF has images with minimal text, likely scanned: {file_path.name}")
                        return True
                
                logger.info(f"PDF appears to be digital: {file_path.name}")
                return False
                
        except Exception as e:
            log_error("ScannedPDFDetection", str(e), f"File: {file_path}")
            # Default to digital if detection fails
            return False
    
    def assess_quality(self, file_path: Path) -> dict:
        """
        Assess document quality
        
        Args:
            file_path: Path to document
            
        Returns:
            Quality metrics dictionary
        """
        try:
            file_type = self.detect_file_type(file_path)
            quality = {
                'file_type': file_type,
                'file_size': os.path.getsize(file_path),
                'readable': True,
                'quality_score': 1.0,
                'issues': []
            }
            
            if file_type == 'pdf':
                # Case 6: Check for password protection FIRST
                if HAS_PIKEPDF:
                    try:
                        pikepdf.open(file_path)  # Will raise if password-protected
                    except pikepdf.PasswordError:
                        quality['readable'] = False
                        quality['quality_score'] = 0.0
                        quality['issues'].append('password_protected')
                        quality['error'] = 'Document is password protected. Please provide an unlocked version.'
                        logger.warning(f"Password-protected PDF: {file_path.name}")
                        return quality
                    except Exception:
                        pass  # Other pikepdf errors — continue with pdfplumber

                with pdfplumber.open(file_path) as pdf:
                    quality['num_pages'] = len(pdf.pages)
                    quality['is_scanned'] = self.is_scanned_pdf(file_path)
                    
                    # Check if encrypted
                    try:
                        if pdf.pages[0].extract_text() is None:
                            quality['issues'].append('Encrypted or corrupted')
                            quality['readable'] = False
                            quality['quality_score'] = 0.0
                    except:
                        quality['issues'].append('Error reading PDF')
                        quality['readable'] = False
                        quality['quality_score'] = 0.5
            
            elif file_type == 'docx':
                # Basic DOCX quality check
                quality['num_pages'] = 1  # Will be determined during extraction
            
            elif file_type == 'image':
                # Check image quality
                with Image.open(file_path) as img:
                    quality['dimensions'] = img.size
                    quality['mode'] = img.mode
                    
                    # Low resolution warning
                    if img.size[0] < 800 or img.size[1] < 600:
                        quality['issues'].append('Low resolution')
                        quality['quality_score'] = 0.6
            
            logger.info(f"Quality assessment complete: {file_path.name} - Score: {quality['quality_score']}")
            return quality
            
        except Exception as e:
            log_error("QualityAssessment", str(e), f"File: {file_path}")
            return {
                'file_type': 'unknown',
                'readable': False,
                'quality_score': 0.0,
                'issues': [str(e)]
            }
    
    def split_pages(self, file_path: Path) -> list:
        """
        Split document into individual pages
        
        Args:
            file_path: Path to document
            
        Returns:
            List of page objects/data
        """
        try:
            file_type = self.detect_file_type(file_path)
            pages = []
            
            if file_type == 'pdf':
                with pdfplumber.open(file_path) as pdf:
                    pages = [{'page_num': i+1, 'page': page} for i, page in enumerate(pdf.pages)]
                    logger.info(f"Split PDF into {len(pages)} pages")
            
            elif file_type == 'docx':
                # DOCX doesn't have clear page boundaries
                pages = [{'page_num': 1, 'type': 'docx'}]
            
            elif file_type == 'image':
                pages = [{'page_num': 1, 'type': 'image'}]
            
            return pages
            
        except Exception as e:
            log_error("PageSplitting", str(e), f"File: {file_path}")
            return []
    
    def analyze_layout(self, page_data: dict) -> dict:
        """
        Analyze page layout
        
        Args:
            page_data: Page object from split_pages
            
        Returns:
            Layout analysis results
        """
        try:
            layout = {
                'has_tables': False,
                'has_images': False,
                'columns': 1,
                'text_regions': 0
            }
            
            if 'page' in page_data:
                page = page_data['page']
                
                # Check for tables
                tables = page.extract_tables()
                if tables:
                    layout['has_tables'] = True
                    layout['num_tables'] = len(tables)
                
                # Check for images
                images = page.images
                if images:
                    layout['has_images'] = True
                    layout['num_images'] = len(images)
                
                # Simple column detection (basic heuristic)
                text = page.extract_text()
                if text:
                    # Count line breaks and width to estimate columns
                    lines = text.split('\n')
                    layout['text_regions'] = len(lines)
            
            return layout
            
        except Exception as e:
            log_error("LayoutAnalysis", str(e))
            return {'error': str(e)}
