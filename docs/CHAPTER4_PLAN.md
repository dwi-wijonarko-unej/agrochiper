# CHAPTER4_PLAN.md — Rencana Penyusunan Bab 4 Manuskrip

> Judul artikel: **"A Microservices Prototype for Adaptive Agro-IoT Image Encryption:
> Integrating Entropy and GLCM Features with Hybrid UHC-Blowfish"**
>
> Dokumen ini adalah rencana kerja (bukan naskah jadi) untuk menulis **Bab 4 — Hasil
> dan Pembahasan** berdasarkan data yang dikumpulkan lewat eksperimen EXP-001 s.d.
> EXP-004. Premis metodologi mengikuti temuan `EXPERIMENT_AUDIT.md` dan
> instrumentasi `docs/EXPERIMENT_DATA.md`: evaluasi dibatasi pada *decision behavior*
> (bukan akurasi), dan fidelity dibuktikan lewat *lossless recovery rate*.

---

## 1. Tujuan Bab 4

Bab 4 harus menjawab empat pertanyaan penelitian (RQ):

1. **RQ1** — Bagaimana profil fitur (entropy, GLCM correlation, GLCM contrast,
   ukuran/resolusi) citra penyakit kopi pada dataset yang digunakan?
2. **RQ2** — Bagaimana AI Selector berperilaku: distribusi pilihan UHC/Blowfish/
   Hybrid, dan bagaimana keputusan itu berkorelasi dengan fitur masukan?
3. **RQ3** — Bagaimana kualitas kripto dan fidelity: entropy ciphertext, korelasi
   byte, NPCR/UACI (bila asumsi terpenuhi), payload expansion, dan lossless
   recovery — untuk Adaptive vs UHC-only vs Blowfish-only vs Hybrid-only?
4. **RQ4** — Bagaimana performa prototipe microservices: latency end-to-end
   (p50/p95/p99), throughput, error rate, dan resource CPU/RAM per container?

---

## 2. Pemetaan Data → Subbab

| Subbab | Sumber data | File utama |
| --- | --- | --- |
| 4.1 Profil dataset | EXP-001 metadata + fitur | `results/EXP-001/run_metadata.json`, `raw_batch_results.csv` |
| 4.2 Perilaku AI Selector | EXP-001 (adaptive) | `analysis/...`, `selector_distribution.csv`, `selector_feature_summary.csv` |
| 4.3 Fidelity & keamanan kripto | EXP-002 (forced) + EXP-003 | `method_comparison.csv`, `crypto_metrics_*.csv` |
| 4.4 Perbandingan Adaptive vs baseline | EXP-002 | `adaptive_vs_baseline.csv` |
| 4.5 Performa microservices | EXP-004 | `load_test_*.csv/csv`, `service_resource_usage.csv` |
| 4.6 Reproduksibilitas | semua metadata | `run_metadata.json`, git commit, versi container |

---

## 3. Alur Eksekusi Eksperimen (berurutan)

Prasyarat: `.env` ada (`GATEWAY_API_KEY` 64 karakter), stack berjalan.

```bash
# 0) Build & run stack
docker compose up -d --build
curl localhost:8080/health

# 1) EXP-001 — perilaku selector (adaptive, warmup 10, repeat 3) pada dataset
python client/batch_runner.py <DATASET> \
  --experiment-id EXP-001 --warmup 10 --repeat 3 --resume

# 2) EXP-002 — baseline forced method (4 skenario, dataset & setup sama)
export EXPERIMENT_MODE=true   # set di .env lalu: docker compose up -d gateway
python client/batch_runner.py <DATASET> --experiment-id EXP-002-UHC \
  --warmup 10 --repeat 3 --force-rerun \
  --extra-header "X-Experiment-Force-Method: UHC"      # header diimplementasikan di runner
python client/batch_runner.py <DATASET> --experiment-id EXP-002-Blo --force-rerun ... "Blowfish"
python client/batch_runner.py <DATASET> --experiment-id EXP-002-Hyb --force-rerun ... "Hybrid UHC-Blowfish"
python client/batch_runner.py <DATASET> --experiment-id EXP-002-Ada --force-rerun ... "adaptive"

# 3) EXP-003 — metrik kriptografi offline (ciphertext yang disimpan saat EXP-002)
python analysis/crypto_metrics.py --input results/EXP-002/... --out results/EXP-003

# 4) EXP-004 — load test (k6/Locust) di staging, bukan produksi
#    skenario 1/5/10/20 virtual users, warmup 30s, test 2m, ramp-down 15s

# 5) Ekspor log eksperimen ke CSV
python analysis/export_experiment_data.py --db-dir data/experiment --out-dir results/exported

# 6) Generasi tabel artikel
python analysis/analyze_selector.py ...    # EXP-001/002 → tabel A/B/E
python analysis/build_paper_tables.py ...  # → PAPER_DATASET.csv, PAPER_TABLES.xlsx, PAPER_SUMMARY.md
```

