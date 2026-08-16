<Right># Kerangka Artikel Ilmiah: A Decision Tree-Based Adaptive AI Selector for Hybrid Encryption Algorithm Selection on Coffee Disease Images in Edge-Cloud Architecture

Kerangka ini disusun berdasarkan proposal hibah "Orkestrasi Microservices Berbasis AI Selector untuk Enkripsi Citra Penyakit Kopi dengan Hybrid Unimodular Hill Cipher-Blowfish" yang menjadi dasar luaran artikel. Struktur mengikuti format artikel ilmiah standar (IEEE/Sinta 2): Abstrak, Pendahuluan, Tinjauan Pustaka, Metodologi, Hasil dan Pembahasan, Kesimpulan.[^1]

## Judul dan Abstrak

Judul artikel menegaskan tiga elemen inti: Decision Tree sebagai model AI Selector, hybrid encryption (Unimodular Hill Cipher/UHC dan Blowfish), serta konteks aplikasi citra penyakit kopi pada arsitektur edge-cloud. Abstrak sebaiknya memuat: (1) latar belakang urgensi keamanan citra agro-IoT, (2) gap penelitian pada seleksi cipher statis, (3) metode AI Selector berbasis fitur citra (entropi, ukuran, tekstur GLCM), (4) hasil kuantitatif utama (akurasi klasifikasi, PSNR, SSIM, throughput/latency), dan (5) kontribusi terhadap paradigma AI-driven cipher selection dalam ekosistem Industry 5.0 pertanian.[^1]

## I. Pendahuluan

### A. Latar Belakang dan Konteks Domain
- Posisi Indonesia sebagai produsen kopi terbesar keempat dunia dan kontribusi Jawa Timur/Jember sebesar 70% pada varietas Arabika-Robusta.[^1]
- Ancaman penyakit leaf rust (Hemileia vastatrix) dan anthracnose yang menimbulkan kerugian ekonomi hingga Rp25 triliun per tahun, mendorong adopsi IoT dan computer vision untuk deteksi dini.[^1]
- Risiko keamanan pada transmisi citra dari perangkat petani/IoT ke cloud sebagai celah kerentanan siber di ekosistem agro-digital.[^1]

### B. Permasalahan Enkripsi Konvensional
- Keterbatasan Hill Cipher klasik terhadap known-plaintext attack dan analisis linear.[^1]
- Kerentanan Blowfish terhadap isu key reuse pada volume data citra besar.[^1]
- Kendala orkestrasi manual pada microservices yang memicu latency hingga 40%, menegaskan perlunya mekanisme seleksi otomatis.[^1]

### C. Research Gap dan Kontribusi Riset
- Belum ada studi yang mengintegrasikan pemilihan tipe algoritma enkripsi (bukan hanya parameter/kunci) menggunakan machine learning berbasis karakteristik citra (entropi, ukuran, tekstur).[^1]
- Kontribusi utama: memperkenalkan paradigma AI-driven cipher selection dalam microservices IoT yang mengoptimalkan keamanan citra agro secara adaptif.[^1]

### D. Tujuan Penelitian
- Merancang model AI Selector berbasis Decision Tree yang adaptif terhadap variasi karakteristik visual citra penyakit kopi.
- Membangun purwarupa orkestrasi microservices untuk distribusi beban enkripsi pada lingkungan container.
- Memvalidasi ketahanan dan efektivitas sistem pada skala uji lapangan terbatas di Jember.[^1]

## II. Tinjauan Pustaka / Related Work

### A. Kriptografi Citra dan Skema Hybrid
- Perbandingan performa Blowfish, AES, Twofish, Salsa20, ChaCha20 untuk enkripsi citra dan trade-off keamanan-kecepatan-memori.[^1]
- Perkembangan Unimodular Hill Cipher (matriks determinan Â±1) sebagai penguat Hill Cipher klasik, termasuk kombinasi UHC-AES yang meningkatkan entropi dan menurunkan korelasi piksel.[^1]
- Posisi gap: kombinasi UHC-Blowfish spesifik untuk citra IoT pertanian belum banyak dieksplorasi.

