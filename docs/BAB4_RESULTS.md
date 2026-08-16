# 3 Results and Analysis — AgroCipher Experimental Findings

> Draft Bab 4 (bagian *Results and Analysis*) untuk manuskrip
> **"Adaptive Agro-IoT Image Encryption Using Entropy and GLCM Features with a
> Hybrid UHC-Blowfish Microservices Prototype"**.
>
> Semua angka diturunkan dari eksperimen nyata pada purwarupa (EXP-001 s.d.
> EXP-004) dan dapat ditelusuri ke `results/` (raw CSV, ekspor SQLite,
> `PAPER_DATASET.csv`, `PAPER_TABLES.xlsx`, `FIGURE_DATA/`). Hasil v1 (750 citra)
> diarsipkan di `results/archive_v1/` dan TIDAK dipakai di Bab ini.
>
> **Ringkasan integritas**: seluruh 19.838 request utama (EXP-001 8.502 +
> EXP-002 11.336) berhasil (`http_status=200`, `success=1`) dan seluruhnya **lossless
> recovery** (`psnr="∞"`, `decrypt_verified=True`). Tidak ada request gagal.

---

## 3.1 Experimental Setup

Eksperimen dijalankan terhadap purwarupa microservices berjalan di lingkungan
**single-node Docker Compose** (Go gateway; Python/FastAPI feature-, selector-,
dan encryption-service; uvicorn single worker; host 3.7 GB RAM). Gateway
melindungi endpoint dengan API key 64 karakter (`GATEWAY_API_KEY`); mode
eksperimen (`EXPERIMENT_MODE`) hanya mengaktifkan header *forced method* untuk
skenario baseline, dan dinonaktifkan saat analisis.

### Dataset

Dataset eksperimen (**v2**) dibentuk dari **campuran lima sumber** citra daun
kopi yang dinormalisasi menjadi **enam kelas** dengan sampling round-robin
antar sumber (seed 42, cap 500/kelas), lalu diturunkan skalanya ke resolusi
maksimal 1024 px (RGB, JPEG q=90):

| Kelas | Jumlah | Kontribusi sumber |
| --- | --- | --- |
| Healthy | 500 | OLD 100, COF 100, DRIVE 100, ETH-test 100, ETH-aug 100 |
| Rust | 500 | OLD 100, COF 100, DRIVE 100, ETH-test 100, ETH-aug 100 |
| Miner | 500 | OLD 250, DRIVE 250 |
| Phoma | 500 | OLD 125, DRIVE 125, ETH-test 125, ETH-aug 125 |
| Red Spider Mite | 334 | OLD 167, COF 167 |
| Cerscospora | 500 | ETH-test 250, ETH-aug 250 |
| **Total** | **2834** | — |

`manifest.json` menyimpan pemetaan sumber→kelas per file (reproduksibilitas).

### Eksperimen

| ID | Tujuan | Konfigurasi | Request utama |
| --- | --- | --- | --- |
| EXP-001 | Perilaku selector (adaptive) | repeat 3, warmup 10 | 8502 (0 gagal) |
| EXP-002 | Baseline metode forced (UHC/Blowfish/Hybrid/Adaptive) | repeat 1, warmup 5 | 2834 × 4 (0 gagal) |
| EXP-003 | Kriptografi ciphertext | sampel deterministik stride 300/skenario | 1136 payload |
| EXP-004 | Load test microservices | VU 1/5/10/20, durasi 120 s, warmup 10 s | 430–604/skenario |

---

## 3.2 Feature Characteristics and Selector Decisions

### 3.2.1 Profil fitur citra

Rata-rata entropy Shannon per kelas (EXP-001):

| Kelas | Rerata entropy |
| --- | --- |
| Red Spider Mite | 7.5692 |
| Healthy | 6.4230 |
| Cerscospora | 6.0164 |
| Rust | 6.1331 |
| Phoma | 5.7387 |
| Miner | 5.2429 |

Dataset campuran memiliki rentang entropy luas (≈1.15–7.90), sehingga
menyediakan variasi karakteristik yang cukup untuk menguji keputusan adaptif.

### 3.2.2 Distribusi keputusan AI Selector