> Catatan: `--extra-header` untuk memaksa metode belum diimplementasikan di
> batch_runner saat dokumen ini ditulis; bisa langsung memakai
> `curl -H "X-Experiment-Force-Method: UHC" ...` untuk pengujian manual, atau
> tambahkan flag kecil ke runner (non-intrusif).

---

## 4. Rancangan Tabel (placeholder, penomoran T4.x)

| # Tabel | Nama | Isi inti | Sumber |
| --- | --- | --- | --- |
| T4.1 | Dataset_Profile | N citra, kelas penyakit, format, resolusi, ukuran (min/mean/max) | run_metadata + CSV |
| T4.2 | Feature_Statistics | N, mean±SD, median, IQR, min/max tiap fitur per metode terpilih | selector_feature_summary |
| T4.3 | Selector_Distribution | frekuensi & % UHC/Blowfish/Hybrid + means | selector_distribution |
| T4.4 | Method_Comparison | time, entropy, PSNR/lossless, payload expansion per method | method_comparison |
| T4.5 | Crypto_Security | korelasi byte (H/V/D), NPCR, UACI, chi-square bila valid | crypto_metrics_summary |
| T4.6 | Microservices_Performance | throughput, p50/p95/p99, error rate, CPU/RAM per skenario | load_test_summary |
| T4.7 | Error_Analysis | jumlah & jenis kegagalan per eksperimen | experiment_failures |
| T4.8 | Reproducibility_Metadata | commit, compose config, versi, checksum dataset | run_metadata |

### Rancangan Gambar (placeholder, penomoran F4.x)

- F4.1 Distribusi entropy & GLCM contrast vs decision code (strip/hexbin).
- F4.2 Decision tree selector: tampilan pohon (text + PNG/SVG) dengan batas
  pemisah & feature importance.
- F4.3 Encryption/decryption time per method (boxplot, log-scale bila perlu).
- F4.4 Cipher entropy per method (boxplot/error bar).
- F4.5 Latency p50/p95(p99) per skenario beban.
- F4.6 Success/error rate per skenario beban; contoh histogram ciphertext.

---

## 5. Prosedur Analisis per Metrik (aturan wajib)

1. **N jelas**: setiap tabel mencantumkan N (jumlah baris) dan filter
   (sukses/gagal). Metrik agregat **hanya dari request sukses**; failure rate
   dilaporkan terpisah.
2. **Terminologi fidelity**: jangan rata-rata PSNR; laporkan **lossless recovery
   rate** = `decrypt_verified == 1` (atau `psnr_is_infinite == 1`) probabilitas.
   Uraikan pembatasan: PSNR hanya membuktikan recovery, tidak keamanan.
3. **Outlier**: jangan hapus diam-diam; jika dihapus, buat kolom `is_outlier` +
   dokumentasi aturan (mis. |z|>3 atau IQR 1.5×), laporkan dampaknya.
4. **Skew**: untuk waktu/latensi gunakan median + IQR, bukan hanya mean±SD.
5. **Infinity PSNR**: jangan substitusi angka arbitrer; kolom `psnr_is_infinite`
   + proporsinya.
6. **NPCR/UACI**: hanya bila dua ciphertext memiliki panjang/format byte sama dan
   dibangkitkan dengan mode + key yang sama. Karena UHC deterministik dan
   Blowfish memakai IV acak, uji differential untuk Blowfish memerlukan IV tetap
   yang didokumentasikan; jika tidak dapat dipenuhi, **jangan laporkan**, tulis
   keterbatasan.
7. **Korelasi ciphertext**: hitung pada representasi byte (bukan pixel citra)
   karena payload adalah blob; jelaskan tingkat (horizontal = byte posisi
   berurutan).
8. **Normalisasi skor** (adaptive_vs_baseline): definisikan eksplisit, mis.
   `security_score = min-max-normalize(cipher_entropy)` dan
   `performance_score = normalisasi terbalik(encryption_time + latency)`,
   `combined = 0.5·security + 0.5·performance`; tulis rumus persis pada
   `docs/SELECTOR_ANALYSIS.md` agar reproducible.
9. **Kausalitas dilarang**: dari distribusi fitur dan keputusan hanya boleh
   inferensi korelasi/deskriptif, bukan klaim "fitur X menyebabkan pemilihan".

---

## 6. Konten yang Harus Ditulis (draf outline per subbab)

### 4.1 Profil Dataset
- Sumber data, jumlah citra, struktur folder (kelas = label), format & resolusi,
  ukuran file; tabel T4.1 + F4.1.

