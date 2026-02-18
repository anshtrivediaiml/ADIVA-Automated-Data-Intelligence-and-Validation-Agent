"""
OCR Test with Sample Scanned Documents

Tests OCR extraction with various scanned document samples.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from extractor import DocumentExtractor
from logger import logger
import json


def test_ocr_extraction():
    """Test OCR with scanned documents"""
    
    logger.info("=" * 70)
    logger.info("TESTING OCR EXTRACTION WITH SCANNED DOCUMENTS")
    logger.info("=" * 70)
    
    # Initialize extractor
    extractor = DocumentExtractor()
    
    # Find sample images
    samples_dir = Path("data/samples/scanned")
    
    if not samples_dir.exists():
        print(f"\n⚠️  Scanned samples directory not found: {samples_dir}")
        print("\nCreating directory and instructions...")
        samples_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n✅ Created: {samples_dir}")
        print("\n📁 Place scanned document images in this folder:")
        print(f"   {samples_dir.absolute()}")
        print("\nSupported formats: PDF, PNG, JPG, TIFF, BMP")
        print("\nThen run this script again!")
        return
    
    # Find all image files
    image_files = []
    for ext in ['*.pdf', '*.png', '*.jpg', '*.jpeg', '*.tiff', '*.bmp']:
        image_files.extend(samples_dir.glob(ext))
    
    if not image_files:
        print(f"\n⚠️  No scanned documents found in: {samples_dir}")
        print("\nPlace scanned images or PDFs in this directory, then run again!")
        print("\nSupported formats: PDF, PNG, JPG, TIFF, BMP")
        return
    
    print(f"\n📄 Found {len(image_files)} scanned document(s) to test:\n")
    for f in image_files:
        print(f"  • {f.name}")
    
    # Process each file
    for idx, file_path in enumerate(image_files, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST {idx}/{len(image_files)}: {file_path.name}")
        print("=" * 70)
        
        try:
            logger.info(f"\nExtracting from scanned document: {file_path.name}")
            
            # Extract
            result = extractor.extract(str(file_path))
            
            # Display results
            print(f"\n✅ Status: {result['status']}")
            print(f"📊 Extractor: {result['metadata']['extractor_used']}")
            print(f"⏱️  Time: {result['metadata']['processing_time_seconds']}s")
            
            # OCR-specific info
            if 'extraction_method' in result['metadata']:
                print(f"🔍 Method: {result['metadata']['extraction_method'].upper()}")
            
            # Text stats
            text_length = result['text']['length']
            word_count = result['text']['word_count']
            print(f"📝 Extracted: {text_length} characters, {word_count} words")
            
            # Show preview (first 500 chars)
            preview = result['text']['raw'][:500]
            print(f"\n📄 Text Preview:")
            print("-" * 70)
            print(preview)
            if text_length > 500:
                print(f"\n... (showing first 500 of {text_length} characters)")
            print("-" * 70)
            
            # Classification if available
            if 'classification' in result:
                cls = result['classification']
                print(f"\n🤖 AI Classification:")
                print(f"   Type: {cls['document_type']}")
                print(f"   Confidence: {cls['confidence'] * 100:.1f}%")
            
            # Confidence if available
            if 'comprehensive_confidence' in result:
                conf = result['comprehensive_confidence']
                print(f"\n📊 Extraction Quality:")
                print(f"   Overall: {conf['overall_confidence'] * 100:.1f}% (Grade: {conf['grade']})")
                
                # OCR quality metric
                if 'ocr_quality' in conf['metrics']:
                    ocr_conf = conf['metrics']['ocr_quality'] * 100
                    print(f"   OCR Quality: {ocr_conf:.1f}%")
            
            # Save detailed results
            output_file = Path(result.get('output_file', ''))
            if output_file.exists():
                print(f"\n💾 Detailed results saved to: {output_file.name}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.error(f"OCR extraction failed for {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 70}")
    print("OCR TESTING COMPLETE")
    print("=" * 70)
    logger.info("OCR testing session complete")


if __name__ == "__main__":
    test_ocr_extraction()
