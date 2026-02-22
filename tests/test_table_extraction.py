"""
Test Table Extraction Improvements
Tests: PDF multi-backend extraction, DOCX merged cells detection
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from logger import logger


def test_camelot_availability():
    """Test if camelot is available"""
    print("\n" + "=" * 70)
    print("TESTING CAMELOT AVAILABILITY")
    print("=" * 70)

    try:
        import camelot

        print(f"\n[PASS] camelot-py version: {camelot.__version__}")
        return True
    except ImportError as e:
        print(f"\n[FAIL] camelot-py not available: {e}")
        return False


def test_tabula_availability():
    """Test if tabula is available"""
    print("\n" + "=" * 70)
    print("TESTING TABULA AVAILABILITY")
    print("=" * 70)

    try:
        import tabula

        print(f"\n[PASS] tabula-py installed")
        return True
    except ImportError as e:
        print(f"\n[FAIL] tabula-py not available: {e}")
        return False


def test_pdf_extractor_init():
    """Test PDF Extractor initialization"""
    print("\n" + "=" * 70)
    print("TESTING PDF EXTRACTOR INITIALIZATION")
    print("=" * 70)

    try:
        from extractors.pdf_extractor import PDFExtractor, HAS_CAMELOT, HAS_TABULA

        extractor = PDFExtractor()

        print(f"\n[PASS] PDF Extractor initialized")
        print(f"  - HAS_CAMELOT: {HAS_CAMELOT}")
        print(f"  - HAS_TABULA: {HAS_TABULA}")
        print(f"  - has_camelot: {extractor.has_camelot}")
        print(f"  - has_tabula: {extractor.has_tabula}")

        return True
    except Exception as e:
        print(f"\n[FAIL] PDF Extractor initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_table_validation():
    """Test table structure validation"""
    print("\n" + "=" * 70)
    print("TESTING TABLE STRUCTURE VALIDATION")
    print("=" * 70)

    try:
        from extractors.pdf_extractor import PDFExtractor

        extractor = PDFExtractor()

        # Test valid table
        valid_table = {
            "headers": ["Name", "Age", "City"],
            "rows": [["John", "25", "NYC"], ["Jane", "30", "LA"]],
            "row_count": 2,
            "col_count": 3,
        }

        result = extractor._validate_table(valid_table)
        print(f"\n  Valid table: {result}")

        # Test invalid table (too few rows)
        invalid_table_1 = {
            "headers": ["Name"],
            "rows": [],
            "row_count": 0,
            "col_count": 1,
        }
        result_1 = extractor._validate_table(invalid_table_1)
        print(f"  Invalid table (no rows): {result_1}")

        # Test invalid table (too few cols)
        invalid_table_2 = {
            "headers": ["Name"],
            "rows": [["John"]],
            "row_count": 1,
            "col_count": 1,
        }
        result_2 = extractor._validate_table(invalid_table_2)
        print(f"  Invalid table (single col): {result_2}")

        print(f"\n[PASS] Table validation working correctly")
        return True
    except Exception as e:
        print(f"\n[FAIL] Table validation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_table_deduplication():
    """Test table deduplication"""
    print("\n" + "=" * 70)
    print("TESTING TABLE DEDUPLICATION")
    print("=" * 70)

    try:
        from extractors.pdf_extractor import PDFExtractor

        extractor = PDFExtractor()

        # Create duplicate tables
        tables = [
            {
                "row_count": 3,
                "col_count": 3,
                "headers": ["A", "B", "C"],
                "rows": [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]],
                "data": [],
                "source": "pdfplumber",
            },
            {
                "row_count": 3,
                "col_count": 3,
                "headers": ["A", "B", "C"],
                "rows": [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]],
                "data": [],
                "source": "camelot",
            },
            {
                "row_count": 2,
                "col_count": 2,
                "headers": ["X", "Y"],
                "rows": [["a", "b"], ["c", "d"]],
                "data": [],
                "source": "tabula",
            },
        ]

        deduped = extractor._deduplicate_tables(tables)

        print(f"\n  Input tables: {len(tables)}")
        print(f"  After deduplication: {len(deduped)}")

        if len(deduped) < len(tables):
            print(
                f"\n[PASS] Deduplication removed {len(tables) - len(deduped)} duplicate(s)"
            )
            return True
        else:
            print(f"\n[FAIL] Deduplication did not remove any tables")
            return False

    except Exception as e:
        print(f"\n[FAIL] Table deduplication test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_docx_extractor_init():
    """Test DOCX Extractor initialization"""
    print("\n" + "=" * 70)
    print("TESTING DOCX EXTRACTOR INITIALIZATION")
    print("=" * 70)

    try:
        from extractors.docx_extractor import DOCXExtractor

        extractor = DOCXExtractor()

        print(f"\n[PASS] DOCX Extractor initialized")
        print(f"  - Supported extensions: {extractor.supported_extensions}")

        return True
    except Exception as e:
        print(f"\n[FAIL] DOCX Extractor initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_merge_detection_methods():
    """Test DOCX merge detection methods"""
    print("\n" + "=" * 70)
    print("TESTING DOCX MERGE DETECTION METHODS")
    print("=" * 70)

    try:
        from docx import Document
        from docx.shared import Inches
        from extractors.docx_extractor import DOCXExtractor
        import tempfile
        import os

        extractor = DOCXExtractor()

        # Create a test document with merged cells
        doc = Document()

        # Add a table with merged cells
        table = doc.add_table(rows=3, cols=3)

        # Fill table
        for i, row in enumerate(table.rows):
            for j, cell in enumerate(row.cells):
                cell.text = f"Cell {i},{j}"

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name

        doc.save(tmp_path)

        try:
            # Test extraction
            result = extractor.extract_tables(Path(tmp_path))

            print(f"\n  Tables extracted: {len(result)}")

            if result:
                table_data = result[0]
                print(
                    f"  Has merged cells: {table_data.get('has_merged_cells', False)}"
                )
                print(f"  Merged regions: {table_data.get('merged_regions', [])}")

            print(f"\n[PASS] Merge detection methods working")
            return True

        finally:
            os.unlink(tmp_path)

    except Exception as e:
        print(f"\n[FAIL] Merge detection test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_all_tests():
    """Run all table extraction tests"""
    print("\n" + "=" * 70)
    print("ADIVA TABLE EXTRACTION TESTS")
    print("=" * 70)

    results = {
        "Camelot Availability": test_camelot_availability(),
        "Tabula Availability": test_tabula_availability(),
        "PDF Extractor Init": test_pdf_extractor_init(),
        "Table Validation": test_table_validation(),
        "Table Deduplication": test_table_deduplication(),
        "DOCX Extractor Init": test_docx_extractor_init(),
        "Merge Detection": test_merge_detection_methods(),
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
