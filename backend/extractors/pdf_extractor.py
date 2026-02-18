"""
ADIVA - PDF Extractor (Digital PDFs)

Extracts text and structured data from digital (text-based) PDF files.
"""

from pathlib import Path
from typing import Dict, Any
import pdfplumber
from extractors.base_extractor import BaseExtractor
from logger import logger, log_extraction, log_error
import time


class PDFExtractor(BaseExtractor):
    """
    Extracts content from digital PDF files using pdfplumber
    """
    
    def __init__(self):
        """Initialize PDF extractor"""
        super().__init__()
        self.supported_extensions = {'.pdf'}
    
    def can_extract(self, file_path: Path) -> bool:
        """Check if this can extract from the file"""
        return file_path.suffix.lower() in self.supported_extensions
    
    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from PDF
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        start_time = time.time()
        
        try:
            full_text = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text from page
                    text = page.extract_text()
                    
                    if text:
                        # Add page marker
                        full_text.append(f"\n--- Page {page_num} ---\n")
                        full_text.append(text)
                    else:
                        logger.warning(f"No text found on page {page_num} of {file_path.name}")
            
            result = "\n".join(full_text)
            
            # Log extraction
            extraction_time = time.time() - start_time
            log_extraction(file_path.name, len(result), extraction_time)
            
            return result
            
        except Exception as e:
            log_error("PDFExtraction", str(e), f"File: {file_path}")
            raise
    
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from PDF
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Metadata dictionary
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata = {
                    'num_pages': len(pdf.pages),
                    'pdf_metadata': pdf.metadata or {},
                }
                
                # Add first page dimensions
                if pdf.pages:
                    first_page = pdf.pages[0]
                    metadata['page_width'] = first_page.width
                    metadata['page_height'] = first_page.height
                
                return metadata
                
        except Exception as e:
            log_error("PDFMetadataExtraction", str(e), f"File: {file_path}")
            return {}
    
    def extract_tables(self, file_path: Path) -> list:
        """
        Extract tables from PDF
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of tables (each table is a list of rows)
        """
        try:
            all_tables = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract tables from page
                    tables = page.extract_tables()
                    
                    for table_num, table in enumerate(tables, 1):
                        # Convert table to list of dicts
                        if table and len(table) > 1:
                            headers = table[0]
                            rows = table[1:]
                            
                            table_data = {
                                'page': page_num,
                                'table_num': table_num,
                                'headers': headers,
                                'rows': rows,
                                'data': []
                            }
                            
                            # Convert to list of dictionaries
                            for row in rows:
                                if len(row) == len(headers):
                                    row_dict = {headers[i]: row[i] for i in range(len(headers))}
                                    table_data['data'].append(row_dict)
                            
                            all_tables.append(table_data)
                            logger.info(f"Extracted table {table_num} from page {page_num}: {len(rows)} rows")
            
            return all_tables
            
        except Exception as e:
            log_error("PDFTableExtraction", str(e), f"File: {file_path}")
            return []
    
    def get_page_count(self, file_path: Path) -> int:
        """Get number of pages in PDF"""
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except:
            return 0
