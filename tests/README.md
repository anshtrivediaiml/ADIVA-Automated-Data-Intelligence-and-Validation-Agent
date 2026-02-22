# ADIVA — Tests

All test scripts live in this folder. Run any of them from the **project root**:

```bash
# Single-file tests
python tests/test_extraction.py
python tests/test_ocr.py
python tests/test_ocr_extraction.py
python tests/test_ai_extraction.py
python tests/test_exports.py
python tests/test_multilang_setup.py

# API test (requires API running on localhost:8000)
python tests/test_api.py

# Batch test against test_images/ folder
python tests/batch_test.py

# Print results from last batch test
python tests/print_results.py

# Generate synthetic test documents
python tests/generate_test_docs.py
```

## File Descriptions

| File | Purpose |
|------|---------|
| `batch_test.py` | Runs extraction on all images in `test_images/` and prints a summary table |
| `print_results.py` | Pretty-prints JSON results from the last batch test run |
| `test_extraction.py` | Tests basic document extraction pipeline |
| `test_ocr.py` | Tests Tesseract OCR setup |
| `test_ocr_extraction.py` | Tests OCR on scanned document samples |
| `test_ai_extraction.py` | Tests full AI-powered extraction pipeline |
| `test_exports.py` | Tests Excel, CSV, HTML export generation |
| `test_multilang_setup.py` | Tests multi-language (Hindi/Gujarati) OCR support |
| `test_api.py` | Integration tests for all REST API endpoints |
| `generate_test_docs.py` | Generates synthetic PDF/image test documents |

> **Note:** All paths are resolved relative to the project root automatically.
