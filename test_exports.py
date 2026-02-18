"""
Test Export Functionality

Test all export formats with a sample extraction.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from extractor import DocumentExtractor
from logger import logger


def test_exports():
    """Test all export formats"""
    
    logger.info("=" * 70)
    logger.info("TESTING EXPORT FUNCTIONALITY")
    logger.info("=" * 70)
    
    # Initialize extractor
    extractor = DocumentExtractor()
    
    # Test with resume
    sample_file = Path("data/samples/functionalsample.pdf")
    
    if sample_file.exists():
        logger.info(f"\nExtracting and exporting: {sample_file.name}")
        logger.info("-" * 70)
        
        try:
            # Extract
            result = extractor.extract(str(sample_file))
            
            print("\n" + "=" * 70)
            print("EXPORT TEST RESULTS")
            print("=" * 70)
            print(f"Status: {result['status']}")
            print(f"File: {result['metadata']['filename']}")
            
            if 'exports' in result:
                print("\n✅ Exports Created:")
                for format_type, file_path in result['exports'].items():
                    print(f"  • {format_type.upper()}: {Path(file_path).name}")
            else:
                print("\n⚠️  No structured data exports (document may not have schema)")
            
            print(f"\nJSON Output: {Path(result['output_file']).name}")
            
            if 'comprehensive_confidence' in result:
                conf = result['comprehensive_confidence']
                print(f"\nOverall Confidence: {conf['overall_confidence'] * 100:.1f}% (Grade: {conf['grade']})")
            
            print("=" * 70)
            
            logger.info("Export test completed successfully!")
            
        except Exception as e:
            logger.error(f"Export test failed: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        logger.warning(f"Sample file not found: {sample_file}")
        print("\nPlace a test document in data/samples/ and update the path")


if __name__ == "__main__":
    test_exports()
