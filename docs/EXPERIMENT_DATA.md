# EXPERIMENT_DATA.md — Instrumentasi Data Eksperimen AgroCipher

Dokumen ini menjelaskan kolom, satuan, dan sumber setiap log eksperimen yang
ditambahkan pada sistem AgroCipher (dokumen pendamping `EXPERIMENT_AUDIT.md`).

Tujuan instrumentasi: menyediakan data mentah untuk Bab 4 manuskrip tanpa mengubah
kontrak API produksi. **Semua logging bersifat fail-open** — kegagalan menulis log
tidak pernah menggagalkan enkripsi.

---

## 1. Identitas: request_id

Setiap request dari client diberi `request_id` unik (16-byte hex, dibuat gateway).
Di dalam satu request yang sama, `request_id` yang sama dikirim ke:

| Service | Cara pengiriman |
| --- | --- |
| feature-service | multipart form field `request_id` |
| selector-service | field JSON `request_id` (opsional, default `""`) |
| encryption-service | multipart form field `request_id` |
| client (batch_runner) | dibaca dari respons JSON agregat |

`request_id` menjadi kunci gabung (join key) antar tabel log dan CSV eksperimen.

---

## 2. Table SQLite per service

Setiap service menulis ke database SQLite sendiri:
`<EXPERIMENT_DB_PATH>` (default `/experiment/experiment_logs.db`, volume
docker-compose). Satu koneksi bersama (`check_same_thread=False`), tulis serial.

### 2.1 feature-service → tabel `feature_logs`

| Kolom | Satuan | Sumber |
| --- | --- | --- |
| `id` | — | autoincrement |
| `request_id` | — | dari gateway |
| `timestamp_utc` | ISO-8601 UTC | `time.gmtime()` |
| `filename` | — | nama file upload |
| `file_extension` | — | `os.path.splitext(...)[1].lower()` |
| `image_width` | piksel | `Image.size[0]` |
| `image_height` | piksel | `Image.size[1]` |
| `file_size_kb` | KB (file terkompresi) | `len(data)/1024.0` |
| `entropy` | bit/piksel (0–8) | Shannon, 256 bin, grayscale 8-bit |
| `glcm_correlation` | — | `graycoprops(..., "correlation")`, 1 level piksel, angle 0° |
| `glcm_contrast` | — | `graycoprops(..., "contrast")`, parameter GLCM sama |
| `feature_extraction_time_ms` | ms | `perf_counter` di sekitar decode+GLCM |
| `processing_time_ms` | ms | seluruh handler feature-service |
| `status` | `ok` / `error` | hasil eksekusi |
| `error_message` | — | pesan error bila gagal |

### 2.2 selector-service → tabel `selector_logs`

| Kolom | Satuan | Sumber |
| --- | --- | --- |
| `id` | — | autoincrement |
| `request_id` | — | dari gateway |
| `timestamp_utc` | ISO-8601 UTC | `time.gmtime()` |
| `selector_method` | `UHC`/`Blowfish`/`Hybrid UHC-Blowfish` | hasil `model.predict` |
| `decision_code` | 0/1/2 | output DecisionTree |
| `reasoning` | — | string statis per decision_code (bukan path pohon) |
| `selector_inference_time_ms` | ms | `perf_counter` di sekitar `model.predict` |
| `processing_time_ms` | ms | seluruh handler predict |
| `model_version` | — | `md5:<hash pkl>` bila model file ada, else `dt-maxdepth3-seed42` |
| `model_features_used` | — | `entropy,size_kb,glcm_correlation,glcm_contrast` |
| `status` | `ok` / `error` | |
| `error_message` | — | |

### 2.3 encryption-service → tabel `crypto_logs`

| Kolom | Satuan | Sumber |
| --- | --- | --- |
| `id` | — | autoincrement |
| `request_id` | — | dari gateway |
| `timestamp_utc` | ISO-8601 UTC | `time.gmtime()` |
| `method` | `UHC`/`Blowfish`/`Hybrid UHC-Blowfish` | `cipher_mode` yang diterima |
| `encryption_time_ms` | ms | `perf_counter` blok kripto saja (tanpa I/O jaringan) |
| `decryption_time_ms` | ms | `perf_counter` blok dekripsi-verify |
| `cipher_entropy` | bit/byte (0–8) | Shannon dari **seluruh payload** (header+tag+ciphertext) |
| `psnr` | dB sebagai string; `∞` = lossless | `20·log10(255/√mse)` |
| `psnr_is_infinite` | 0/1 | `mse == 0` |
| `decrypt_verified` | 0/1 | `mse == 0` (lossless recovery) |
| `encrypted_payload_size_bytes` | byte | `len(payload)` |
| `original_payload_size_bytes` | byte | `len(img.tobytes())` (RGB mentah) |
| `processing_time_ms` | ms | seluruh handler process |
| `status` | `ok` / `error` | |
| `error_message` | — | |