### B. Enkripsi dan Keamanan Citra pada IoT Pertanian
- Studi deteksi penyakit kopi berbasis CNN dan IoT (sensor lingkungan, klasifikasi mutu biji kopi via MobileNetV2) yang berfokus pada akurasi deteksi, bukan keamanan data.[^1]
- Penegasan celah riset: keamanan data citra penyakit tanaman selama transmisi/penyimpanan cloud belum menjadi fokus utama.

### C. Keamanan Microservices untuk Aplikasi IoT
- Karakteristik microservices (modularitas, skalabilitas) versus perluasan permukaan serangan pada level container.[^1]
- Pendekatan mimic defense dan penjadwalan image adaptif sebagai pembanding mekanisme orkestrasi cerdas.[^1]

### D. Mekanisme Seleksi Dinamis Berbasis AI
- Pendekatan compressed sensing (CS-ASIC) untuk kompresi citra AIoT sebagai pembanding pendekatan adaptif berbasis fitur, meski berfokus pada kompresi bukan pemilihan cipher.[^1]
- Penegasan bahwa AI-based cipher-type selector (bukan sekadar tuning parameter) masih jarang dibahas secara sistematis di literatur.

### E. Kerangka Konseptual dan Peta Jalan
- Diagram alur sistem: layer lapangan (petani) â†’ perangkat IoT/smartphone â†’ jaringan â†’ platform microservices (AI Selector Service memilih UHC/Blowfish/Hybrid) â†’ dashboard.[^1]
- Lima tahap peta jalan: implementasi cipher terpisah, desain hybrid, pengembangan AI Selector, integrasi microservices, evaluasi komprehensif.[^1]

## III. Metodologi

### A. Desain Penelitian
- Pendekatan eksperimental kuantitatif setingkat TKT 2 (formulasi konsep dan proof-of-concept tanpa deployment fisik penuh).[^1]
- Lokasi: Laboratorium AI Fakultas Ilmu Komputer Universitas Jember; dataset 1.000 citra penyakit kopi dari Kaggle.[^1]

### B. Dataset dan Pra-pemrosesan
- Preprocessing 1.000 citra (resize 512x512, normalisasi).
- Ekstraksi fitur: entropi, ukuran file, tekstur (GLCM â€” mean dan contrast) sebagai input model.[^1]

### C. Implementasi Algoritma Kriptografi
- Implementasi UHC berbasis matriks unimodular 3x3 dan Blowfish 16-round Feistel secara terpisah sebagai baseline.[^1]
- Perancangan skema hybrid: UHC untuk pixel shuffling, Blowfish untuk substitusi blok.[^1]

### D. Pengembangan Model AI Selector (Decision Tree)
- Pelatihan model Decision Tree (Scikit-learn) dengan skema split 80:20 train-test.
- Fitur input: entropi, ukuran file, mean GLCM, contrast GLCM; output kelas: UHC, Blowfish, atau Hybrid.[^1]
- Target metrik akurasi klasifikasi minimal 85%.[^1]
- Jelaskan struktur pohon keputusan (criterion split, depth, pruning) dan rasionalisasi pemilihan Decision Tree dibanding model lain (interpretability, ringan untuk edge).

### E. Arsitektur Orkestrasi Microservices
- Tech stack: Python, Docker, Kubernetes (service discovery, load balancing), workflow engine n8n, PostgreSQL terenkripsi, Redis cache.[^1]
- Diagram arsitektur edge-cloud: AI Selector Service, Hybrid Encryption Services (UHC/Blowfish/Hybrid), orkestrasi Kubernetes/n8n.[^1]

### F. Skema Pengujian dan Evaluasi
- Pengujian keamanan: analisis entropi, histogram, korelasi piksel, resistensi terhadap differential attack, noise analysis, brute force simulation.[^1]
- Pengujian performa: PSNR (target â‰¥35dB), SSIM, throughput (image/s), latency (ms), penggunaan CPU/memori pada load test 1.000 citra.[^1]
- Uji lapangan terbatas dengan 20 petani di Jember menggunakan smartphone Android untuk upload citra real-time.[^1]

