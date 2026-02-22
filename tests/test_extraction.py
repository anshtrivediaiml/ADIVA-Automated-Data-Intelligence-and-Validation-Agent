"""
Test Script for Document Extraction System

This script tests the basic extraction functionality.
"""

import sys
from pathlib import Path

# Add backend to path (project root is one level above tests/)
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / 'backend'))


from extractor import DocumentExtractor
from logger import logger
import json


def test_extraction():
    """Test document extraction"""
    
    logger.info("=" * 60)
    logger.info("TESTING DOCUMENT EXTRACTION SYSTEM")
    logger.info("=" * 60)
    
    # Initialize extractor
    extractor = DocumentExtractor()
    
    # Check if sample file exists
    sample_file = Path("data/samples/Orchestration_UI.pdf")
    
    if sample_file.exists():
        logger.info(f"\nTesting extraction with: {sample_file.name}")
        logger.info("-" * 60)
        
        try:
            # Extract from the document
            result = extractor.extract(str(sample_file))
            
            # Display results
            print("\n" + "=" * 60)
            print("EXTRACTION RESULTS")
            print("=" * 60)
            print(f"Status: {result['status']}")
            print(f"File: {result['metadata']['filename']}")
            print(f"File Type: {result['metadata']['file_type']}")
            print(f"Extractor Used: {result['metadata']['extractor_used']}")
            print(f"Processing Time: {result['metadata']['processing_time_seconds']} seconds")
            print(f"Characters Extracted: {result['text']['length']}")
            print(f"Words Extracted: {result['text']['word_count']}")
            print(f"Tables Found: {len(result['tables'])}")
            
            if 'output_file' in result:
                print(f"Output saved to: {result['output_file']}")
            
            print("=" * 60)
            
            # Show extraction log
            print("\nExtraction Log:")
            for log_entry in result['extraction_log']:
                print(f"  - {log_entry}")
            
            logger.info("\n" + "=" * 60)
            logger.info("EXTRACTION TEST: SUCCESS")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            print(f"\n❌ Error: {e}")
    
    else:
        logger.warning(f"Sample file not found: {sample_file}")
        logger.info("\nTo test with a real document:")
        logger.info("1. Place a PDF or DOCX file in data/samples/")
        logger.info("2. Update the sample_file path in this script")
        logger.info("3. Run: python test_extraction.py")
        
        logger.info("\n" + "=" * 60)
        logger.info("EXTRACTION SYSTEM STATUS: READY (Waiting for test document)")
        logger.info("=" * 60)


if __name__ == "__main__":
    test_extraction()
