# EXPERIMENT_AUDIT.md — Audit Kesiapan Eksperimen AgroCipher

> Audit berbasis kode aktual (commit `34f9a39`) untuk menyiapkan eksperimen artikel:
> **"A Microservices Prototype for Adaptive Agro-IoT Image Encryption: Integrating Entropy and GLCM Features with Hybrid UHC-Blowfish"**
>
> Status: **audit hanya**. Tidak ada perubahan kode yang dilakukan. Semua temuan merujuk
> ke `file:line` implementasi yang sedang berjalan.

---

## Ringkasan Eksekutif

1. **Pipeline sudah berjalan utuh** dan kontrak API antar-service konsisten dengan
   AGENTS.md. Gateway mengorkestrasi `feature → selector → encryption` secara serial
   (tanpa paralelisme, tanpa request_id, tanpa observability waktu per service).
2. **Semua komponen kriptografi bersifat lossless deterministik** → PSNR selalu `∞`
   bila dekripsi berhasil. Artikel WAJIB melaporkan *lossless recovery rate*, bukan
   rata-rata PSNR.
3. **AI Selector BUKAN model empiris yang divalidasi.** Label 0/1/2 diturunkan dari
   aturan sintetis pada data acak (seed 42), lalu difit ke DecisionTree `max_depth=3`.
   Tidak boleh disebut "akurasi ≥ X% terhadap ground truth". Istilah aman: *decision
   behavior*.
4. **Hanya encryption-service yang menulis log (SQLite).** Gateway, feature-service,
   dan selector-service tidak mencatat apa pun → tidak ada request_id, tidak ada
   latency end-to-end, tidak ada error_type, tidak ada versi model.
5. **Kolom satuan saat ini berlawanan** dengan kebutuhan artikel: `encryption_time` /
   `decryption_time` dalam **detik** di API & SQLite, sedangkan kolom eksperimen yang
   diminta dalam **milidetik**. Jangan mengubah satuan field lama (kompatibilitas
   batch_runner & analytics); tambahkan field ms baru.
6. **Kunci UHC bersifat statis** (diturunkan deterministik dari `.env`), bukan per-
   request. Hanya IV Blowfish yang fresh per request. Ini batasan keamanan yang harus
   dinyatakan jujur.
7. Repo ini **Docker Compose saja** → klaim harus bertumpu pada istilah
   *containerized microservices prototype*, bukan Kubernetes/autoscaling.

---

## 1. Peta Alur Data Aktual

Alur eksekusi yang benar-benar terjadi di kode (bukan yang di-README):

```
 client (batch_runner.py / curl)
   │  POST /api/v1/encrypt-image  (multipart "file", header X-API-Key)
   ▼
 [gateway] encryptHandler  (gateway/main.go:75)
   │  requireAPIKey -> GATEWAY_API_KEY 401/503  (gateway/main.go:172-196)
   │  1) baca file bytes  (gateway/main.go:85-96)
   ├─▶ [feature-service] POST /extractor/v1/analyze (multipart file)
   │     └─> {entropy, size_kb, glcm_correlation, glcm_contrast}  (feature-service/app.py:45-50)
   ├─▶ [selector-service] POST /selector/v1/predict (JSON 4 fitur)
   │     └─> {decision_code, recommended_cipher, reasoning}  (selector-service/app.py:74-77)
   ├─▶ [encryption-service] POST /encryption/v1/process (multipart file + field cipher_mode=recommended_cipher)
   │     ├─ encrypt → decrypt → verify (PSNR)
   │     ├─ INSERT ke SQLite logs.db  (encryption-service/app.py:258-268)
   │     └─> {method, encryption_time, decryption_time, cipher_entropy, psnr,
   │          output_filename, cipher_base64}  (encryption-service/app.py:269-277)
   ▼
 [gateway] respon agregat {file, features, selector, result}  (gateway/main.go:144-152)
   ▼
 client → CSV (batch_runner.py)   |  web/analytics.html -> GET /api/v1/logs (gateway/main.go:198-223)
```

Fakta penting alur:

- **Serial murni**: gateway menunggu feature → selector → encryption satu per satu
  (`gateway/main.go:99`, `116`, `131`). Tidak ada tracing waktu per segmen; seluruh
  pengukuran waktu hidup di dalam encryption-service.
