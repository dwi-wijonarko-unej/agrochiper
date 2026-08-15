# AgroCipher Microservices Prototype

This repository contains a microservices prototype for the research:
**AI Selector-based orchestration for adaptive coffee disease image encryption using Hybrid UHC-Blowfish**.

## Architecture

Services:

- `gateway` (Go): API Gateway & Orchestrator
- `feature-service` (Python/FastAPI): entropy + GLCM texture extraction
- `selector-service` (Python/FastAPI): Decision Tree-based AI Selector
- `encryption-service` (Python/FastAPI): UHC + Blowfish hybrid encryption and decrypt-verify with SQLite logging
- `web` (nginx): static landing page served at http://localhost:8084

Configuration:

- `.env` file for secrets and service URLs
- Docker Compose for multi-service orchestration

## Run (local or VPS)

```bash
docker compose up -d --build
docker compose ps
```

## Health check

```bash
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8082/health
curl http://localhost:8083/health
```

## Web landing page

The static homepage is served by nginx:

- http://localhost:8084 — AgroCipher landing page (`web/index.html`)

## Authentication

The `/api/v1/encrypt-image` endpoint is protected with an API key. The key is
read from the `GATEWAY_API_KEY` environment variable (set it in your `.env`).

Clients must send the key on every request via either:

- header `X-API-Key: <key>`, or
- header `Authorization: Bearer <key>`

If the key is missing or wrong the gateway returns `401 Unauthorized`. If the
server has not configured `GATEWAY_API_KEY`, the gateway rejects all requests
with `503` (fail-closed). The `/health` endpoint remains public.

Generate a strong key for production:

```bash
openssl rand -hex 32
```

## Encrypt test image

Assuming `sample.jpg` exists in the current folder and `GATEWAY_API_KEY` is set:

```bash
curl -X POST http://localhost:8080/api/v1/encrypt-image \
  -H "X-API-Key: $GATEWAY_API_KEY" \
  -F "file=@sample.jpg"
```

Equivalent using a Bearer token:

```bash
curl -X POST http://localhost:8080/api/v1/encrypt-image \
  -H "Authorization: Bearer $GATEWAY_API_KEY" \
  -F "file=@sample.jpg"
```

Response JSON includes:

- image features (entropy, size, GLCM correlation/contrast)
- AI Selector decision (UHC / Blowfish / Hybrid)
- encryption & decryption runtimes
- ciphertext entropy
- PSNR
- base64-encoded encrypted payload

## Batch Runner (bulk encryption)

Script `client/batch_runner.py` melakukan scan rekursif pada folder dataset,
mengirim setiap gambar ke API gateway, dan menyimpan semua metrik ke CSV.

### Prasyarat

```bash
pip install requests
```

### Struktur folder

```
agrochiper/
├── .env                  ← GATEWAY_API_KEY dibaca dari sini
└── client/
    └── batch_runner.py
```

API key dibaca **otomatis** dari `GATEWAY_API_KEY` di file `.env` root project.
Tidak perlu export env var secara manual.

### Penggunaan

```bash
# Minimal — scan folder dataset, output ke results_batch.csv
python client/batch_runner.py ./dataset-daun-kopi

# Dengan argumen lengkap
python client/batch_runner.py <folder_dataset> [api_url] [output_csv]

# Contoh eksplisit
python client/batch_runner.py ./dataset \
  http://localhost:8080/api/v1/encrypt-image \
  hasil_eksperimen.csv
```

### Output terminal

```
.env path       : /opt/research/agrochiper/.env
.env exists     : True
API key len     : 64 karakter  (harus 64)
API key end     : ...57591e0

Dataset folder  : ./dataset-daun-kopi
API endpoint    : http://localhost:8080/api/v1/encrypt-image
Output CSV      : results_batch.csv
Total gambar    : 120
Akan diproses   : 120 gambar

[   1/120] bercak/img_001.jpg          -> Blowfish (OK)
[   2/120] bercak/img_002.jpg          -> Hybrid UHC-Blowfish (OK)
...
=============================================
  RINGKASAN BATCH
=============================================
  Berhasil diproses  :    118 gambar
  Gagal diproses     :      2 gambar
  Total waktu batch  :   45.32 detik
  Hasil tersimpan di : results_batch.csv
=============================================
```

