Untuk mendapatkan data yang dibutuhkan dalam artikel ini, prompt apa yang harus saya tulis kepada agent llm saya di repository code aplikasi saya

Berikut kumpulan prompt yang bisa Anda berikan ke coding agent (misalnya di Cursor, Copilot, atau agent lain di repository code Anda) untuk menghasilkan setiap jenis data yang dibutuhkan artikel, disusun mengikuti lima tahap metodologi pada proposal.

## Tahap 1: Persiapan Dataset dan Ekstraksi Fitur

```
Buatkan script Python untuk:
1. Memuat 1.000 citra penyakit kopi dari folder dataset/, resize ke 512x512, dan normalisasi pixel value ke rentang 0-1.
2. Ekstrak fitur dari setiap citra: entropi Shannon, ukuran file (byte), dan tekstur GLCM (mean, contrast) menggunakan skimage.feature.graycomatrix.
3. Simpan hasil ekstraksi fitur ke file CSV dengan kolom: filename, label_penyakit, entropy, file_size, glcm_mean, glcm_contrast.
4. Tampilkan statistik deskriptif (min, max, mean, std) untuk setiap fitur, dikelompokkan per label penyakit (leaf rust vs anthracnose).
Gunakan library OpenCV, skimage, dan pandas. Sertakan logging progres tiap 100 citra.
```

## Tahap 2: Implementasi dan Evaluasi Cipher (UHC, Blowfish, Hybrid)

```
Implementasikan tiga skema enkripsi citra di Python:
1. Unimodular Hill Cipher (UHC) dengan matriks kunci 3x3 berdeterminan ±1, untuk operasi pixel shuffling.
2. Blowfish 16-round Feistel (gunakan library pycryptodome) untuk operasi substitusi blok.
3. Hybrid UHC-Blowfish: UHC untuk shuffling posisi piksel, lalu Blowfish untuk substitusi nilai piksel.

Untuk setiap skema, hitung dan simpan ke CSV:
- PSNR dan SSIM (bandingkan citra asli vs citra terenkripsi-didekripsi ulang)
- Entropi citra hasil enkripsi
- Korelasi piksel horizontal/vertikal/diagonal
- Waktu enkripsi dan dekripsi (dalam milidetik)
- Data histogram (untuk divisualisasikan sebagai grafik pemerataan)

Jalankan pada seluruh 1.000 citra dataset, simpan hasil per citra dan agregat rata-rata per skema ke file cipher_evaluation.csv.
```

## Tahap 3: Pengembangan Model AI Selector (Decision Tree)

```
Buatkan pipeline machine learning menggunakan scikit-learn untuk:
1. Memuat fitur dari features.csv (entropy, file_size, glcm_mean, glcm_contrast).
2. Membuat label target "cipher_optimal" (UHC/Blowfish/Hybrid) berdasarkan skema mana yang menghasilkan PSNR tertinggi dan waktu enkripsi tercepat dari cipher_evaluation.csv (gabungkan dengan logika threshold atau skor komposit).
3. Split data 80:20 train-test dengan random_state tetap untuk reproducibility.
4. Latih model DecisionTreeClassifier, lakukan hyperparameter tuning (max_depth, min_samples_split) dengan GridSearchCV.
5. Evaluasi: akurasi, confusion matrix, classification report (precision/recall/F1), dan feature importance.
6. Ekspor visualisasi pohon keputusan (plot_tree) dan simpan model terlatih (.pkl).
Simpan semua metrik evaluasi ke model_evaluation.csv dan simpan gambar confusion matrix serta feature importance sebagai PNG.
```

## Tahap 4: Simulasi Arsitektur Microservices (Load Testing)

```
Buatkan skenario load testing untuk arsitektur microservices AI Selector menggunakan Docker Compose (mensimulasikan Kubernetes secara lokal):
1. Deploy service: ai-selector-service (menerima fitur citra, mengembalikan keputusan cipher), encryption-service (UHC/Blowfish/Hybrid), dan gateway.
2. Gunakan Locust atau k6 untuk mensimulasikan 1.000 request citra secara bertahap (10, 50, 100, 500, 1000 concurrent requests).
3. Ukur dan catat: throughput (images/detik), latency rata-rata dan p95 (ms), penggunaan CPU dan memori tiap container (gunakan docker stats atau cAdvisor).
4. Simpan hasil pengujian ke load_test_results.csv dengan kolom: concurrent_users, throughput, avg_latency, p95_latency, cpu_usage, memory_usage.
```

## Tahap 5: Pengujian Keamanan (Security Testing)

```
Buatkan script pengujian keamanan untuk hasil enkripsi UHC, Blowfish, dan Hybrid:
1. Differential attack test: ubah 1 pixel pada citra asli, enkripsi ulang, lalu hitung NPCR (Number of Pixels Changed Rate) dan UACI (Unified Average Changing Intensity) dibanding hasil enkripsi citra asli.
2. Noise robustness test: tambahkan Gaussian noise dan salt-and-pepper noise pada citra terenkripsi, lalu ukur PSNR hasil dekripsi setelah noise.
3. Brute force simulation: estimasi keyspace masing-masing cipher dan waktu brute force teoretis berdasarkan kecepatan komputasi standar (laporkan sebagai analisis teoretis, bukan simulasi penuh).
Simpan semua metrik ke security_test_results.csv dengan kolom skema, NPCR, UACI, PSNR_after_noise, keyspace_estimate.
```

## Prompt Tambahan: Konsolidasi Data untuk Artikel

```
Buatkan script yang menggabungkan seluruh file CSV (features.csv, cipher_evaluation.csv, model_evaluation.csv, load_test_results.csv, security_test_results.csv) menjadi satu ringkasan tabel per bagian Hasil & Pembahasan artikel. Buat juga chart Plotly untuk:
1. Perbandingan PSNR/SSIM antar skema cipher (bar chart)
2. Confusion matrix Decision Tree (heatmap)
3. Feature importance (bar chart horizontal)
4. Throughput vs concurrent users (line chart)
5. NPCR/UACI antar skema (bar chart)
Ekspor semua chart sebagai PNG resolusi tinggi untuk dimasukkan ke draft artikel.
```

**Catatan penggunaan**: jalankan prompt secara berurutan (Tahap 1 → 5) karena output tiap tahap menjadi input tahap berikutnya. Sesuaikan nama file/folder dengan struktur repository Anda sebelum menempelkan prompt ke coding agent.