- **Satu-satunya titik log** adalah `encryption_logs` (table dibuat di
  `encryption-service/app.py:30-44`, volume `./data/encryption:/data` →
  `DB_PATH=/data/logs.db`). Kolom: `id, filename, method, encryption_time,
  decryption_time, cipher_entropy, psnr, created_at`. Log endpoint terbatas
  `LIMIT 100` (`encryption-service/app.py:142`).
- **Tidak ada request_id** di seluruh sistem. Tidak mungkin menghubungkan log
  encryption ke request batch tanpa identitas baru.
- **cipher_base64 dikirim kembali ke client** dalam body respons — menghindari
  pencatatannya di CSV eksperimen adalah kewajiban client.
- **Blowfish mode "Hybrid UHC-Blowfish"** dari selector masuk ke cabang `else`
  (`encryption-service/app.py:196`) karena `cipher_mode != "UHC"` dan `!= "Blowfish"`.
  Nama tag payload `b"HYB"`. Ini kompatibel, tapi rapuh: editor label di selector
  harus tetap terpetakan ke cabang `else`.

---

## 2. Fitur Citra yang Benar-Benar Dihitung

Sumber: `feature-service/app.py`. Semua perhitungan dilakukan per-request saat
inference (tidak ada cache, tidak ada tabel fitur).

| Fitur | Rumus / implementasi | Lokasi | Konfigurasi |
| --- | --- | --- | --- |
| **Entropy (Shannon)** | `H = -Σ p(b)·log2(p(b))`, histogram 256 bin pada piksel grayscale, `p = hist/total` (hanya bin `p>0`) | `feature-service/app.py:27-30` | Nilai grayscale 0–255; satuan bit/piksel, maks 8.0; dibulatkan 4 desimal |
| **Ukuran file** | `size_kb = len(data)/1024.0` — **ukuran file terkompresi** dari multipart, bukan piksel mentah | `feature-service/app.py:24` | KB; dipengaruhi format (JPEG/PNG), bukan murni resolusi |
| **GLCM contrast** | Haralick `Σ_{i,j} (i−j)²·p(i,j)` dari `graycoprops(glcm,"contrast")` | `feature-service/app.py:42` | Lihat parameter GLCM di bawah |
| **GLCM correlation** | Haralick `Σ (i−μi)(j−μj)p(i,j)/(σi·σj)` dari `graycoprops(glcm,"correlation")` | `feature-service/app.py:43` | Lihat parameter GLCM di bawah |

### Parameter GLCM (penting untuk metodologi artikel)

Sumber `feature-service/app.py:20-41`:

- **Grayscale conversion**: `Image.open(...).convert("L")` (8-bit Luma). **Bukan**
  luminance YCbCr atau mean RGB — sebut sebagai "8-bit grayscale via PIL/L".
- **Requantization**: `img_quantized = (img_arr / 32).astype(np.uint8)` →
  nilai 0–255 dikompaksi ke **8 level (0–7)**. Catatan: `255/32 = 7.97` → `uint8` = 7,
  jadi level tepat 0..7.
- **Distance**: `distances=[1]` → offset 1 piksel.
- **Angle**: `angles=[0]` → **hanya arah horizontal 0°**. Korelasi/kontras dihitung
  pada satu arah; artikel harus menyatakan ini sebagai keterbatasan (tidak
  isotropik; tidak pakai 45/90/135).
- **Levels**: `levels=8` (sesuai requantization 8 level).
- **Symmetric**: `symmetric=True` → GLCM dihitung dengan pendekatan simetris
  (offset dan kebalikannya), lalu `normed=True` → dinormalisasi menjadi matriks
  probabilitas.

Nilai yang dikembalikan dibulatkan ke 4 desimal (`app.py:45-50`). GLCM correlation
dapat bernilai negatif (checkerboard), yang kemudian dimasukkan sebagai input model.

---

## 3. Audit AI Selector

Sumber: `selector-service/app.py`.

### 3.1 Apakah Decision Tree benar-benar dimuat saat inference?

**Ya — berupa objek sklearn nyata, dimuat sekali ke global.**

- `startup_event()` (`app.py:42-49`): `joblib.load("ai_selector_model.pkl")`;
  bila gagal → `train_default_model()` lalu `joblib.dump`. Pola `@app.on_event`
  DEPRECATED di FastAPI — jangan dimodernisasi (ikut AGENTS.md).
