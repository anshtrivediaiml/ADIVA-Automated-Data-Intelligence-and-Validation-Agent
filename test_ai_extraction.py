"""
Test Script for AI-Powered Document Extraction

This script tests the complete extraction pipeline with AI classification and structured extraction.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from extractor import DocumentExtractor
from logger import logger
import json


def test_ai_extraction():
    """Test AI-powered document extraction"""
    
    logger.info("=" * 70)
    logger.info("TESTING AI-POWERED DOCUMENT EXTRACTION SYSTEM")
    logger.info("=" * 70)
    
    # Initialize extractor
    extractor = DocumentExtractor()
    
    # Check if sample file exists
    sample_file = Path("data/samples/functionalsample.pdf")
    
    if sample_file.exists():
        logger.info(f"\nTesting AI extraction with: {sample_file.name}")
        logger.info("-" * 70)
        
        try:
            # Extract from the document
            result = extractor.extract(str(sample_file))
            
            # Display results
            print("\n" + "=" * 70)
            print("AI-POWERED EXTRACTION RESULTS")
            print("=" * 70)
            print(f"Status: {result['status']}")
            print(f"File: {result['metadata']['filename']}")
            print(f"Processing Time: {result['metadata']['processing_time_seconds']} seconds")
            print(f"Words Extracted: {result['text']['word_count']}")
            print(f"Tables Found: {len(result['tables'])}")
            
            # Show AI classification results
            if 'classification' in result:
                print("\n" + "-" * 70)
                print("AI CLASSIFICATION:")
                print(f"  Document Type: {result['classification']['document_type']}")
                print(f"  Confidence: {result['classification'].get('confidence', 'N/A')}")
                print(f"  Reasoning: {result['classification'].get('reasoning', 'N/A')}")
            else:
                print("\n⚠️  AI Classification: Not available (API key may not be configured)")
            
            # Show structured extraction results
            if 'structured_data' in result:
                print("\n" + "-" * 70)
                print("STRUCTURED DATA EXTRACTION:")
                print(f"  Extraction Confidence: {result.get('extraction_confidence', 'N/A')}")
                print(f"  Extracted Fields: {len(result['structured_data'])} top-level fields")
                print(f"  Preview: {list(result['structured_data'].keys())[:5]}")
            else:
                print("\n  Structured Extraction: Skipped (document type not recognized or no schema)")
            
            if 'output_file' in result:
                print("\n" + "-" * 70)
                print(f"Output saved to: {result['output_file']}")
            
            print("=" * 70)
            
            # Show extraction log
            print("\nExtraction Log:")
            for log_entry in result['extraction_log']:
                print(f"  {log_entry}")
            
            logger.info("\n" + "=" * 70)
            logger.info("AI EXTRACTION TEST: SUCCESS")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        logger.warning(f"Sample file not found: {sample_file}")
        logger.info("\nTo test with a real document:")
        logger.info("1. Place a PDF or DOCX file in data/samples/")
        logger.info("2. Update the sample_file path in this script")
        logger.info("3. Ensure MISTRAL_API_KEY is set in .env")
        logger.info("4. Run: python test_ai_extraction.py")


if __name__ == "__main__":
    test_ai_extraction()
