# SELECTOR_ANALYSIS.md — Evaluasi Perilaku AI Selector (Deskriptif)

> Ringkasan temuan EXP-001/EXP-002 untuk subbab 4.2 & 4.4.
> **Bukan** klaim akurasi: label keputusan dibangkitkan rule-derived sintetis
> (seed 42) karena tidak ada ground-truth "metode terbaik" per citra. Lihat
> `EXPERIMENT_AUDIT.md` §"Klaim yang boleh/tidak boleh".

## 1. Model

- DecisionTreeClassifier `max_depth=3`, `random_state=42`, fitur
  `[entropy, size_kb, glcm_correlation, glcm_contrast]`, label `{0:UHC,
  1:Blowfish, 2:Hybrid UHC-Blowfish}`.
- Model dilatih otomatis di container pada startup (pkl sintetis, tidak di git).
- Struktur pohon ekspor: `results/analysis/decision_tree.txt` (ringkasan):

```
|--- entropy <= 4.78                        -> UHC
|--- entropy >  4.78
|   |--- entropy <= 6.24                    -> Blowfish
|   |--- entropy >  6.24
|       |--- glcm_contrast <= 0.23          -> Blowfish
|       |--- glcm_contrast >  0.23          -> Hybrid UHC-Blowfish
```

- Feature importance (`results/analysis/feature_importance.csv`):
  `entropy=0.869`, `glcm_contrast=0.131`, `size_kb=0`, `glcm_correlation=0`
  — konsisten dengan struktur pohon (pemisah utama entropy; kontras hanya
  memisahkan cabang Hybrid).

## 2. Distribusi pilihan (EXP-001, 2834 citra, repeat=3)

`results/analysis/selector_distribution.csv`:

| Metode | Citra (mode) | % | Rerata entropy | Rerata kor. GLCM | Rerata kontras GLCM | Rerata size_kb |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 583 | 20.57 | 3.25 | 0.985 | 0.04 | 46.9 |
| Blowfish | 2052 | 72.41 | 6.76 | 0.984 | 0.07 | 84.4 |
| Hybrid UHC-Blowfish | 199 | 7.02 | 7.68 | 0.897 | 0.64 | 220.9 |

- **Interpretasi deskriptif**: dataset campuran (6 kelas, 5 sumber) memberi
  distribusi keputusan yang jauh lebih seimbang daripada run v1 (UHC 0.13% →
  20.57%): porsi signifikan citra berentropi rendah dipilih UHC; citra
  bertekstur/kontras tinggi dipilih Hybrid. Tafsir ini KORELASI, bukan
  kausalitas (aturan §5.9 di `CHAPTER4_PLAN.md`).
- Cipher entropy rata-rata per metode terpilih: UHC 6.73 (rendah!), Blowfish
  dan Hybrid 7.9999 — konsisten dengan temuan kripto EXP-003 (UHC lemah).

## 3. Perbandingan metode (EXP-002, 2834 request/skenario, semua sukses)

`results/analysis/method_comparison.csv`:

| Metode | Enkripsi (ms) | Dekripsi (ms) | E2E mean (ms) | E2E p95 (ms) | Cipher entropy | Lossless |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 72.4 | 59.0 | 285.5 | 440 | 7.7376 | 100% |
| Blowfish | 19.1 | 18.5 | 214.7 | 324 | 7.9999 | 100% |
| Hybrid UHC-Blowfish | 99.5 | 88.4 | 357.1 | 544 | 7.9999 | 100% |
| Adaptive | 38.8 | 31.7 | 241.3 | 405 | 7.7394 | 100% |

- Semua request `decrypt_verified=True`, PSNR `∞` → **lossless recovery rate
  100%** di semua skenario.
- Cipher entropy UHC & Adaptive jelas di bawah Blowfish/Hybrid (7.74 vs 7.9999)
  — cermin nyata dari kelemahan difusi UHC (lihat `docs/CRYPTO_METRICS.md`).
- Expansion payload `encrypted/original` ≈ 1.0000x (overhead header + padding
  PKCS7 + IV ≤ 16 byte).
- Catatan: ekspor ukuran payload dari DB enkripsi (`experiment_encryption.csv`,
  join `request_id`); kolom sizes tidak ada di `raw_batch_results.csv`.

## 4. Adaptive vs baseline (skor ternormalisasi)

`results/analysis/adaptive_vs_baseline.csv` — rumus persis:

- `security_score = 100 · (E − E_min)/(E_max − E_min)` dengan
  `E` = cipher entropy rata-rata per metode.
- `performance_score = 100 · (C_max − C)/(C_max − C_min)` dengan
  `C` = mean(encryption_time_ms) + mean(end_to_end_latency_ms).
- `combined_score = 0.5·security_score + 0.5·performance_score`.
- `rank`: 1 = tertinggi.

| Metode | Security | Performance | Combined | Rank |
| --- | --- | --- | --- | --- |
| Blowfish | 100.0 | 100.0 | 100.0 | 1 |
| Hybrid UHC-Blowfish | 100.0 | 0.0 | 50.0 | 2 |
| Adaptive | 0.69 | 79.18 | 39.93 | 3 |
| UHC | 0.0 | 44.29 | 22.14 | 4 |

**Cara membaca (hati-hati)**: karena adaptive memilih UHC untuk 20.6% citra,
rata-rata cipher entropy adaptive turun (7.74) sehingga `security_score`
adaptif rendah (0.69) — trade-off yang JELAS terlihat, bukan bukti
superioritas. Hasil ini justru menguatkan narasi: adaptive menukar sedikit
keamanan difusi demi performa pada subpopulasi entropi-rendah. Tulis sebagai
hasil deskriptif; jangan klaim akurasi.

## 5. Input & reproduksi

```bash
# (deps: numpy, scikit-learn, joblib)
python analysis/analyze_selector.py --exp1 results/EXP-001/raw_batch_results.csv
# membaca juga results/EXP-002-*/raw_batch_results.csv + analysis/models/ai_selector_model.pkl
```

Artefak:
- `results/analysis/selector_distribution.csv`
- `results/analysis/selector_feature_summary.csv`
- `results/analysis/method_comparison.csv`
- `results/analysis/adaptive_vs_baseline.csv`
- `results/analysis/feature_importance.csv`, `decision_tree.txt`, `model_params.json`