- Saat inference, jika `model is None` (mis. startup gagal), dilatih ulang
  on-the-fly (`app.py:60-61`) → **model selalu Disk → RAM ``sklearn.tree
  .DecisionTreeClassifier``**, lalu `model.predict([[...]])` pada tiap request
  (`app.py:63-67`).

### 3.2 Sumber / aturan label kelas UHC/Blowfish/Hybrid

**Label 0/1/2 berasal dari ATURAN BUATAN pada data acak, bukan data empiris.**
`train_default_model()` (`app.py:20-39`):

- Membangkitkan `X = np.random.rand(200, 4)` (seed 42) lalu diskalakan:
  - `X[:,0] *= 8` → entropy ∈ [0,8]
  - `X[:,1] *= 500` → size_kb ∈ [0,500]
  - `X[:,2] = uniform(-1,1)` → correlation
  - `X[:,3] *= 1` → contrast ∈ [0,1]
- Label disusun dari aturan pada contoh latih:
  - `entropy > 6.2 AND contrast > 0.2` → `2` (Hybrid)
  - `entropy > 4.8` → `1` (Blowfish)
  - else → `0` (UHC)
- `DecisionTreeClassifier(max_depth=3, random_state=42)` (default gini/best).

**Konsekuensi untuk artikel**: ini *rule-derived synthetic training set*, bukan label
dari eksperimen nyata (tidak ada ground truth "metode terbaik" untuk citra kopi).
`ai_selector_model.pkl` tidak ada di git (dibuat saat startup container, tidak
reproducible antar environment selain oleh seed 42).

### 3.3 Fitur input model

Tepat 4 fitur, urutan sama antara training dan inference:
`[entropy, size_kb, glcm_correlation, glcm_contrast]` (`app.py:22-26` training;
`app.py:64-65` inference). Tidak ada normalisasi/scaling (tree tidak butuh).

### 3.4 Mapping decision_code 0/1/2

`mapping = {0:"UHC", 1:"Blowfish", 2:"Hybrid UHC-Blowfish"}` (`app.py:68`).
Gateway meneruskan `recommended_cipher` sebagai `cipher_mode` ke encryption-service
(`gateway/main.go:130`); encryption-service menerima `"UHC"` dan `"Blowfish"` secara
eksplisit, selainnya (`"Hybrid UHC-Blowfish"`) → Hybrid (`encryption-service/app.py:178,193,196`).

### 3.5 Logika "reasoning"

`reasoning` adalah **string statis per decision_code**, bukan hasil interpretasi
path pohon:

- `0` → "Low image complexity detected."
- `1` → "Moderate entropy detected."
- `2` → "High entropy and contrast detected. Maximum security fallback activated."

`app.py:69-73`. Tidak mencerminkan threshold aktual pohon, tidak mengandung nilai
fitur, dan tidak berubah antar request. Untuk artikel, reasoning ini **tidak dapat
digunakan sebagai bukti alasan pemilihan**; bukti yang valid adalah struktur pohon
(batas pemisah) dan analisis distribusi fitur vs keputusan.

### 3.6 Model dilatih dari data empiris atau rule-based?

**Rule-based / synthetic.** Tidak ada training-set empiris, tidak ada
train/test split, tidak ada validasi. Agar transparan, artikel harus menyebut
selector sebagai *rule-derived DecisionTree placeholder*, dan evaluasi dibatasi pada
*decision behavior*, bukan akurasi.

### 3.7 Cara mengekspor struktur pohon, feature importance, hyperparameter

Setelah container berjalan (`docker compose up -d`), copy model:

```bash
docker cp coffee-selector-service:/app/ai_selector_model.pkl analysis/models/.
```

```python
import joblib
from sklearn.tree import export_text, export_graphviz, DecisionTreeClassifier
clf: DecisionTreeClassifier = joblib.load("ai_selector_model.pkl")

print(export_text(clf, feature_names=["entropy","size_kb","glcm_correlation","glcm_contrast"]))
print(clf.feature_importances_)          # feature importance
print(clf.get_params())                  # hyperparameter (criterion, splitter, max_depth=3, ...)
# PNG/SVG
export_graphviz(clf, out_file="tree.dot", feature_names=[...],
                class_names=["UHC","Blowfish","Hybrid UHC-Blowfish"],
                filled=True, rounded=True)
# lalu: dot -Tpng tree.dot -o tree.png   (Graphviz)
```

