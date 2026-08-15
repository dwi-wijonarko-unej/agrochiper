# CRYPTO_METRICS.md — Analisis Kriptografi Ciphertext (EXP-003)

> Hasil analisis ciphertext yang disimpan saat EXP-002 ke
> `results/EXP-003/ciphertexts/` (9000 payload `.bin`, nama = `<request_id>.bin`).
> Analisis **offline**, replikasi fungsi enkripsi `encryption-service/app.py`.

## 1. Data & pemetaan

- Payload `.bin` = `cipher_base64` dari respons gateway → **header + ciphertext**
  (format: `II` width,height + tag `UHC`/`BLO`/`HYB` + `[I pad_len]` + ciphertext).
- `request_id` → (metode, citra sumber) dari `results/EXP-002-*/raw_batch_results.csv`
  (hanya fase `main`).
- **Sampling deterministik merata (stride)**: `--save-ciphertext-limit 300`
  di batch_runner menyimpan ~284 payload/skenario yang tersebar rata di seluruh
  urutan file (bukan 300 pertama → menghindari bias ke kelas pertama).
  Total 1136 payload (`results/EXP-003/ciphertexts/`), mencakup semua 6 kelas.
- Sampel analisis: 300 per metode (rng.seed=42).

## 2. Ringkasan (`results/EXP-003/crypto_metrics_summary.csv`)

| Metode | Entropy payload | Kor. byte adj. | Kor. row-gap | chi² stat | Uniform pass (α=.05) | Expansion |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 7.54589 | 0.11919 | 0.12796 | 12,079,299 | 20.7% | 1.000009 |
| Blowfish | 7.99990 | 0.00004 | 0.00004 | 253.5 | 94.3% | 1.000015 |
| Hybrid UHC-Blowfish | 7.99990 | -0.00001 | 0.00000 | 256.6 | 93.3% | 1.000017 |

- **UHC jauh lebih lemah** pada dataset campuran yang beragam: entropy 7.55
  (vs 7.9999 Blowfish/Hybrid), korelasi byte non-negligible (≈0.12), chi²
  statistik 12 juta dengan pass-rate uniform 20.7% — bukti nyata difusi Hill
  cipher yang buruk; ini justru menguatkan justifikasi Hybrid UHC–Blowfish.
- Entropy mendekati 8 bit/byte (maksimal) untuk Blowfish/Hybrid → korelasi byte
  ≈ 0.
- Critical value dipakai `chi2(255)@0.05 ≈ 292.98` (tanpa p-value eksak karena
  script tanpa scipy).

## 3. NPCR/UACI differential (`results/EXP-003/npcr_uaci.csv`)

Prosedur (memenuhi aturan §5.6 `CHAPTER4_PLAN.md`):
- 10 citra (2 per kelas) dari `data/experiment_dataset/`, flip **1 byte**
  (pixel (0,0), kanal R, XOR 1) → plaintext vs varian.
- Enkripsi kedua versi dengan **mode & kunci sama**; panjang ciphertext identik.
- **Blowfish/Hybrid memakai IV tetap `b"\x00"*8` pada KEDUA enkripsi** (IV bukan
  bagian perbandingan) — deviasi dari runtime `os.urandom(8)`, didokumentasikan;
  NPCR/UACI mengukur sensitivitas blok, bukan IV.

| Metode | NPCR mean (%) | UACI mean (%) |
| --- | --- | --- |
| UHC | 0.001 | 0.000 |
| Blowfish | 99.607 | 33.470 |
| Hybrid UHC-Blowfish | 99.606 | 33.467 |
| Baseline tanpa enkripsi | 0.00006 | 0.0000 |

- UHC hampir tidak sensitif terhadap flip 1 byte karena Hill cipher
  memproses blok n=16: hanya ~n byte yang berubah → NPCR ≈ 16/1572864 ≈ 0.001%.
  Ini **keterbatasan penting UHC** dalam difusi (one-byte avalanche); menjadi
  justifikasi arsitektur **Hybrid UHC–Blowfish** yang menambahkan lapisan
  Blowfish (NPCR 99.6%, dekat ideal 99.61%; UACI 33.47%, dekat ideal 33.46%).

## 4. Detail & artefak

- `results/EXP-003/crypto_metrics_detail.csv` — 900 baris (per payload):
  entropy payload & ciphertext, chi², kor. adjacent & row-gap, ukuran.
- `results/EXP-003/crypto_metrics.json` — metadata & asumsi.
- Korelasi: "adjacent" = lag 1 byte; "row-gap" = lag `3×width` (pitch baris RGB
  raster) — **bukan korelasi spasial 2D** (payload adalah blob, bukan citra).

## 5. Keterbatasan (tulis di artikel, jangan lewatkan)

1. Header (width,height,tag,pad_len) + IV Blowfish tidak terenkripsi
   (dalam payload).
2. Kunci UHC statis dari `UHC_PASSWORD2`; logistic-map non-kriptografis.
3. Blowfish: kunci dari `SECRET_KEY` variabel-oktet, CBC tanpa MAC, blok 64-bit,
   IV acak → ciphertext berbeda tiap request (bagus untuk NPCR antar-citra,
   tetapi panjang dahulu: NPCR/UACI di sini memakai IV tetap, lihat §3).
4. chi² hanya statistik keseragaman; bukan tes keacakan kriptografis kuat.
5. Sampel 300/metode untuk metrik byte; 10 citra untuk differential.

## 6. Reproduksi

```bash
# (deps: numpy, pillow, cryptography)
python analysis/crypto_metrics.py --sample 300 --npcr-images 10
```