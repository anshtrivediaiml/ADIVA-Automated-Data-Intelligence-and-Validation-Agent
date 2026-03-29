"""
ADIVA - Document Extraction Orchestrator

This module orchestrates the complete document extraction pipeline:
- Document preprocessing and analysis
- Multi-format extraction (PDF, DOCX, OCR)
- Table extraction
- Metadata collection
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable
import time
import json
import re

try:
    from extractors.preprocessor import DocumentPreprocessor
    from extractors.pdf_extractor import PDFExtractor
    from extractors.docx_extractor import DOCXExtractor
    from extractors.ocr_extractor import OCRExtractor, _detect_script_from_text, _is_garbage_text
    from logger import logger, log_extraction, log_error
    import config
except ModuleNotFoundError:
    from backend.extractors.preprocessor import DocumentPreprocessor
    from backend.extractors.pdf_extractor import PDFExtractor
    from backend.extractors.docx_extractor import DOCXExtractor
    from backend.extractors.ocr_extractor import OCRExtractor, _detect_script_from_text, _is_garbage_text
    from backend.logger import logger, log_extraction, log_error
    from backend import config

# Map Tesseract codes to display names
_LANG_DISPLAY = {'eng': 'English', 'hin': 'Hindi', 'guj': 'Gujarati'}


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
            try:
                from ai_agent import AIAgent
            except ModuleNotFoundError as exc:
                if exc.name != "ai_agent":
                    raise
                from backend.ai_agent import AIAgent
            if config.MISTRAL_API_KEY:
                self.ai_agent = AIAgent()
                logger.info("AI Agent initialized for intelligent extraction")
            else:
                logger.warning("Mistral API key not configured. AI features disabled.")
        except Exception as e:
            logger.warning(f"Could not initialize AI Agent: {e}")
        
        # Initialize confidence scorer
        try:
            try:
                from confidence_scorer import ConfidenceScorer
            except ModuleNotFoundError as exc:
                if exc.name != "confidence_scorer":
                    raise
                from backend.confidence_scorer import ConfidenceScorer
            self.confidence_scorer = ConfidenceScorer()
            logger.info("Confidence Scorer initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Confidence Scorer: {e}")
            self.confidence_scorer = None
        
        logger.info("DocumentExtractor initialized with all extractors")

    def _extract_ocr_confidence(
        self,
        extractor: Any,
        raw_text: str,
        metadata: Optional[Dict[str, Any]],
    ) -> float:
        """Use OCR run metadata first, then fall back to legacy text headers."""
        if extractor != self.ocr_extractor:
            return 1.0

        run_summary = (metadata or {}).get('ocr_run_summary', {})
        average_confidence = run_summary.get('average_page_confidence')
        if isinstance(average_confidence, (int, float)):
            return max(0.0, min(1.0, float(average_confidence) / 100.0))

        match = re.search(r"OCR Confidence:\s*([0-9]+(?:\.[0-9]+)?)%", raw_text or "")
        if match:
            try:
                return max(0.0, min(1.0, float(match.group(1)) / 100.0))
            except Exception:
                return 1.0
        return 1.0

    def _promote_status(self, current_status: str, candidate_status: str) -> str:
        priority = {'success': 0, 'needs_review': 1, 'low_confidence': 2, 'error': 3}
        if priority.get(candidate_status, 0) > priority.get(current_status, 0):
            return candidate_status
        return current_status

    def _build_review_summary(
        self,
        *,
        extractor: Any,
        raw_text: str,
        quality: Dict[str, Any],
        classification: Optional[Dict[str, Any]],
        has_schema: bool,
        structured_data: Optional[Dict[str, Any]],
        extraction_confidence: Optional[float],
        comprehensive_confidence: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        status = 'success'
        reasons: list[str] = []
        ocr_confidence = self._extract_ocr_confidence(extractor, raw_text, metadata)
        overall_confidence = None

        if comprehensive_confidence:
            overall_confidence = comprehensive_confidence.get('overall_confidence')

        signals = {
            'quality_score': quality.get('quality_score'),
            'ocr_confidence': round(ocr_confidence, 2),
            'classification_confidence': (classification or {}).get('confidence'),
            'classification_status': (classification or {}).get('classification_status'),
            'classification_source': (classification or {}).get('classification_source'),
            'schema_expected': has_schema,
            'extraction_confidence': extraction_confidence,
            'overall_confidence': overall_confidence,
        }

        text_word_count = len((raw_text or '').split())
        if not (raw_text or '').strip():
            status = self._promote_status(status, 'low_confidence')
            reasons.append('no_text_extracted')
        elif extractor == self.ocr_extractor and text_word_count < 20:
            status = self._promote_status(status, 'low_confidence')
            reasons.append('very_little_text_extracted')

        quality_score = float(quality.get('quality_score', 1.0) or 0.0)
        if quality_score < config.REVIEW_MIN_QUALITY_SCORE:
            reasons.append('document_quality_below_review_threshold')
            status = self._promote_status(status, 'needs_review')
        if quality_score < 0.45:
            reasons.append('document_quality_very_low')
            status = self._promote_status(status, 'low_confidence')

        if extractor == self.ocr_extractor:
            if ocr_confidence < config.REVIEW_MIN_OCR_CONFIDENCE:
                reasons.append('ocr_confidence_below_review_threshold')
                status = self._promote_status(status, 'needs_review')
            if ocr_confidence < config.LOW_CONFIDENCE_MIN_OCR:
                reasons.append('ocr_confidence_very_low')
                status = self._promote_status(status, 'low_confidence')

        if classification:
            if classification.get('classification_status') != 'confirmed':
                reasons.append('classification_not_confirmed_by_llm')
                status = self._promote_status(status, 'needs_review')
            if float(classification.get('confidence', 0.0) or 0.0) < config.REVIEW_MIN_CLASSIFICATION_CONFIDENCE:
                reasons.append('classification_confidence_low')
                status = self._promote_status(status, 'needs_review')
            if classification.get('classification_warning'):
                reasons.append('classification_disagreement_detected')
                status = self._promote_status(status, 'needs_review')
        else:
            reasons.append('classification_missing')
            status = self._promote_status(status, 'needs_review')

        if has_schema and not structured_data:
            reasons.append('schema_data_missing')
            status = self._promote_status(status, 'needs_review')

        if extraction_confidence is not None:
            if extraction_confidence < config.REVIEW_MIN_EXTRACTION_CONFIDENCE:
                reasons.append('schema_coverage_below_review_threshold')
                status = self._promote_status(status, 'needs_review')
            if extraction_confidence < config.LOW_CONFIDENCE_MIN_EXTRACTION:
                reasons.append('schema_coverage_very_low')
                status = self._promote_status(status, 'low_confidence')

        if isinstance(overall_confidence, (int, float)):
            if overall_confidence < config.REVIEW_MIN_EXTRACTION_CONFIDENCE:
                reasons.append('overall_confidence_below_review_threshold')
                status = self._promote_status(status, 'needs_review')
            if overall_confidence < config.LOW_CONFIDENCE_MIN_EXTRACTION:
                reasons.append('overall_confidence_very_low')
                status = self._promote_status(status, 'low_confidence')

        return {
            'status': status,
            'needs_human_review': status != 'success',
            'reasons': sorted(set(reasons)),
            'signals': signals,
            'quality_issues': quality.get('issues', []),
        }


    
    def extract(
        self,
        file_path: str,
        stage_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Complete extraction pipeline for a document
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing all extracted data and metadata
        """
        start_time = time.time()
        stage_start = time.perf_counter()
        file_path = Path(file_path)
        
        logger.info(f"Starting extraction for: {file_path.name}")
        
        extraction_log = []
        stage_timings: Dict[str, float] = {}

        def _notify_stage(state: str, stage_name: str) -> None:
            if stage_callback is None:
                return
            try:
                stage_callback(state, stage_name)
            except Exception as exc:
                logger.warning(f"Stage callback failed for state={state}, stage={stage_name}: {exc}")

        def _mark(stage_name: str) -> None:
            nonlocal stage_start
            now = time.perf_counter()
            stage_timings[stage_name] = round(now - stage_start, 4)
            stage_start = now
        
        try:
            # Step 1: Preprocess and analyze
            extraction_log.append("Step 1: Preprocessing and quality assessment")
            _notify_stage("preprocessing", "quality_assessment")
            file_type = self.preprocessor.detect_file_type(file_path)
            quality = self.preprocessor.assess_quality(file_path)
            _mark("preprocess")
            
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
            _mark("select_extractor")
            
            # Step 3: Extract text
            extraction_log.append("Step 3: Extracting text content")
            _notify_stage("ocr_running", "text_extraction")

            if hasattr(extractor, 'extract_text') and isinstance(extractor, OCRExtractor):
                raw_text = extractor.extract_text(
                    file_path,
                    language=None,
                    quality_assessment=quality,
                )
            else:
                raw_text = extractor.extract_text(file_path)

            # Case 8: Garbage text detection for digital PDFs
            # If a "digital" PDF has garbage embedded text (bad prior OCR),
            # re-route to the OCR extractor for proper extraction.
            if not isinstance(extractor, OCRExtractor) and file_type == 'pdf':
                if _is_garbage_text(raw_text):
                    logger.warning(
                        f"Digital PDF '{file_path.name}' has garbage embedded text "
                        f"(likely bad prior OCR). Re-routing to OCR extractor."
                    )
                    extraction_log.append(
                        "Step 3b: Garbage text detected in digital PDF — re-routing to OCR"
                    )
                    extractor = self.ocr_extractor
                    raw_text = extractor.extract_text(
                        file_path,
                        language=None,
                        quality_assessment=quality,
                    )
            _mark("extract_text")

            word_count = len(raw_text.split())
            extraction_log.append(f"Extracted {len(raw_text)} characters, {word_count} words")

            # Detect language from extracted text using Unicode script ranges
            detected_lang_code = _detect_script_from_text(raw_text)
            detected_lang_display = _LANG_DISPLAY.get(detected_lang_code, detected_lang_code)
            extraction_log.append(f"Detected language: {detected_lang_display}")
            logger.info(f"Document language detected: {detected_lang_display}")
            
            # Step 4: Extract metadata
            extraction_log.append("Step 4: Extracting metadata")
            metadata = extractor.extract_metadata(file_path)
            _mark("extract_metadata")
            
            # Step 5: Extract tables
            extraction_log.append("Step 5: Extracting tables")
            tables = extractor.extract_tables(file_path)
            extraction_log.append(f"Found {len(tables)} tables")
            _mark("extract_tables")
            
            # Step 6: AI Classification (if available)
            classification = None
            _notify_stage("classifying", "document_classification")
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
            _mark("classify")
            
            # Step 7: Structured Data Extraction (if document type has a schema)
            structured_data = None
            extraction_confidence = None
            _notify_stage("extracting", "structured_extraction")

            # Dynamically use the schema registry — any type with a registered schema
            # will automatically be extracted. No need to maintain a hardcoded list.
            try:
                from schemas import SCHEMA_REGISTRY
            except ModuleNotFoundError as exc:
                if exc.name != "schemas":
                    raise
                from backend.schemas import SCHEMA_REGISTRY

            doc_type = classification['document_type'] if classification else 'unknown'
            has_schema = doc_type in SCHEMA_REGISTRY
            llm_available_for_extraction = bool(classification) and not classification.get('llm_error')

            if self.ai_agent and classification and has_schema and llm_available_for_extraction:
                extraction_log.append(f"Step 7: Extracting structured data for {doc_type}")
                try:
                    structured_data = self.ai_agent.extract_structured_data(raw_text, doc_type)
                    extraction_confidence = self.ai_agent.calculate_extraction_confidence(
                        structured_data,
                        doc_type
                    )
                    extraction_log.append(f"Structured extraction complete (confidence: {extraction_confidence})")
                except Exception as e:
                    logger.error(f"Structured extraction failed: {e}")
                    extraction_log.append(f"Structured extraction failed: {str(e)}")
            elif self.ai_agent and classification and has_schema and not llm_available_for_extraction:
                extraction_log.append(
                    f"Step 7: Structured extraction skipped because the LLM was unavailable during classification for '{doc_type}'"
                )
            else:
                extraction_log.append(f"Step 7: Structured extraction skipped (type '{doc_type}' has no schema)")
            _mark("structured_extract")

            
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
                    'detected_language': detected_lang_display,
                    'detected_language_code': detected_lang_code,
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
            
            comprehensive_confidence = None
            if structured_data:
                result['structured_data'] = structured_data
                result['extraction_confidence'] = extraction_confidence
                
                # Add comprehensive confidence scoring
                if self.confidence_scorer and classification:
                    extraction_metadata = {
                        'ocr_confidence': self._extract_ocr_confidence(extractor, raw_text, metadata)
                    }
                    
                    comprehensive_confidence = self.confidence_scorer.calculate_comprehensive_confidence(
                        structured_data,
                        classification['document_type'],
                        extraction_metadata
                    )
                    
                    result['comprehensive_confidence'] = comprehensive_confidence
                    logger.info(f"Comprehensive confidence: {comprehensive_confidence['overall_confidence']} ({comprehensive_confidence['grade']})")
            _mark("confidence_scoring")

            review_summary = self._build_review_summary(
                extractor=extractor,
                raw_text=raw_text,
                quality=quality,
                classification=classification,
                has_schema=has_schema,
                structured_data=structured_data,
                extraction_confidence=extraction_confidence,
                comprehensive_confidence=comprehensive_confidence,
                metadata=metadata,
            )
            result['status'] = review_summary['status']
            result['review'] = review_summary
            result['metadata']['review_summary'] = review_summary

            
            # Step 7: Create organized output folder
            logger.info("Creating extraction output folder")
            _notify_stage("exporting", "persist_outputs")
            extraction_folder = config.get_extraction_folder(file_path.name)
            extraction_log.append(f"Step 8: Saving results to: {extraction_folder.name}")
            
            # Save JSON results
            output_file = config.get_output_filename("extraction", ".json", extraction_folder)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            result['output_file'] = str(output_file)
            result['extraction_folder'] = str(extraction_folder)
            logger.info(f"Extraction results saved to: {extraction_folder.name}/extraction.json")
            _mark("save_json")
            
            # Step 8: Export to multiple formats (if structured data exists)
            if structured_data:
                extraction_log.append("Step 9: Exporting to multiple formats")
                logger.info("Exporting to CSV, Excel, and HTML")
                
                try:
                    try:
                        from exporters import CSVExporter, ExcelExporter, HTMLExporter
                    except ModuleNotFoundError as exc:
                        if exc.name != "exporters":
                            raise
                        from backend.exporters import CSVExporter, ExcelExporter, HTMLExporter
                    
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
            _mark("exports")

            result['metadata']['stage_timings_seconds'] = stage_timings



            
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
                    'processing_time_seconds': round(processing_time, 2),
                    'stage_timings_seconds': stage_timings,
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