Catatan: karena pohon bukan source of truth untuk label (label dipaksakan dari
aturan acak), interpretasi rule-by-rule dari `export_text` akan menyimpang dari
aturan mentah pada batas antar kelas.

---

## 4. Audit Hybrid UHC–Blowfish

Sumber: `encryption-service/app.py`.

### 4.1 Urutan proses Hybrid

- Enkripsi (`app.py:196-211`) → **UHC dulu (Hill cipher), lalu Blowfish** pada output UHC:
  `img_bytes → Hill n=16 → Blowfish-CBC`. Payload `= uint32(width) + uint32(height) + b"HYB" + uint32(pad_len) + blowfish(iv_8 || uhc_ciphertext)`.
- Dekripsi (`app.py:232-239`) → urutan dibalik: **Blowfish decrypt dulu, baru inverse Hill**.
- UHC-only (`app.py:178-192`): `header + b"UHC" + pad_len + hill_ciphertext` (tanpa Blowfish).
- Blowfish-only (`app.py:193-195`): `header + b"BLO" + blowfish(img_bytes)`.

### 4.2 Ukuran/blok dan mode Blowfish

- **Blowfish**: blok **64-bit**, **mode CBC**, PKCS7 **padding 64-bit**
  (`app.py:110-128`, `padding.PKCS7(64)`). IV 8-byte `os.urandom(8)` **diprepend** ke
  ciphertext (self-contained payload). Import dari `cryptography.hazmat.decrepit`
  (`app.py:10`) → kunci `cryptography==43.0.1` (lihat AGENTS.md: jangan upgrade).
- **UHC (Hill cipher)**: ukuran matriks `n = UHC_MATRIX_SIZE` (default 16, `.env`).
  Matriks dibangun dari `logistic_map(x0, ...)` dengan `x0 = float("0."+PWD2+"1")`,
  `r = 3.923`, disimpan sebagai `int32` mod 256 (`app.py:47-59`). Matriks berbentuk
  upper-triangular diagonal 1 sehingga determinan 1 mod 256 → invertibel. Inverse
  dihitung ulang per panggilan via eliminasi Gauss-Jordan sederhana (`app.py:84-96`).
  Padding byte `pad_len` agar panjang kelipatan `n`; nilai pad direkam di header
  (`struct.pack("I", pad_len)`).

### 4.3 Manajemen key & IV

- **Blowfish `SECRET_KEY`** (default `"kunci_rahasia_16b"`, 16 byte, dari `.env`)
  dipakai untuk **semua request dan untuk selamanya** — tidak berotasi.
- **Matriks Hill UHC** dihitung deterministik dari `UHC_PASSWORD2` (default `"7391"`)
  → matriks **sama persis untuk setiap request**.
- **IV Blowfish**: `os.urandom(8)` → **baru setiap request** (hanya di sisi enkripsi;
  dekripsi membaca kembali dari awal payload).

### 4.4 Apakah tiap request memakai key/IV baru?

- **UHC: TIDAK** — matriks kunci identik antar request (deterministik dari `.env`).
- **Blowfish: IV baru ya, kunci tidak.**
- Karena keduanya bersifat stateful-deterministik, ciphertext dua enkripsi citra yang
  sama dengan **Blowfish** berbeda (IV acak), sedangkan ciphertext **UHC-only** pasti
  identik → berpengaruh pada uji NPCR/UACI antar-request dan pada *cipher entropy*
  stabil.

### 4.5 Dapatkah ciphertext didekripsi kembali lossless?

**Ya, untuk ketiga mode, selama `.env` konsisten.** Kedua cipher bersifat lossless
(UHC: transformasi linear mod 256 + inverse eksak; Blowfish: CBC + PKCS7). Jika
`UHC_MATRIX_SIZE` / `UHC_PASSWORD2` identik saat enkripsi-dekripsi, `mse == 0` →
PSNR `"∞"` (`app.py:245-246`). PSNR adalah satu-satunya mekanisme verifikasi
(terdapat flag `decrypt_verified` **belum ada**). Catatan: `final_img_arr`
direkonstruksi `reshape(r_h, r_w, 3)` — asumsi byte-order RGB sama dengan sumber
(`img.tobytes()` setelah `convert("RGB")`, `app.py:167-170,243`).

