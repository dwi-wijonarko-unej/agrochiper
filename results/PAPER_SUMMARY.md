# PAPER_SUMMARY — AgroCipher Eksperimen Bab 4

Dihasilkan: build_paper_tables.py

## Dataset
- 2834 citra uji (Healthy: 500, Rust: 500, Miner: 500, Phoma: 500, Red Spider Mite: 334, Cerscospora: 500)
- Sumber: campuran 5 sumber (Coffee Leaf Diseases, coffee___, drive-download, ethiopian test, ethiopian train aug), 6 kelas ternormalisasi; downscale max 1024 px, JPEG q90, seed 42; round-robin antar sumber (cap 500/kelas).
- Rata-rata entropy per kelas: {'Healthy': 6.423, 'Rust': 6.1331, 'Miner': 5.2429, 'Phoma': 5.7387, 'Red Spider Mite': 7.5692, 'Cerscospora': 6.0164}

## Hasil EXP-001 (adaptive)
- Request utama: 8502; sukses: 8502 (100.0% jika total_main)
- Seluruh 8502 request lossless (psnr='∞', decrypt_verified=True).
- Metode terpilih: UHC 583 citra (20.57%); Blowfish 2052 citra (72.41%); Hybrid UHC-Blowfish 199 citra (7.02%)
- Enkripsi: rata-rata 50.0443 ms; end-to-end rata-rata 339.7405 ms.
- Cipher entropy rata-rata: 7.7394 bit/byte (maks. 8).

## EXP-002 (perbandingan metode)
- UHC: sukses 100.0%, enkripsi 77.5755 ms, e2e 325.7361 ms, cipher entropy 7.7376, PSNR ∞ (lossless).
- Blowfish: sukses 100.0%, enkripsi 21.3943 ms, e2e 216.0977 ms, cipher entropy 7.9999, PSNR ∞ (lossless).
- Hybrid UHC-Blowfish: sukses 100.0%, enkripsi 89.6319 ms, e2e 352.1934 ms, cipher entropy 7.9999, PSNR ∞ (lossless).
- Adaptive: sukses 100.0%, enkripsi 36.4734 ms, e2e 254.8285 ms, cipher entropy 7.7394, PSNR ∞ (lossless).

## EXP-003 (kriptografi)
- UHC: entropy payload 7.545893, korelasi byte 0.119191, NPCR 0.0009%, UACI 0.0004%.
- Blowfish: entropy payload 7.999899, korelasi byte 4.4e-05, NPCR 99.6075%, UACI 33.47%.
- Hybrid UHC-Blowfish: entropy payload 7.999896, korelasi byte -8e-06, NPCR 99.6057%, UACI 33.4668%.
- Baseline tanpa enkripsi: NPCR 5.9e-05%, UACI 4.2e-05% (flip 1 byte).

## EXP-004 (performa microservices, load test)
- VU=1: 430 request, throughput 3.583 req/s, latensi p50=252.46ms p95=398.31ms p99=490.43ms, error 0.0%, CPU enkripsi 54.27%.
- VU=5: 556 request, throughput 4.633 req/s, latensi p50=1017.22ms p95=1573.92ms p99=1847.88ms, error 0.0%, CPU enkripsi 63.19%.
- VU=10: 550 request, throughput 4.583 req/s, latensi p50=2184.44ms p95=3334.78ms p99=3719.32ms, error 0.0%, CPU enkripsi 66.33%.
- VU=20: 604 request, throughput 5.033 req/s, latensi p50=4030.7ms p95=6655.98ms p99=8184.13ms, error 0.0%, CPU enkripsi 63.65%.
- Bottleneck: encryption-service (CPU 54-66%); throughput plateau ~4.6-5.0 req/s (uvicorn single worker).

## Catatan keterbatasan
- Tanpa ground-truth label metode terbaik: tidak ada klaim akurasi/precision selector.
- Blowfish: IV tetap hanya untuk uji NPCR/UACI offline; runtime pakai os.urandom(8).
- Load test single-node Docker Compose (uvicorn single worker), bukan Kubernetes.
- Korelasi 'vertikal' = lag baris raster, bukan korelasi spasial 2D.