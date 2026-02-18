"""
ADIVA - Document Extraction Orchestrator

This module orchestrates the complete document extraction pipeline:
- Document preprocessing and analysis
- Multi-format extraction (PDF, DOCX, OCR)
- Table extraction
- Metadata collection
"""

from pathlib import Path
from typing import Dict, Any, Optional
import time
import json

from extractors.preprocessor import DocumentPreprocessor
from extractors.pdf_extractor import PDFExtractor
from extractors.docx_extractor import DOCXExtractor
from extractors.ocr_extractor import OCRExtractor
from logger import logger, log_extraction, log_error
import config


class DocumentExtractor:
    """
    Main document extraction orchestrator
    Handles the complete extraction pipeline
    """
    
    def __init__(self):
        """Initialize the document extractor with all sub-extractors"""
        logger.info("Initializing DocumentExtractor")
        
        # Initialize all extractors
        self.preprocessor = DocumentPreprocessor()
        self.pdf_extractor = PDFExtractor()
        self.docx_extractor = DOCXExtractor()
        self.ocr_extractor = OCRExtractor()
        
        # Initialize AI agent (optional, only if API key is configured)
        self.ai_agent = None
        try:
            from ai_agent import AIAgent
            if config.MISTRAL_API_KEY:
                self.ai_agent = AIAgent()
                logger.info("AI Agent initialized for intelligent extraction")
            else:
                logger.warning("Mistral API key not configured. AI features disabled.")
        except Exception as e:
            logger.warning(f"Could not initialize AI Agent: {e}")
        
        # Initialize confidence scorer
        try:
            from confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()
            logger.info("Confidence Scorer initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Confidence Scorer: {e}")
            self.confidence_scorer = None
        
        logger.info("DocumentExtractor initialized with all extractors")


    
    def extract(self, file_path: str) -> Dict[str, Any]:
        """
        Complete extraction pipeline for a document
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing all extracted data and metadata
        """
        start_time = time.time()
        file_path = Path(file_path)
        
        logger.info(f"Starting extraction for: {file_path.name}")
        
        extraction_log = []
        
        try:
            # Step 1: Preprocess and analyze
            extraction_log.append("Step 1: Preprocessing and quality assessment")
            file_type = self.preprocessor.detect_file_type(file_path)
            quality = self.preprocessor.assess_quality(file_path)
            
            extraction_log.append(f"File type detected: {file_type}")
            extraction_log.append(f"Quality score: {quality['quality_score']}")
            
            if not quality['readable']:
                raise ValueError(f"Document not readable: {quality['issues']}")
            
            # Step 2: Choose appropriate extractor
            extraction_log.append("Step 2: Selecting extractor")
            
            if file_type == 'pdf':
                is_scanned = self.preprocessor.is_scanned_pdf(file_path)
                if is_scanned:
                    extraction_log.append("Using OCR extractor (scanned PDF)")
                    extractor = self.ocr_extractor
                else:
                    extraction_log.append("Using PDF extractor (digital PDF)")
                    extractor = self.pdf_extractor
            elif file_type == 'docx':
                extraction_log.append("Using DOCX extractor")
                extractor = self.docx_extractor
            elif file_type == 'image':
                extraction_log.append("Using OCR extractor (image)")
                extractor = self.ocr_extractor
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # Step 3: Extract text
            extraction_log.append("Step 3: Extracting text content")
            raw_text = extractor.extract_text(file_path)
            word_count = len(raw_text.split())
            extraction_log.append(f"Extracted {len(raw_text)} characters, {word_count} words")
            
            # Step 4: Extract metadata
            extraction_log.append("Step 4: Extracting metadata")
            metadata = extractor.extract_metadata(file_path)
            
            # Step 5: Extract tables
            extraction_log.append("Step 5: Extracting tables")
            tables = extractor.extract_tables(file_path)
            extraction_log.append(f"Found {len(tables)} tables")
            
            # Step 6: AI Classification (if available)
            classification = None
            if self.ai_agent:
                extraction_log.append("Step 6: AI document classification")
                try:
                    classification = self.ai_agent.classify_document(raw_text[:3000])
                    extraction_log.append(f"Classified as: {classification['document_type']} (confidence: {classification.get('confidence', 0)})")
                except Exception as e:
                    logger.error(f"Classification failed: {e}")
                    extraction_log.append(f"Classification failed: {str(e)}")
            else:
                extraction_log.append("Step 6: AI classification skipped (AI agent not available)")
            
            # Step 7: Structured Data Extraction (if document type recognized)
            structured_data = None
            extraction_confidence = None
            
            if self.ai_agent and classification and classification['document_type'] in ['invoice', 'resume', 'contract']:
                extraction_log.append(f"Step 7: Extracting structured data for {classification['document_type']}")
                try:
                    structured_data = self.ai_agent.extract_structured_data(raw_text, classification['document_type'])
                    extraction_confidence = self.ai_agent.calculate_extraction_confidence(
                        structured_data, 
                        classification['document_type']
                    )
                    extraction_log.append(f"Structured extraction complete (confidence: {extraction_confidence})")
                except Exception as e:
                    logger.error(f"Structured extraction failed: {e}")
                    extraction_log.append(f"Structured extraction failed: {str(e)}")
            else:
                extraction_log.append("Step 7: Structured extraction skipped")
            
            # Step 8: Prepare output
            processing_time = time.time() - start_time
            extraction_log.append(f"Step 8: Extraction complete in {processing_time:.2f} seconds")

            
            # Build result
            result = {
                'status': 'success',
                'metadata': {
                    'filename': file_path.name,
                    'file_path': str(file_path),
                    'file_size_bytes': file_path.stat().st_size,
                    'file_type': file_type,
                    'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'processing_time_seconds': round(processing_time, 2),
                    'extractor_used': extractor.name,
                    'quality_assessment': quality,
                    **metadata
                },
                'text': {
                    'raw': raw_text,
                    'length': len(raw_text),
                    'word_count': word_count
                },
                'tables': tables,
                'extraction_log': extraction_log
            }
            
            # Add AI results if available
            if classification:
                result['classification'] = classification
            
            if structured_data:
                result['structured_data'] = structured_data
                result['extraction_confidence'] = extraction_confidence
                
                # Add comprehensive confidence scoring
                if self.confidence_scorer and classification:
                    extraction_metadata = {
                        'ocr_confidence': quality.get('ocr_confidence', 1.0) if quality.get('is_scanned') else 1.0
                    }
                    
                    comprehensive_confidence = self.confidence_scorer.calculate_comprehensive_confidence(
                        structured_data,
                        classification['document_type'],
                        extraction_metadata
                    )
                    
                    result['comprehensive_confidence'] = comprehensive_confidence
                    logger.info(f"Comprehensive confidence: {comprehensive_confidence['overall_confidence']} ({comprehensive_confidence['grade']})")

            
            # Step 7: Create organized output folder
            logger.info("Creating extraction output folder")
            extraction_folder = config.get_extraction_folder(file_path.name)
            extraction_log.append(f"Step 8: Saving results to: {extraction_folder.name}")
            
            # Save JSON results
            output_file = config.get_output_filename("extraction", ".json", extraction_folder)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            result['output_file'] = str(output_file)
            result['extraction_folder'] = str(extraction_folder)
            logger.info(f"Extraction results saved to: {extraction_folder.name}/extraction.json")
            
            # Step 8: Export to multiple formats (if structured data exists)
            if structured_data:
                extraction_log.append("Step 9: Exporting to multiple formats")
                logger.info("Exporting to CSV, Excel, and HTML")
                
                try:
                    from exporters import CSVExporter, ExcelExporter, HTMLExporter
                    
                    # CSV Export
                    csv_exporter = CSVExporter()
                    csv_file = config.get_output_filename("extraction", ".csv", extraction_folder)
                    csv_exporter.export(result, csv_file)
                    result['exports'] = result.get('exports', {})
                    result['exports']['csv'] = csv_file
                    extraction_log.append(f"  ✓ CSV: {Path(csv_file).name}")
                    
                    # Excel Export
                    excel_exporter = ExcelExporter()
                    excel_file = config.get_output_filename("extraction", ".xlsx", extraction_folder)
                    excel_exporter.export(result, excel_file)
                    result['exports']['excel'] = excel_file
                    extraction_log.append(f"  ✓ Excel: {Path(excel_file).name}")
                    
                    # HTML Export
                    html_exporter = HTMLExporter()
                    html_file = config.get_output_filename("extraction", ".html", extraction_folder)
                    html_exporter.export(result, html_file)
                    result['exports']['html'] = html_file
                    extraction_log.append(f"  ✓ HTML: {Path(html_file).name}")
                    
                    logger.info(f"All exports completed in folder: {extraction_folder.name}")
                    
                except Exception as e:
                    logger.error(f"Export failed: {e}")
                    extraction_log.append(f"Export failed: {str(e)}")
            else:
                extraction_log.append("Step 9: Format exports skipped (no structured data)")



            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            log_error("DocumentExtraction", str(e), f"File: {file_path}")
            
            return {
                'status': 'error',
                'error': str(e),
                'metadata': {
                    'filename': file_path.name,
                    'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'processing_time_seconds': round(processing_time, 2)
                },
                'extraction_log': extraction_log
            }
    
    def extract_batch(self, file_paths: list) -> list:
        """
        Extract from multiple documents
        
        Args:
            file_paths: List of file paths
            
        Returns:
            List of extraction results
        """
        logger.info(f"Starting batch extraction for {len(file_paths)} files")
        results = []
        
        for file_path in file_paths:
            try:
                result = self.extract(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to extract {file_path}: {e}")
                results.append({
                    'status': 'error',
                    'filename': Path(file_path).name,
                    'error': str(e)
                })
        
        logger.info(f"Batch extraction complete: {len(results)} processed")
        return results

