"""
Test OCR Preprocessing Improvements
Tests: Deskew, Shadow Removal, Background Cleanup, DPI Detection
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from logger import logger


def test_opencv_availability():
    """Test if OpenCV is available"""
    print("\n" + "=" * 70)
    print("TESTING OPENCOP AVAILABILITY")
    print("=" * 70)

    try:
        import cv2
        import numpy as np

        print(f"\n[PASS] OpenCV version: {cv2.__version__}")
        print(f"[PASS] NumPy version: {np.__version__}")
        return True
    except ImportError as e:
        print(f"\n[FAIL] OpenCV not available: {e}")
        return False


def test_ocr_extractor_init():
    """Test OCR Extractor initialization"""
    print("\n" + "=" * 70)
    print("TESTING OCR EXTRACTOR INITIALIZATION")
    print("=" * 70)

    try:
        from extractors.ocr_extractor import OCRExtractor, HAS_CV2, HAS_OCR

        extractor = OCRExtractor()

        print(f"\n[PASS] OCR Extractor initialized")
        print(f"  - HAS_CV2: {HAS_CV2}")
        print(f"  - HAS_OCR: {HAS_OCR}")
        print(f"  - OCR Available: {extractor.ocr_available}")
        print(f"  - Available Languages: {extractor._available_langs}")

        return HAS_CV2 and HAS_OCR
    except Exception as e:
        print(f"\n[FAIL] OCR Extractor initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_deskew_method():
    """Test deskew method"""
    print("\n" + "=" * 70)
    print("TESTING DESKEW METHOD")
    print("=" * 70)

    try:
        import cv2
        import numpy as np
        from PIL import Image
        from extractors.ocr_extractor import OCRExtractor

        extractor = OCRExtractor()

        # Create a skewed test image (text at 5 degree angle)
        img = np.ones((500, 800, 3), dtype=np.uint8) * 255
        cv2.putText(
            img,
            "TEST DESKEW SAMPLE DOCUMENT",
            (100, 250),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (0, 0, 0),
            2,
        )

        # Rotate by 5 degrees
        M = cv2.getRotationMatrix2D((400, 250), 5, 1)
        skewed = cv2.warpAffine(img, M, (800, 500), borderValue=(255, 255, 255))

        pil_img = Image.fromarray(skewed)

        # Test deskew
        result = extractor._deskew_image(pil_img)

        print(f"\n[PASS] Deskew method executed")
        print(f"  - Input size: {pil_img.size}")
        print(f"  - Output size: {result.size}")

        return True
    except Exception as e:
        print(f"\n[FAIL] Deskew test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_shadow_removal_method():
    """Test shadow removal method"""
    print("\n" + "=" * 70)
    print("TESTING SHADOW REMOVAL METHOD")
    print("=" * 70)

    try:
        import cv2
        import numpy as np
        from PIL import Image
        from extractors.ocr_extractor import OCRExtractor

        extractor = OCRExtractor()

        # Create image with simulated shadow
        img = np.ones((500, 800, 3), dtype=np.uint8) * 255

        # Add text
        cv2.putText(
            img,
            "TEST SHADOW REMOVAL",
            (100, 250),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (0, 0, 0),
            2,
        )

        # Add shadow gradient
        shadow = np.linspace(255, 150, 500).reshape(500, 1)
        shadow = np.repeat(shadow, 800, axis=1).astype(np.uint8)
        img[:, :, 0] = np.clip(
            img[:, :, 0].astype(int) - (255 - shadow) // 3, 0, 255
        ).astype(np.uint8)
        img[:, :, 1] = np.clip(
            img[:, :, 1].astype(int) - (255 - shadow) // 3, 0, 255
        ).astype(np.uint8)

        pil_img = Image.fromarray(img)

        # Test shadow removal
        result = extractor._remove_shadows(pil_img)

        print(f"\n[PASS] Shadow removal method executed")
        print(f"  - Input size: {pil_img.size}")
        print(f"  - Output size: {result.size}")

        return True
    except Exception as e:
        print(f"\n[FAIL] Shadow removal test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_background_cleanup_method():
    """Test background cleanup method"""
    print("\n" + "=" * 70)
    print("TESTING BACKGROUND CLEANUP METHOD")
    print("=" * 70)

    try:
        import cv2
        import numpy as np
        from PIL import Image
        from extractors.ocr_extractor import OCRExtractor

        extractor = OCRExtractor()

        # Create noisy image
        img = np.ones((500, 800, 3), dtype=np.uint8) * 255

        # Add text
        cv2.putText(
            img,
            "TEST BACKGROUND CLEANUP",
            (100, 250),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (0, 0, 0),
            2,
        )

        # Add noise
        noise = np.random.randint(0, 50, (500, 800, 3), dtype=np.uint8)
        img = np.clip(img.astype(int) - noise, 0, 255).astype(np.uint8)

        pil_img = Image.fromarray(img)

        # Test background cleanup
        result = extractor._cleanup_background(pil_img)

        print(f"\n[PASS] Background cleanup method executed")
        print(f"  - Input size: {pil_img.size}")
        print(f"  - Output mode: {result.mode}")

        return True
    except Exception as e:
        print(f"\n[FAIL] Background cleanup test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_dpi_detection_method():
    """Test DPI detection method"""
    print("\n" + "=" * 70)
    print("TESTING DPI DETECTION METHOD")
    print("=" * 70)

    try:
        import cv2
        import numpy as np
        from PIL import Image
        from extractors.ocr_extractor import OCRExtractor

        extractor = OCRExtractor()

        # Create test images with different sizes
        test_cases = [
            (500, 800, "small"),
            (1000, 1500, "medium"),
            (2000, 3000, "large"),
        ]

        for h, w, desc in test_cases:
            img = np.ones((h, w, 3), dtype=np.uint8) * 255
            font_scale = h / 500
            cv2.putText(
                img,
                "TEST DPI DETECTION",
                (int(100 * font_scale), int(250 * font_scale)),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale * 1.5,
                (0, 0, 0),
                2,
            )

            pil_img = Image.fromarray(img)

            # Test DPI detection
            dpi = extractor._detect_dpi(pil_img)

            print(f"  [{desc}] Size: {w}x{h} -> DPI: {dpi}")

        print(f"\n[PASS] DPI detection method executed")
        return True
    except Exception as e:
        print(f"\n[FAIL] DPI detection test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_enhance_image_pipeline():
    """Test enhanced image pipeline"""
    print("\n" + "=" * 70)
    print("TESTING ENHANCED IMAGE PIPELINE")
    print("=" * 70)

    try:
        import cv2
        import numpy as np
        from PIL import Image
        from extractors.ocr_extractor import OCRExtractor

        extractor = OCRExtractor()

        # Create test image
        img = np.ones((500, 800, 3), dtype=np.uint8) * 255
        cv2.putText(
            img,
            "TEST ENHANCEMENT PIPELINE",
            (100, 250),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (0, 0, 0),
            2,
        )

        pil_img = Image.fromarray(img)

        # Test normal enhancement
        result_normal = extractor._enhance_image(pil_img, aggressive=False)
        print(f"\n  Normal enhancement:")
        print(f"    - Input: {pil_img.size}, mode: {pil_img.mode}")
        print(f"    - Output: {result_normal.size}, mode: {result_normal.mode}")

        # Test aggressive enhancement
        result_aggressive = extractor._enhance_image(
            pil_img, aggressive=True, enable_deskew=True, enable_shadow_removal=True
        )
        print(f"\n  Aggressive enhancement:")
        print(f"    - Input: {pil_img.size}, mode: {pil_img.mode}")
        print(f"    - Output: {result_aggressive.size}, mode: {result_aggressive.mode}")

        print(f"\n[PASS] Enhanced image pipeline executed")
        return True
    except Exception as e:
        print(f"\n[FAIL] Enhancement pipeline test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_all_tests():
    """Run all preprocessing tests"""
    print("\n" + "=" * 70)
    print("ADIVA OCR PREPROCESSING TESTS")
    print("=" * 70)

    results = {
        "OpenCV Availability": test_opencv_availability(),
        "OCR Extractor Init": test_ocr_extractor_init(),
        "Deskew Method": test_deskew_method(),
        "Shadow Removal": test_shadow_removal_method(),
        "Background Cleanup": test_background_cleanup_method(),
        "DPI Detection": test_dpi_detection_method(),
        "Enhancement Pipeline": test_enhance_image_pipeline(),
    }

    print("\n" + "=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    run_all_tests()
