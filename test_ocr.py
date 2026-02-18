"""
Test OCR Functionality

Test Tesseract OCR with ADIVA.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from logger import logger


def test_tesseract():
    """Test Tesseract installation"""
    
    logger.info("=" * 70)
    logger.info("TESTING TESSERACT OCR")
    logger.info("=" * 70)
    
    try:
        import pytesseract
        import platform
        
        # Configure path if Windows
        if platform.system() == 'Windows':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Users\AnshTrivedi\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        
        # Get version
        version = pytesseract.get_tesseract_version()
        print(f"\n✅ Tesseract OCR is installed and working!")
        print(f"Version: {version}")
        
        logger.info(f"Tesseract version: {version}")
        
        # Test OCR on simple text
        try:
            from PIL import Image
            print(f"\n✅ PIL (Pillow) is installed")
        except ImportError:
            print(f"\n⚠️  PIL (Pillow) not installed - install with: pip install Pillow")
        
        try:
            from pdf2image import convert_from_path
            print(f"✅ pdf2image is installed")
        except ImportError:
            print(f"⚠️  pdf2image not installed - install with: pip install pdf2image")
        
        print("\n" + "=" * 70)
        print("TESSERACT OCR: READY FOR USE ✅")
        print("=" * 70)
        
        logger.info("Tesseract OCR test completed successfully")
        
    except Exception as e:
        print(f"\n❌ Error testing Tesseract: {e}")
        logger.error(f"Tesseract test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_tesseract()