### 4.6 Batasan keamanan implementasi (WAJIB dinyatakan jujur di artikel)

1. **Kunci UHC statis** (deterministik per `.env`) → *key reuse* antar citra;
   Hill cipher linier ⇒ rentan *known/chosen-plaintext attack*. Bukan upaya
   *one-time-pad*.
2. **`SECRET_KEY` Blowfish statis** dan dibagikan ke semua request; tidak
   menggunakan *Authenticated Encryption* (CBC **tanpa MAC/HMAC**) ⇒ **malleable**.
3. **Blok Blowfish 64-bit** ⇒ risiko *birthday bound* pada volume enkripsi besar
   (tidak relevan untuk citra tunggal, tapi batasi klaim).
4. **Keacakan UHC bergantung pada logistic map r=3.923 + seed float pendek**
   (`x0` dari `PWD2`) — bukan PRNG kriptografis; ruang kunci efektif kecil.
5. **Header payload tidak terenkripsi** (width, height, tag, pad_len) → metadata
   resolusi bocor; `cipher_entropy` dihitung atas header + ciphertext
   (`app.py:248-252`), sehingga bukan murni entropi ciphertext saja.
6. **Tidak ada autentikasi/integridas di tingkat payload**; deteksi korupsi hanya
   lewat PSNR (dan jika `mse>0`, gambar rusak secara diam-diam tetap
   "berhasil dekripsi").
7. **Container tidak memakai TLS** (port 8080-8083 HTTP polos, compose). base64
   ciphertext melewati jaringan tanpa enkripsi transport.
8. Konkurensi: encryption-service memakai **satu koneksi SQLite bersama**
   (`check_same_thread=False`, `app.py:28`) dengan uvicorn single worker → tulis
   serial; tidak diuji penskalaan.

---

## 5. Audit Metrik

| Metrik | Definisi & satuan | Lokasi | Catatan |
| --- | --- | --- | --- |
| **`encryption_time`** | `time.perf_counter()` **detik** hanya untuk blok kripto di encryption-service (bukan I/O jaringan/file service) | `app.py:176-213` | Satuan **detik** di API (`app.py:254`), SQLite, dan CSV batch_runner |
| **`decryption_time`** | `time.perf_counter()` **detik** hanya blok dekripsi-verify | `app.py:216-241` | Satuan **detik**, `app.py:255` |
| **`cipher_entropy`** | Shannon entropy dari **seluruh byte payload** (header+tag+pad+ciphertext, di-`np.frombuffer`) | `app.py:248-252` | Bins 256; maks 8.0; **termasuk metadata header**; dibulatkan 4 desimal |
| **`psnr`** | `mse=mean((orig−final)²)`; `"∞"` bila `mse==0`, else `20·log10(255/√mse)` | `app.py:245-246` | **string**, `∞` = lossless; MAX=255.0 dipakai sebagai konstanta |
| `decrypt_verified` | **tidak ada** — hanya diturunkan implisit dari PSNR==∞ | — | Kolom baru diperlukan |
| Feature extraction time | **tidak ada** (feature-service tidak memakai `perf_counter`) | feature-service — | |
| Selector inference time | **tidak ada** | selector-service — | |
| `model_version` | **tidak ada** | — | |
| End-to-end latency | **tidak ada**; gateway tidak mencatat waktu | gateway — | |
| `request_id` | **tidak ada** di seluruh sistem | — | penghubung log/batch |
| Per-service error/status | **tidak ada**; error hanya berupa HTTP status statis di gateway (`502/400/503/401`) | gateway/main.go | |
| Ukuran payload asal/terenkripsi | **tidak ada kolom**; hanya bisa diturunkan dari `len(payload)` intern | — | |)

### Metrik yang belum tersedia untuk evaluasi artikel

- **SSIM** (original vs dekripsi) — belum.
- **NPCR / UACI** — belum (membutuhkan dua ciphertext panjang sama & format
  kompatibel; untuk mode dengan IV acak hasilnya berbeda panjang? Perlu dicek —
  semua mode menghasilkan payload panjang deterministik untuk gambar sama, jadi
  *feasible* → lihat rekomendasi).
- **Korelasi piksel/byte ciphertext** (horizontal/vertikal/diagonal) — belum.
- **Throughput** (req/s, image/s) & **latency p50/p95/p99 per service** — belum;
  tanpa request_id/tracing tidak dapat dihitung per service.