### 4.2 Perilaku AI Selector
- Deskripsi DecisionTree (max_depth=3, fitur 4, label rule-derived).
- Distribusi pilihan (T4.3), fitur per kelas (T4.2), feature importance (F4.2).
- Batasan: selector adalah *rule-derived placeholder*, evaluasi = decision
  behavior, bukan akurasi (tidak ada ground truth).

### 4.3 Fidelity & Keamanan Kripto
- Lossless recovery rate per metode (EXP-001/002).
- Cipher entropy, korelasi byte, NPCR/UACI, chi-square bila valid (EXP-003).
- Payload expansion (`encrypted/original`).
- Batasan keamanan jujur (kunci UHC statis, Blowfish CBC tanpa MAC, blok 64-bit,
  metadata header tidak terenkripsi).

### 4.4 Adaptive vs Baseline
- Tabel E adaptive_vs_baseline + analisis trade-off security/performance.
- Klaim harus hati-hati: bukti "nilai tambah selector" = perbedaan outcome,
  bukan akurasi.

### 4.5 Performa Microservices
- Throughput, latency e2e p50/p95/p99 tiap skenario, error rate, CPU/RAM
  (T4.6, F4.5, F4.6).
- Nyatakan konteks: **containerized microservices prototype, single-node
  (Docker Compose, uvicorn single worker); bukan Kubernetes**
  → batasi klaim skalabilitas.

### 4.6 Reproduksibilitas
- commit hash, versi container/library, checksum daftar file dataset, parameter
  eksperimen (warmup/repeat/concurrency), spesifikasi host.

---

## 7. Klaim yang BOLEH vs TIDAK BOLEH (dari audit)

### Boleh
- "Keputusan selector mengikuti pola berbasis entropy/kontras (deskriptif)."
- "Seluruh N citra didekripsi **lossless** (recovery rate = X%, PSNR = ∞)."
- "Hybrid UHC–Blowfish menunjukkan latency/entropy trade-off sbb (perbandingan
  deskriptif pada setup yang sama)."
- "Prototipe microservices berjalan di lingkungan container 1-node dengan
  throughput/latensi sbb pada skenario beban yang diuji."
- "Perbandingan Adaptive vs baseline dilakukan pada dataset & konfigurasi yang
  identik, dengan frekuensi pemilihan metode X%."

### Tidak boleh
- "Akurasi selector ≥ 85%" (tidak ada ground truth & train/test split).
- "UHC aman secara kriptografis" (kunci statis, linier, logistic map non-kriptografis).
- "Skalabel horizontal / Kubernetes" (belum diimplementasi/diuji).
- "PSNR rata-rata membuktikan keamanan" (hanya fidelity).
- Klaim kausal dari distribusi fitur → keputusan.

---

## 8. Checklist Penyelesaian Bab 4

- [x] Dataset akhir disetujui (v2: 2834 citra; campuran 5 sumber → 6 kelas
  ternormalisasi: Healthy/Rust/Miner/Phoma/Red Spider Mite/Cerscospora;
  cap 500/kelas round-robin, seed 42; `data/experiment_dataset_v2/` + `manifest.json`).
- [x] EXP-001 selesai (`results/EXP-001/raw_batch_results.csv` + `run_metadata.json`).
- [x] EXP-002 4 skenario selesai; `method_comparison.csv` dihasilkan
  (`results/analysis/method_comparison.csv`).
- [x] EXP-003 dijalankan & asumsi NPCR/UACI didokumentasikan
  (`results/EXP-003/*`, `docs/CRYPTO_METRICS.md`) — valid dengan IV tetap;
  ciphertext disimpan via sampling stride merata (`--save-ciphertext-limit 300`, ~2GB).
- [x] EXP-004 pada staging; CPU/RAM & error log container dikumpulkan
  (`results/EXP-004/load_test_summary.csv`, `service_resource_usage.csv`).
- [x] Semua log diekspor (`results/exported/experiment_*.csv`).
- [x] Tabel T4.1–T4.5, T4.7, T4.8 & gambar F4.1–F4.4 siap
  (`results/PAPER_TABLES.xlsx`, `results/FIGURE_DATA/`, `results/PAPER_SUMMARY.md`)
  — angka dapat ditelusuri ke raw.
- [x] T4.6 Microservices_Performance & F4.5/F4.6 (dari EXP-004;
  `docs/BAB4_RESULTS.md` §3.5).
- [x] Bagian limitation (keamanan, akurasi, skalabilitas) di-draf
  (`docs/SELECTOR_ANALYSIS.md`, `docs/CRYPTO_METRICS.md`, `PAPER_SUMMARY.md`,
  `docs/BAB4_RESULTS.md`).
- [ ] Bagian reproduksibilitas lengkap (commit, checksum, versi) — sebagian:
  commit tercatat di T4.8, checksum dataset/manifest perlu divalidasi.