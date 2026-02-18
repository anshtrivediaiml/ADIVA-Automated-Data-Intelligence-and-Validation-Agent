"""
ADIVA - DOCX Extractor

Extracts text and structured data from Microsoft Word (.docx) files.
"""

from pathlib import Path
from typing import Dict, Any
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from extractors.base_extractor import BaseExtractor
from logger import logger, log_extraction, log_error
import time


class DOCXExtractor(BaseExtractor):
    """
    Extracts content from DOCX files using python-docx
    """
    
    def __init__(self):
        """Initialize DOCX extractor"""
        super().__init__()
        self.supported_extensions = {'.docx'}
    
    def can_extract(self, file_path: Path) -> bool:
        """Check if this can extract from the file"""
        return file_path.suffix.lower() in self.supported_extensions
    
    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from DOCX
        
        Args:
            file_path: Path to DOCX file
            
        Returns:
            Extracted text
        """
        start_time = time.time()
        
        try:
            doc = Document(file_path)
            full_text = []
            
            # Extract paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)
            
            # Extract text from tables
            for table in doc.tables:
                full_text.append("\n[TABLE]")
                for row in table.rows:
                    row_text = " | ".join([cell.text for cell in row.cells])
                    full_text.append(row_text)
                full_text.append("[/TABLE]\n")
            
            result = "\n".join(full_text)
            
            # Log extraction
            extraction_time = time.time() - start_time
            log_extraction(file_path.name, len(result), extraction_time)
            
            return result
            
        except Exception as e:
            log_error("DOCXExtraction", str(e), f"File: {file_path}")
            raise
    
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from DOCX
        
        Args:
            file_path: Path to DOCX file
            
        Returns:
            Metadata dictionary
        """
        try:
            doc = Document(file_path)
            
            metadata = {
                'num_paragraphs': len(doc.paragraphs),
                'num_tables': len(doc.tables),
                'num_sections': len(doc.sections),
            }
            
            # Try to extract core properties
            try:
                core_props = doc.core_properties
                metadata['author'] = core_props.author or ""
                metadata['title'] = core_props.title or ""
                metadata['created'] = str(core_props.created) if core_props.created else ""
                metadata['modified'] = str(core_props.modified) if core_props.modified else ""
            except:
                pass
            
            return metadata
            
        except Exception as e:
            log_error("DOCXMetadataExtraction", str(e), f"File: {file_path}")
            return {}
    
    def extract_tables(self, file_path: Path) -> list:
        """
        Extract tables from DOCX
        
        Args:
            file_path: Path to DOCX file
            
        Returns:
            List of tables
        """
        try:
            doc = Document(file_path)
            all_tables = []
            
            for table_num, table in enumerate(doc.tables, 1):
                # Extract table data
                table_data = {
                    'table_num': table_num,
                    'num_rows': len(table.rows),
                    'num_cols': len(table.columns),
                    'rows': [],
                    'data': []
                }
                
                # Get all rows
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    table_data['rows'].append(row_data)
                
                # Assume first row is header
                if table_data['rows']:
                    headers = table_data['rows'][0]
                    table_data['headers'] = headers
                    
                    # Convert to list of dictionaries
                    for row in table_data['rows'][1:]:
                        if len(row) == len(headers):
                            row_dict = {headers[i]: row[i] for i in range(len(headers))}
                            table_data['data'].append(row_dict)
                
                all_tables.append(table_data)
                logger.info(f"Extracted table {table_num}: {table_data['num_rows']} rows x {table_data['num_cols']} cols")
            
            return all_tables
            
        except Exception as e:
            log_error("DOCXTableExtraction", str(e), f"File: {file_path}")
            return []