- **CPU/memori per container**, jumlah **restart container**, **error log** selama
  eksperimen — belum.
- **Error rate** agregat — hanya tersedia dari CSV batch_runner (`error` kolom).

---

## 6. Rekomendasi Perubahan Minimal & Non-Intrusif

Prinsip: **jangan ubah bentuk API publik** (endpoint, auth, field lama), **jangan
ubah perilaku selector**, **jaga batch_runner** tetap bisa memanggil mode lama.
Tambahkan identitas `request_id` dan field *eksperimen* yang bersifat **additive**
(index JSON lama tidak boleh dipindah). Prioritas: **Wajib** (butuh untuk artikel)
/ **Disarankan** / **Opsional**.

### 6.1 Wajib

| Perubahan | File | Detail | Kompatibilitas |
| --- | --- | --- | --- |
| Generate & propagasi **`request_id`** | `gateway/main.go` | Sebelum memanggil feature: `request_id = <uuid/randomhex>`; kirim sebagai field form/header ke keempat panggilan internal; tambahkan `"request_id"` di respons agregat. | Additive: client lama memakai `.get()`, aman. |
| Logging request/fitur | feature-service | Catat `request_id, timestamp_utc, filename, image_width, image_height, file_size_kb, entropy, glcm_*, feature_extraction_time_ms` ke SQLite terpisah (bukan `encryption_logs`) — jangan ganti respons. | Tidak menyentuh kontrak JSON. |
| Logging keputusan selector | selector-service | `request_id, selector_method, decision_code, reasoning, selector_inference_time_ms, model_version, model_features_used`. `model_version` bisa hash file model atau konstanta `"dt-maxdepth3-seed42"`. | Tambah field respons opsional; parse lama aman. |
| Logging kripto (ms + ukuran) | encryption-service | Tambahkan field baru `*_ms` + `encrypted_payload_size_bytes`, `original_payload_size_bytes`, `decrypt_verified` (bool), simpan via request_id. **Jangan** mengubah unit `encryption_time` yang sudah ada. | Field lama tetap detik; field baru additive. |
| Logging end-to-end & error | gateway | Catat `gateway_start_time, gateway_end_time, end_to_end_latency_ms, http_status, error_type` per request_id, termasuk jalur error. | Internal, tidak mengubah respons sukses. |
| Logging layanan terpadu | ke-4 service | Tabel `service_logs(request_id, service_name, processing_time_ms, status, error_message, timestamp_utc)`; **tulis log aman salur** (try/except; kegagalan log tidak boleh menggagalkan enkripsi). | Fail-open untuk logging hanya. |
| Export script | `analysis/export_experiment_data.py` | Ekspor tabel ke `experiment_requests.csv`, `experiment_selector.csv`, `experiment_encryption.csv`, `experiment_gateway.csv`, `experiment_failures.csv`. | Script baru. |

### 6.2 Disarankan

| Perubahan | File | Detail |
| --- | --- | --- |
| Mode eksperimen batch (`--experiment-id/--warmup/--repeat/--resume/--force-rerun`) | `client/batch_runner.py` | Refactor argumen via `argparse` sambil mempertahankan mode posisional lama `[folder] [api] [csv]`; tambahkan `run_number`, `experiment_id`, `image_width/height`, `end_to_end_latency_ms`, simpan ke `results/EXP-ID/`; tulis `run_metadata.json`. |
| Mode forced-method (EXP-002) | gateway + encryption-service | Header internal `X-Experiment-Force-Method` hanya aktif jika `EXPERIMENT_MODE=true` di env gateway; valid value `UHC|Blowfish|Hybrid UHC-Blowfish|adaptive`; default tetap AI Selector. Jangan aktifkan di produksi tanpa flag env eksplisit. |
| Metrik kriptografi offline | `analysis/crypto_metrics.py` | Korelasi byte tetangga, NPCR/UACI, chi-square histogram, payload sizes — **offline**, tanpa mengubah endpoint. |
| SSIM | encryption-service ops/analysis | Hitung SSIM original vs dekripsi (skimage) dan simpan kolom; jangan simpan sebagai bukti keamanan. |
| PSNR proporsi infinity/non-binary | encryption-service / analysis | Kolom `psnr_is_infinite` + laporkan **lossless recovery rate** (`decrypt_verified`), bukan mean PSNR. |
| Load test (k6/Locust) | scripts/ + compose | Reduksi uji di staging; kumpulkan req/s, p50/p95/p99, CPU/RAM per container (mis. `docker stats --no-stream`). |

