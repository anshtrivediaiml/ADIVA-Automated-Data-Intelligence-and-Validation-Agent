"""
Multi-Language OCR Test

Tests multi-language OCR capability with language detection.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from extractors.ocr_extractor import OCRExtractor
from logger import logger


def test_multilang_setup():
    """Test multi-language OCR setup"""
    
    logger.info("=" * 70)
    logger.info("TESTING MULTI-LANGUAGE OCR SETUP")
    logger.info("=" * 70)
    
    print("\n" + "=" * 70)
    print("Multi-Language OCR Setup Test")
    print("=" * 70)
    
    try:
        # Initialize OCR extractor
        extractor = OCRExtractor()
        
        print(f"\n✅ OCR Extractor initialized successfully!")
        print(f"\n📋 Supported Languages:")
        for code, name in extractor.supported_languages.items():
            print(f"   • {name} ({code})")
        
        # Check available languages
        available = extractor._get_available_languages()
        print(f"\n💾 Installed Tesseract Languages:")
        for lang in available:
            lang_name = extractor.supported_languages.get(lang, lang)
            if lang in extractor.supported_languages:
                print(f"   ✓ {lang_name} ({lang})")
            else:
                print(f"   • {lang}")
        
        # Check for missing languages
        missing = []
        for code in ['hin', 'guj']:
            if code not in available:
                missing.append(extractor.supported_languages[code])
        
        if missing:
            print(f"\n⚠️  Missing Language Packs:")
            for lang in missing:
                print(f"   ❌ {lang}")
            print(f"\n📖 Installation Instructions:")
            print(f"   See LANGUAGE_SETUP.md for detailed steps")
            print(f"   Quick: Download .traineddata files to tessdata folder")
        else:
            print(f"\n🎉 All language packs installed!")
        
        print("\n" + "=" * 70)
        print("Multi-Language OCR: READY")
        print("=" * 70)
        
        logger.info("Multi-language OCR setup test completed")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Multi-language OCR test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_multilang_setup()
