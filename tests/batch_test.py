"""
ADIVA - Batch Test Script
Runs extraction on all images in test_images/ and prints a summary table.
"""
import sys
import os
import json
import time
from pathlib import Path

# Resolve paths relative to project root (one level above tests/)
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / 'backend'))

from extractor import DocumentExtractor

TEST_DIR = ROOT_DIR / 'test_images'
OUTPUT_DIR = ROOT_DIR / 'outputs' / 'batch_test'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

extractor = DocumentExtractor()

images = sorted(TEST_DIR.glob('*.png')) + sorted(TEST_DIR.glob('*.jpg')) + sorted(TEST_DIR.glob('*.jpeg'))

print(f"\n{'='*80}")
print(f"  ADIVA BATCH TEST — {len(images)} images")
print(f"{'='*80}\n")

results = []

for i, img_path in enumerate(images, 1):
    print(f"[{i}/{len(images)}] Processing: {img_path.name}")
    start = time.time()
    try:
        result = extractor.extract(str(img_path))
        elapsed = time.time() - start

        doc_type   = result.get('document_type', 'unknown')
        dt_conf    = result.get('document_type_confidence', 0.0)
        lang       = result.get('language', 'unknown')
        ocr_conf   = result.get('ocr_confidence', 0.0)
        word_count = result.get('word_count', 0)
        has_struct = bool(result.get('structured_data'))
        struct_keys = list(result.get('structured_data', {}).keys()) if has_struct else []
        overall    = result.get('comprehensive_confidence', {})
        grade      = overall.get('grade', 'N/A') if isinstance(overall, dict) else 'N/A'
        score      = overall.get('score', 0.0) if isinstance(overall, dict) else 0.0

        # Save individual JSON output
        out_file = OUTPUT_DIR / f"{img_path.stem}.json"
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        results.append({
            'file': img_path.name,
            'doc_type': doc_type,
            'dt_conf': dt_conf,
            'lang': lang,
            'ocr_conf': ocr_conf,
            'words': word_count,
            'struct': has_struct,
            'struct_keys': struct_keys,
            'grade': grade,
            'score': score,
            'time': elapsed,
            'error': None
        })

        struct_summary = f"{len(struct_keys)} fields: {', '.join(struct_keys[:5])}" if has_struct else "None"
        print(f"  ✅ Type={doc_type} ({dt_conf*100:.0f}%), Lang={lang}, OCR={ocr_conf:.1f}%, Words={word_count}, Grade={grade}({score:.2f}), Struct=[{struct_summary}], Time={elapsed:.1f}s")

    except Exception as e:
        elapsed = time.time() - start
        results.append({'file': img_path.name, 'error': str(e), 'time': elapsed})
        print(f"  ❌ ERROR: {e}")

# Final summary table
print(f"\n{'='*80}")
print(f"  SUMMARY TABLE")
print(f"{'='*80}")
print(f"{'#':<3} {'File':<42} {'Type':<16} {'Lang':<8} {'OCR%':<8} {'Grade':<8} {'Struct':<7} {'Time':<6}")
print(f"{'-'*3} {'-'*42} {'-'*16} {'-'*8} {'-'*8} {'-'*8} {'-'*7} {'-'*6}")

for i, r in enumerate(results, 1):
    if r.get('error'):
        print(f"{i:<3} {r['file'][:41]:<42} {'ERROR':<16} {'':8} {'':8} {'':8} {'':7} {r['time']:.1f}s")
    else:
        struct_mark = '✅' if r['struct'] else '❌'
        print(f"{i:<3} {r['file'][:41]:<42} {r['doc_type']:<16} {r['lang']:<8} {r['ocr_conf']:<8.1f} {r['grade']+'('+str(round(r['score'],2))+')':<8} {struct_mark:<7} {r['time']:.1f}s")

# Stats
ok = [r for r in results if not r.get('error')]
errors = [r for r in results if r.get('error')]
avg_ocr = sum(r['ocr_conf'] for r in ok) / len(ok) if ok else 0
avg_time = sum(r['time'] for r in results) / len(results) if results else 0
with_struct = sum(1 for r in ok if r['struct'])

print(f"\n{'='*80}")
print(f"  STATS: {len(ok)}/{len(images)} OK | {len(errors)} errors | Avg OCR conf: {avg_ocr:.1f}% | Struct extracted: {with_struct}/{len(ok)} | Avg time: {avg_time:.1f}s/img")
print(f"  Output JSONs saved to: {OUTPUT_DIR.absolute()}")
print(f"{'='*80}\n")