### 6.3 Opsional

- NPCR/UACI bila diputuskan: implementasikan sebagai perbandingan offline dua
  ciphertext **dari citra sama, mode sama, key sama** — karena UHC-only
  deterministik, feasible meningkp; untuk Blowfish gunakan **IV sama** saat uji
  differential (document dulu, karena IV acak membuat NPCR/UACI bermakna hanya
  dalam mode uji dengan fixed IV).
- Instrumentasi CPU/mem per service (`docker stats` + script aggregasi).
- TLS di gateway (opsional, tidak penting untuk artikel performa).
- `SELECT id, filename, size_kb` dsb: tambahkan index pada `created_at` bila volume
  besar.

### 6.4 Aturan menjaga kompatibilitas API

1. **Jangan rename / ganti satuan field JSON lama** (`entropy`, `size_kb`,
   `encryption_time` (detik), `decryption_time` (detik), `cipher_entropy`, `psnr`,
   `output_filename`, `cipher_base64`). `batch_runner.py:221-238` memakai `.get()`
   yang toleran field baru → aman.
2. Tambahkan **hanya field baru** (`request_id`, `*_ms`, `psnr_is_infinite`, dll.);
   pydantic tidak required.
3. **Jangan ubah aturan pencocokan `cipher_mode`** di encryption-service
   (`UHC`/`Blowfish`/else=Hybrid) atau kontrak `/encryption/v1/logs` (`{status,data:[]}`)
   yang dipakai `analytics.html`.
4. `batch_runner.py` versi baru: tetap dukung tanpa-argumen style lama (posisional),
   jangan ubah format baris `GATEWAY_API_KEY=` di `.env` (dibaca manual, AGENTS.md).
5. Jangan sentuh pola `@app.on_event("startup")` di selector-service.

---

## Lampiran A — Ringkasan "Apa yang sudah ada untuk artikel" vs "Belum ada"

**Sudah tersedia (dari implementasi aktual):**
- Alur microservices lengkap yang berjalan (4 service + gateway + web).
- Fitur entropy + GLCM (kontras/korelasi) + ukuran file, per citra, per request.
- Keputusan DecisionTree nyata untuk tiap request (mapping 0/1/2).
- UHC/Blowfish/Hybrid yang benar-benar lossless (PSNR `∞`) dengan ukuran waktu detik.
- Entropi ciphertext (termasuk header — dokumentasikan).
- SQLite `encryption_logs` (100 baris terakhir terlihat di analytics).
- Resume & error capture di batch CSV.

**Belum ada (harus ditambahkan untuk eksperimen):**
- request_id dan tracing end-to-end; latensi per service.
- Waktu ekstraksi fitur / inference selector; versi model.
- Ukuran payload asli vs terenkripsi; flag decrypt_verified; PSNR infinity flag.
- SSIM, NPCR/UACI, korelasi ciphertext, chi-square (belum).
- Mode batch eksperimen (warmup/repeat/experiment-id/run_number) dan metadata.
- Mode forced-method untuk baseline EXP-002.
- Load test & metrik resource container.
- Ground truth label untuk evaluasi akurasi selector (tidak ada → jangan klaim akurasi).

## Lampiran B — Klaim yang WAJIB dihindari di artikel (jujur & aman)

1. Jangan klaim **akurasi selector ≥ X%** — tidak ada ground truth & train/test split.
2. Jangan klaim **keamanan kriptografis kuat** dari UHC — kunci statis, linier,
   logistic map non-kriptografis.
3. Jangan klaim **skalabilitas horizontal/Kubernetes** — instance adalah Compose
   single-node, uvicorn single worker.
4. Jangan gunakan **PSNR sesuai target "harus > 30 dB" untuk membuktikan keamanan** —
   PSNR hanya untuk fidelity/lossless recovery.
5. Jangan laporan rata-rata PSNR kosong sebagai keamanan — gunakan
   **lossless recovery rate** (`decrypt_verified` / `psnr_is_infinite`).
6. `encryption_time` di artikel harus ditulis ulang sebagai **ms** (bentuk kolom
   eksperimen baru) dan dinyatakan cakupannya (hanya crypto di encryption-service).