## IV. Hasil dan Pembahasan

### A. Karakteristik Dataset dan Fitur Citra
- Statistik deskriptif fitur (rentang entropi, ukuran file, nilai GLCM) pada 1.000 citra penyakit kopi.
- Visualisasi distribusi fitur antar kelas penyakit (leaf rust vs anthracnose) sebagai dasar pemilihan cipher.

### B. Performa Enkripsi Tunggal vs Hybrid
- Perbandingan PSNR, SSIM, histogram, dan korelasi piksel antara UHC tunggal, Blowfish tunggal, dan hybrid UHC-Blowfish.[^1]
- Analisis waktu enkripsi/dekripsi tiap skema sebagai basis trade-off keamanan-efisiensi.

### C. Akurasi dan Perilaku Model AI Selector
- Hasil akurasi Decision Tree pada data uji (dibandingkan dengan target 85%).[^1]
- Analisis feature importance (entropi vs tekstur vs ukuran) untuk menjelaskan logika keputusan pohon.
- Confusion matrix klasifikasi UHC/Blowfish/Hybrid dan diskusi kesalahan klasifikasi (jika ada).

### D. Evaluasi Keamanan Sistem
- Hasil uji resistensi terhadap differential attack, noise attack, dan brute force pada citra yang dienkripsi dengan rute cipher hasil pilihan AI Selector.[^1]
- Perbandingan tingkat keamanan sistem adaptif versus penggunaan cipher tunggal statis.

### E. Evaluasi Performa Orkestrasi Microservices
- Hasil throughput dan latency pada load test 1.000 citra dalam arsitektur Kubernetes/n8n.[^1]
- Analisis penggunaan CPU/memori dan skalabilitas layanan pada skenario beban tinggi.

### F. Hasil Uji Lapangan
- Temuan dari uji coba 20 petani Jember: kemudahan penggunaan, latensi upload real-time, dan kendala teknis di lapangan.[^1]

### G. Pembahasan Komparatif dan Implikasi
- Diskusi posisi hasil riset dibanding studi hybrid UHC-AES dan skema enkripsi citra IoT sebelumnya.[^1]
- Implikasi praktis bagi ketahanan pangan dan agenda Pertanian Digital Jember serta Industry 5.0.[^1]
- Keterbatasan penelitian (skala TKT 2, dataset terbatas, belum ada deployment produksi penuh).

## V. Kesimpulan

- Ringkasan capaian: keberhasilan (atau kegagalan sebagian) mencapai target akurasi Decision Tree, PSNR, dan metrik keamanan sesuai proposal.[^1]
- Penegasan kontribusi orisinal: paradigma AI-driven cipher selection dalam microservices agro-IoT.[^1]
- Implikasi bagi pengembangan lanjutan: potensi skalabilitas ke platform industri (federated learning, aplikasi mobile untuk 200 petani) sebagai bagian roadmap tahun kedua Grand Riset KopiSecure.[^1]
- Saran penelitian lanjutan: pengujian pada dataset lebih besar, algoritma AI Selector lain sebagai pembanding, serta integrasi dengan quantum-resistant cipher pada roadmap jangka panjang.[^1]

## Catatan Penulisan

- Setiap sub-bab Hasil dan Pembahasan sebaiknya dilengkapi tabel/figure kuantitatif (PSNR, SSIM, akurasi, throughput) sesuai indikator capaian pada proposal agar konsisten dengan luaran hibah yang dijanjikan.[^1]
- Daftar pustaka artikel dapat memanfaatkan referensi primer yang telah dikumpulkan pada tinjauan pustaka proposal, khususnya terkait UHC, Blowfish, dan keamanan microservices, dengan penambahan referensi terbaru saat submission.[^1]

---

## References

1. [README.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/collection_2cc43c4e-bf5f-4e5a-9ab5-d2bf19e9f758/eaea6749-e85f-458f-92fa-777a6bb66cda/README.md)