> Tabel produksi `encryption_logs` dan endpoint `/encryption/v1/logs` TIDAK
> diubah — kontrak lama untuk `web/analytics.html` tetap berlaku.

---

## 3. Log gateway (JSONL)

Gateway (Go, stdlib-only) tidak menulis SQLite; ia menulis **JSON Lines** ke
`GATEWAY_EXPERIMENT_LOG` (default `/experiment/gateway_experiment.jsonl`).

Field per baris: `request_id`, `filename`, `method`, `timestamp_utc`,
`gateway_start_time_utc`, `gateway_end_time_utc`, `end_to_end_latency_ms`,
`http_status`, `error_type`, `feature_service_ms`, `selector_service_ms`,
`encryption_service_ms`, `effective_method`, `experiment_forced_method`.

- `end_to_end_latency_ms` diukur gateway dari awal handler sampai sebelum respons
  dikirim (termasuk 3 panggilan internal).
- `error_type`: `auth_failed`, `api_key_not_configured`, `file_required`,
  `read_file_failed`, `feature_service_call_failed`, `invalid_feature_response`,
  `selector_service_call_failed`, `invalid_selector_response`,
  `encryption_service_call_failed`, `invalid_encryption_response`, atau kosong
  untuk sukses.
- `experiment_forced_method` terisi hanya jika mode eksperimen aktif (lihat §5).

---

## 4. Ekspor ke CSV

```bash
python analysis/export_experiment_data.py \
  --db-dir data/experiment \
  --out-dir results/exported
```

Output:
- `experiment_requests.csv` — gabungan `feature_logs`
- `experiment_selector.csv` — gabungan `selector_logs`
- `experiment_encryption.csv` — gabungan `crypto_logs`
- `experiment_gateway.csv` — seluruh baris JSONL gateway
- `experiment_failures.csv` — baris `status != ok` / `error_message` / `error_type`
  dari keempat sumber, dengan kolom `source`.

Kolom `id` dihilangkan pada tiga CSV pertama.

---

## 5. Mode eksperimen forced-method (EXP-002)

Aktif hanya bila env **`EXPERIMENT_MODE=true`** (production default `false`).
Saat aktif, gateway menerima header internal:

```
X-Experiment-Force-Method: UHC | Blowfish | Hybrid UHC-Blowfish | adaptive
```

- `adaptive` atau nilai invalid → pakai keputusan AI Selector (default).
- Nilai valid lain → memaksa metode tsb, melewati selector untuk pemilihan metode
  (fitur tetap diekstraksi dan di-log; seluruh pipeline tetap jalan).
- Header diabaikan bila `EXPERIMENT_MODE=false`.

---

## 6. Environment variable baru

| Var | Dipakai oleh | Default | Tujuan |
| --- | --- | --- | --- |
| `EXPERIMENT_MODE` | gateway | `false` | Aktifkan forced-method header |
| `EXPERIMENT_DB_PATH` | feature/selector/encryption | `/experiment/experiment_logs.db` | DB log eksperimen per service |
| `GATEWAY_EXPERIMENT_LOG` | gateway | `/experiment/gateway_experiment.jsonl` | JSONL access log gateway |

Semua nilai default dipasok lewat `docker-compose.yml` volume
`./data/experiment/<service>:/experiment`.

---

## 7. Catatan analisis

- Gabungkan antar tabel pakai `request_id`. Baris `experiment_gateway.csv` adalah
  otoritas `http_status`/`error_type`; tabel fitur/selector/crypto hanya ada bila
  request berhasil mencapai service tsb.
- `cipher_entropy` mencakup header payload (8+3+4 byte) — bukan murni ciphertext.
- Untuk evaluasi kriptografi (NPCR/UACI), gunakan payload mentah, bukan base64.
- Jangan menulis `cipher_base64` maupun API key ke CSV eksperimen (batch_runner
  sudah memastikannya).

---

## 8. Penyimpanan ciphertext EXP-003 (hemat disk)

`client/batch_runner.py` mendukung penyimpanan payload mentah untuk analisis
kriptografi:

- `--save-ciphertext-dir <dir>`: simpan `cipher_base64` (payload header+ciphertext)
  sebagai `<request_id>.bin` per request utama.
- `--save-ciphertext-limit N`: simpan hanya **sampel deterministik merata**
  (stride = ceil(total_main/N)) — bukan N pertama. Menghindari bias ke kelas
  yang muncul pertama dalam urutan file (kasus: dataset v1 yang hanya menyimpan
  kelas Cerscospora) dan membatasi disk (~1.7MB/payload; N=300 per skenario ≈ 2GB).

Catatan untuk dataset campuran (6 kelas, 5 sumber), pastikan sample ciphertext
mencakup semua kelas sebelum menjalankan `crypto_metrics.py`; verifikasi cepat
dengan menghitung distribusi kelas dari `request_id` → `relative_path`.