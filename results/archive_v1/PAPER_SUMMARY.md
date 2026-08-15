# PAPER_SUMMARY — AgroCipher Eksperimen Bab 4

Dihasilkan: build_paper_tables.py

## Dataset
- 750 citra uji (Healthy: 150, Rust: 150, Miner: 150, Phoma: 150, Red Spider Mite: 150)
- Sumber: 'Coffee Leaf Diseases' 5 kelas; downscale max 1024 px, JPEG q90, seed 42.
- Rata-rata entropy per kelas: {'Healthy': 7.2439, 'Rust': 7.1546, 'Miner': 6.8914, 'Phoma': 6.7396, 'Red Spider Mite': 7.5712}

## Hasil EXP-001 (adaptive)
- Request utama: 2250; sukses: 2250 (100.0% jika total_main)
- Seluruh 2250 request lossless (psnr='∞', decrypt_verified=True).
- Metode terpilih: UHC 1 citra (0.13%); Blowfish 667 citra (88.93%); Hybrid UHC-Blowfish 82 citra (10.93%)
- Enkripsi: rata-rata 26.3476 ms; end-to-end rata-rata 206.42 ms.
- Cipher entropy rata-rata: 7.9999 bit/byte (maks. 8).

## EXP-002 (perbandingan metode)
- UHC: sukses 100.0%, enkripsi 71.4482 ms, e2e 301.592 ms, cipher entropy 7.9996, PSNR ∞ (lossless).
- Blowfish: sukses 100.0%, enkripsi 22.1222 ms, e2e 226.9453 ms, cipher entropy 7.9999, PSNR ∞ (lossless).
- Hybrid UHC-Blowfish: sukses 100.0%, enkripsi 91.0164 ms, e2e 355.8391 ms, cipher entropy 7.9999, PSNR ∞ (lossless).
- Adaptive: sukses 100.0%, enkripsi 27.2952 ms, e2e 235.5204 ms, cipher entropy 7.9999, PSNR ∞ (lossless).

## EXP-003 (kriptografi)
- UHC: entropy payload 7.999708, korelasi byte 0.000492, NPCR 0.001%, UACI 0.0003%.
- Blowfish: entropy payload 7.999892, korelasi byte -5.2e-05, NPCR 99.609%, UACI 33.468%.
- Hybrid UHC-Blowfish: entropy payload 7.999892, korelasi byte -8e-06, NPCR 99.6054%, UACI 33.4718%.
- Baseline tanpa enkripsi: NPCR 6.2e-05%, UACI 3.1e-05% (flip 1 byte).

## Catatan keterbatasan
- Tanpa ground-truth label metode terbaik: tidak ada klaim akurasi/precision selector.
- Blowfish: IV tetap hanya untuk uji NPCR/UACI offline; runtime pakai os.urandom(8).
- Microservices_Performance (load test) belum dijalankan (EXP-004).
- Korelasi 'vertikal' = lag baris raster, bukan korelasi spasial 2D.