### Kolom output CSV

| Kolom              | Keterangan                                                            |
| :----------------- | :-------------------------------------------------------------------- |
| `relative_path`    | Path relatif dari folder dataset                                      |
| `filename`         | Nama file gambar                                                      |
| `method`           | Algoritma yang dipilih AI: `UHC` / `Blowfish` / `Hybrid UHC-Blowfish` |
| `decision_code`    | Kode numerik keputusan AI (0/1/2)                                     |
| `reasoning`        | Alasan pemilihan algoritma oleh AI                                    |
| `encryption_time`  | Waktu enkripsi (detik)                                                |
| `decryption_time`  | Waktu dekripsi (detik)                                                |
| `cipher_entropy`   | Entropi Shannon ciphertext (maks 8.0)                                 |
| `psnr`             | PSNR hasil dekripsi vs asli (`∞` = lossless sempurna)                 |
| `entropy`          | Entropi Shannon gambar asli                                           |
| `size_kb`          | Ukuran file (KB)                                                      |
| `glcm_correlation` | Korelasi GLCM tekstur gambar                                          |
| `glcm_contrast`    | Kontras GLCM tekstur gambar                                           |
| `error`            | Pesan error jika gagal (kosong jika sukses)                           |

### Fitur resume

Jika proses terhenti di tengah jalan (misalnya koneksi putus), jalankan
**perintah yang sama** tanpa mengubah apapun. Script akan membaca CSV yang
sudah ada, melewati gambar yang sudah berhasil, dan melanjutkan dari posisi
terakhir.

```bash
# Jalankan ulang — otomatis resume, tidak memproses ulang yang sudah OK
python client/batch_runner.py ./dataset-daun-kopi
```

## Inkorporasi & data eksperimen

Mulai versi ini, sistem memiliki instrumentasi eksperimen (fail-open) untuk
menghubungkan seluruh request via `request_id` dan menulis log per-service:

- `feature_logs` (feature-service), `selector_logs` (selector-service),
  `crypto_logs` (encryption-service) di SQLite, dan JSONL gateway
  (`GATEWAY_EXPERIMENT_LOG`). Lihat `docs/EXPERIMENT_DATA.md` untuk kolom & satuan.
- Export ke CSV: `python analysis/export_experiment_data.py` → `results/exported/`.
- `client/batch_runner.py` mode eksperimen:
  `python client/batch_runner.py <dataset> --experiment-id EXP-001 --warmup 10 --repeat 3 --resume`.
- Mode forced-method (baseline evaluasi) hanya aktif bila `EXPERIMENT_MODE=true`
  di `.env`: header `X-Experiment-Force-Method: UHC|Blowfish|Hybrid UHC-Blowfish|adaptive`.
- Rencana eksperimen dan penulisan Bab 4: `docs/CHAPTER4_PLAN.md`, audit awal:
  `EXPERIMENT_AUDIT.md`.

## SQLite logging

The encryption service logs each request into a SQLite database (by default `/data/logs.db`):

Table: `encryption_logs`

Columns:

- `id`
- `filename`
- `method`
- `encryption_time`
- `decryption_time`
- `cipher_entropy`
- `psnr`
- `created_at`

You can inspect the logs (on VPS) with:

```bash
sqlite3 data/encryption/logs.db
sqlite> .tables
sqlite> SELECT id, filename, method, encryption_time, decryption_time, cipher_entropy, psnr, created_at
        FROM encryption_logs ORDER BY id DESC LIMIT 10;
```