| Metode | Citra (mode) | % | Rerata entropy | Rerata kor. GLCM | Rerata kontras GLCM | Rerata ukuran (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 583 | 20.57 | 3.25 | 0.985 | 0.04 | 46.9 |
| Blowfish | 2052 | 72.41 | 6.76 | 0.984 | 0.07 | 84.4 |
| Hybrid UHC-Blowfish | 199 | 7.02 | 7.68 | 0.897 | 0.64 | 220.9 |

AI Selector (DecisionTree, `max_depth=3`, seed 42) memilih **UHC** untuk citra
berentropi rendah (≈1.15–4.78), **Blowfish** untuk entropi sedang–tinggi, dan
**Hybrid UHC-Blowfish** untuk subpopulasi entropi sangat tinggi dengan
**GLCM contrast** tinggi (>0.23). Struktur pohon terekstrak dari model:

```
entropy <= 4.78                            -> UHC
entropy > 4.78
 ├─ entropy <= 6.24                        -> Blowfish
 └─ entropy > 6.24
     ├─ glcm_contrast <= 0.23              -> Blowfish
     └─ glcm_contrast >  0.23              -> Hybrid UHC-Blowfish
```

Feature importance: `entropy = 0.869`, `glcm_contrast = 0.131`, `size_kb = 0`,
`glcm_correlation = 0`. Statistik fitur per metode terpilih tersedia pada
`results/analysis/selector_feature_summary.csv`.

**Batasan (dinyatakan eksplisit)**: label keputusan dibangkitkan rule-derived
sintetis (tidak ada ground-truth "metode terbaik" per citra), sehingga
interpretasi di atas bersifat **deskriptif-korelasional, bukan akurasi
klasifikasi**.

---

## 3.3 Encryption and Decryption Performance

Perbandingan antar metode (EXP-002, 2834 request/skenario, 100% sukses):

| Metode | Enkripsi (ms) | Dekripsi (ms) | E2E mean (ms) | E2E p95 (ms) | Cipher entropy | Lossless |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 72.4 | 59.0 | 285.5 | 440 | 7.7376 | 100% |
| Blowfish | 19.1 | 18.5 | 214.7 | 324 | 7.9999 | 100% |
| Hybrid UHC-Blowfish | 99.5 | 88.4 | 357.1 | 544 | 7.9999 | 100% |
| Adaptive | 38.8 | 31.7 | 241.3 | 405 | 7.7394 | 100% |

Temuan:
- **Blowfish paling cepat** (19.1 ms) dan menghasilkan cipher entropy tertinggi
  (7.9999); **Hybrid paling lambat** (99.5 ms) karena dua lapis transformasi.
- **Adaptive** (38.8 ms) menempuh jalan tengah — lebih cepat dari Hybrid tetapi
  lebih lambat dari Blowfish, karena 20.6% citra diarahkan ke UHC.
- Cipher entropy Adaptive/UHC (7.74) lebih rendah dari Blowfish/Hybrid (7.9999);
  cermin nyata kelemahan difusi UHC (lihat §3.4).

### Adaptive vs baseline (skor ternormalisasi)

`security_score = min-max(cipher_entropy_mean)`,
`performance_score = min-max terbalik(encryption_time + e2e_latency)`,
`combined = 0.5·security + 0.5·performance`.

| Metode | Security | Performance | Combined | Rank |
| --- | --- | --- | --- | --- |
| Blowfish | 100.0 | 100.0 | 100.0 | 1 |
| Hybrid UHC-Blowfish | 100.0 | 0.0 | 50.0 | 2 |
| Adaptive | 0.69 | 79.18 | 39.93 | 3 |
| UHC | 0.0 | 44.29 | 22.14 | 4 |

**Interpretasi jujur**: karena adaptive mengarahkan 20.6% citra ke UHC (yang
entropi ciphertext-nya rendah), skor *security* adaptif turun tajam. Hasil ini
menunjukkan **trade-off eksplisit**: adaptive menukar sedikit kualitas difusi
demi performa pada subpopulasi entropi-rendah — bukan bukti superioritas.

---

## 3.4 Ciphertext Quality and Security Indicators

### 3.4.1 Metrik byte ciphertext (EXP-003, 300 payload/metode)

| Metode | Entropy payload | Kor. byte adj. | Kor. row-gap | χ² stat | Uniform pass (α=0.05) | Expansion |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 7.5459 | 0.1192 | 0.1280 | 12,079,299 | 20.7% | 1.000009 |
| Blowfish | 7.9999 | 0.00004 | 0.00004 | 253.5 | 94.3% | 1.000015 |
| Hybrid UHC-Blowfish | 7.9999 | −0.00001 | 0.00000 | 256.6 | 93.3% | 1.000017 |

- Blowfish & Hybrid: entropy ≈ 8 bit/byte (maksimal), korelasi byte ≈ 0, dan
  distribusi histogram **mendekati seragam** (pass-rate 93–94% pada uji χ²
  terhadap distribusi uniform, critical value `χ²(255)@0.05 ≈ 292.98`).
- UHC: entropy 7.55, korelasi byte non-negligible (≈0.12), χ² statistik
  puluhan juta dengan pass-rate hanya 20.7% → **difusi Hill cipher lemah**
  pada dataset beragam.
- Payload expansion `encrypted/original ≈ 1.0000x` (overhead header + IV +
  padding PKCS7 ≤ 16 byte) pada semua metode.

### 3.4.2 Uji diferensial NPCR/UACI (1-byte flip, re-encrypt offline)

| Metode | NPCR mean (%) | UACI mean (%) |
| --- | --- | --- |
| UHC | 0.001 | 0.000 |
| Blowfish | 99.607 | 33.470 |
| Hybrid UHC-Blowfish | 99.606 | 33.467 |
| Baseline tanpa enkripsi | 0.00006 | 0.0000 |

- Blowfish & Hybrid mendekati ideal (NPCR ≈ 99.61%, UACI ≈ 33.46%).
- UHC hampir tidak sensitif terhadap perubahan 1 byte (NPCR ≈ 16/1572864)
  karena Hill cipher memproses blok n=16 → **avalanche satu-byte yang lemah**.
  Temuan ini menjadi justifikasi empiris utama arsitektur **Hybrid
  UHC–Blowfish**: lapisan Blowfish mengoreksi kelemahan difusi UHC.

> Catatan metode (didokumentasikan di `docs/CRYPTO_METRICS.md`): NPCR/UACI
> menggunakan IV Blowfish tetap (`b"\x00"*8`) pada kedua enkripsi agar panjang
> identik; runtime layanan memakai `os.urandom(8)`. Metrik byte pada sampel
> deterministik 300 payload/metode yang tersebar rata di seluruh kelas.

### 3.4.3 Fidelity dekripsi

Seluruh request (EXP-001 8.502 + EXP-002 11.336 = 19.838 request utama) menghasilkan
`decrypt_verified=True` dan PSNR `∞` → **lossless recovery rate = 100%**.
PSNR hanya membuktikan fidelity, bukan keamanan (sesuai batasan).

---

## 3.5 Discussion of Microservices-Based Adaptive Encryption

### 3.5.1 Performa layanan di bawah beban (EXP-004)

Load test terhadap 40 citra uji, durasi 120 s/skenario, 0% error di semua
skenario:

| VU | Requests | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | CPU enkripsi (%) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 430 | 3.58 | 252 | 398 | 490 | 54.3 |
| 5 | 556 | 4.63 | 1017 | 1574 | 1848 | 63.2 |
| 10 | 550 | 4.58 | 2184 | 3335 | 3719 | 66.3 |
| 20 | 604 | 5.03 | 4031 | 6656 | 8184 | 63.7 |

- **Throughput jenuh pada ≈ 4.6–5.0 req/s** (VU ≥ 5) sementara latensi terus
  membengkak hampir linear terhadap VU → bottleneck di **encryption-service**
  (CPU 54–66%; uvicorn single worker). Gateway 16–19%, feature-service 9–13%,
  selector-service ≈1–2% (lihat `service_resource_usage.csv`).
- Tidak ada request gagal bahkan pada VU=20 → layanan berperilaku *fail-safe*
  dengan degradasi latensi, bukan error.

### 3.5.2 Sintesis

Hasil eksperimen menghubungkan tiga lapisan yang menjadi celah penelitian:
(i) *image-feature-aware cipher selection* (entropy + GLCM → keputusan UHC/
Blowfish/Hybrid) terbukti berjalan konsisten dan menghasilkan distribusi
keputusan yang berarti pada dataset campuran; (ii) *hybrid UHC–Blowfish*
memberikan kualitas ciphertext terbaik dan mengoreksi difusi UHC yang lemah,
dengan overhead waktu yang jelas; dan (iii) *orchestrasi microservices*
mendukung alur ekstraksi→seleksi→enkripsi secara terpisah namun terukur, dengan
bottleneck yang teridentifikasi pada encryption-service. Seluruh hasil bersifat
deskriptif-komparatif pada purwarupa single-node; **tidak ada klaim akurasi
selector, keamanan kriptografis penuh, maupun skalabilitas horizontal**.

---

## 3.6 Reproducibility

- Commit audit: `34f9a398dbcc31e714cdceebdd5481aafc15b940`; versi container
  sebagaimana `docker compose ps`; seluruh metrik bereferensi `request_id`
  (join antara CSV batch, SQLite `data/experiment/*`, dan payload EXP-003).
- Parameter: dataset v2 (2834 citra, seed 42, cap 500/kelas, max-dim 1024);
  EXP-001 repeat 3; EXP-002 repeat 1; EXP-003 sampel stride 300/skenario;
  EXP-004 VU 1/5/10/20, 120 s. `.env` di-git-ignore (API key 64-char acak).
- Artefak analisis: `results/PAPER_DATASET.csv`, `results/PAPER_TABLES.xlsx`,
  `results/PAPER_SUMMARY.md`, `results/FIGURE_DATA/*.csv`,
  `results/analysis/*.csv`, `results/EXP-004/*`.

## Limitations (ringkasan untuk §5/Conclusion)

1. Tanpa ground-truth label "metode terbaik" per citra → evaluasi selector
   dibatasi pada decision behavior, bukan akurasi.
2. Kunci UHC statis (`UHC_PASSWORD2`) & logistic-map non-kriptografis; Blowfish
   CBC tanpa MAC, blok 64-bit; header payload tidak terenkripsi.
3. Load test single-node (uvicorn single worker), bukan cluster/Kubernetes.
4. Korelasi "row-gap" = lag baris raster (bukan korelasi spasial 2D); χ² tanpa
   p-value eksak (tanpa scipy).