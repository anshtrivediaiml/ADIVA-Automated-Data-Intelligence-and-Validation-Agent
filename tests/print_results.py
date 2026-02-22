import json
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
batch_dir = ROOT_DIR / 'outputs' / 'batch_test'

files = sorted(batch_dir.glob('*.json'))

img_labels = {
    '1wdrjd1wdrjd1wdr': 'Img-01', 'ahptfpahptfpahpt': 'Img-02',
    'clf1x4clf1x4clf1': 'Img-03', 'hmi8oxhmi8oxhmi8': 'Img-04',
    'k8s1iak8s1iak8s1': 'Img-05', 'nmtcfynmtcfynmtc': 'Img-06',
    'oohwmdoohwmdoohw': 'Img-07', 'rk6ssgrk6ssgrk6s': 'Img-08',
    'tukltxtukltxtukl': 'Img-09', 'w5avfaw5avfaw5av': 'Img-10',
    'y7jw1ty7jw1ty7jw': 'Img-11',
}

rows = []
for f in files:
    key = f.stem.split('_')[-1]
    label = img_labels.get(key, f.stem[-8:])
    with open(f, encoding='utf-8') as fh:
        d = json.load(fh)

    dtype  = d.get('document_type', 'unknown')
    lang   = d.get('language', 'unknown')
    oconf  = d.get('ocr_confidence', 0.0)
    dtcon  = d.get('document_type_confidence', 0.0)
    cc     = d.get('comprehensive_confidence', {})
    grade  = cc.get('grade', '?') if isinstance(cc, dict) else '?'
    score  = cc.get('score', 0.0) if isinstance(cc, dict) else 0.0
    sd     = d.get('structured_data', {}) or {}
    keys   = [k for k in sd.keys() if not k.startswith('_')]
    words  = d.get('word_count', 0)
    kstr   = ', '.join(keys[:5]) if keys else 'NONE'
    rows.append((label, dtype, lang, oconf, dtcon, grade, score, words, len(keys), kstr))

print()
print('='*110)
print(f"  ADIVA BATCH TEST RESULTS — {len(rows)} images")
print('='*110)
print(f"{'#':<7} {'DocType':<16} {'Lang':<8} {'OCR%':<7} {'DT%':<6} {'Grade':<10} {'Words':<7} {'Fields':<7} Top Fields")
print('-'*110)
for (label, dtype, lang, oconf, dtcon, grade, score, words, nkeys, kstr) in rows:
    g = f"{grade}({score:.2f})"
    print(f"{label:<7} {dtype:<16} {lang:<8} {oconf:<7.1f} {dtcon*100:<6.0f} {g:<10} {words:<7} {nkeys:<7} {kstr}")

print()
ok_rows = [r for r in rows if r[1] != 'other']
avg_ocr = sum(r[3] for r in rows) / len(rows)
with_struct = sum(1 for r in rows if r[8] > 0)
print(f"  Summary: {len(rows)} images | Avg OCR conf: {avg_ocr:.1f}% | Structured: {with_struct}/{len(rows)} | Classified (not 'other'): {len(ok_rows)}/{len(rows)}")
print('='*110)
