# Baseline Metrics

- Generated at: 2026-03-06 02:56:15
- Files processed: 14
- Success: 14
- Failed: 0
- Total runtime (script): 769.09s
- Avg file runtime: 54.931s
- Doc-type accuracy: N/A (no labels; add tests/baseline_expected_types.json)

## Stage Timing Averages (seconds)

- classify: 2.7812
- confidence_scoring: 0.0015
- exports: 0.6294
- extract_metadata: 0.0034
- extract_tables: 0.0000
- extract_text: 43.5803
- preprocess: 0.0943
- save_json: 0.0070
- select_extractor: 0.0000
- structured_extract: 7.8332

## Per-file Results

| File | Status | Time (s) | Actual Type | Expected Type | Type Match |
|---|---|---:|---|---|---|
| gujarati_invoice.png | success | 84.101 | invoice |  | no |
| hindi_invoice.png | success | 68.570 | invoice |  | no |
| hindi_resume.png | success | 111.309 | resume |  | no |
| Gemini_Generated_Image_1wdrjd1wdrjd1wdr.png | success | 64.136 | prescription |  | no |
| Gemini_Generated_Image_ahptfpahptfpahpt.png | success | 115.024 | bank_statement |  | no |
| Gemini_Generated_Image_clf1x4clf1x4clf1.png | success | 60.762 | marksheet |  | no |
| Gemini_Generated_Image_hmi8oxhmi8oxhmi8.png | success | 29.313 | invoice |  | no |
| Gemini_Generated_Image_k8s1iak8s1iak8s1.png | success | 26.923 | invoice |  | no |
| Gemini_Generated_Image_nmtcfynmtcfynmtc.png | success | 53.260 | land_record |  | no |
| Gemini_Generated_Image_oohwmdoohwmdoohw.png | success | 63.935 | land_record |  | no |
| Gemini_Generated_Image_rk6ssgrk6ssgrk6s.png | success | 26.098 | contract |  | no |
| Gemini_Generated_Image_tukltxtukltxtukl.png | success | 20.262 | certificate |  | no |
| Gemini_Generated_Image_w5avfaw5avfaw5av.png | success | 15.310 | utility_bill |  | no |
| Gemini_Generated_Image_y7jw1ty7jw1ty7jw.png | success | 30.025 | ration_card |  | no |
