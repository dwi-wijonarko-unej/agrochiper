# AGENTS.md — AgroCipher Microservices

Guidance for AI coding agents working in this repository.

## Project Overview

Research prototype (TRL 3) of a microservices system that **AI-selects an image
cipher (UHC / Blowfish / Hybrid UHC–Blowfish)** for coffee leaf disease images,
then encrypts and decrypt-verifies the image, logging metrics to SQLite.

The domain pipeline is:

```
client (multipart image)
  -> gateway (Go, orchestrator + API key auth)
      -> feature-service (FastAPI): entropy, size_kb, GLCM correlation/contrast
      -> selector-service (FastAPI): DecisionTree -> UHC(0)/Blowfish(1)/Hybrid(2)
      -> encryption-service (FastAPI): encrypt + decrypt-verify + SQLite logging
  -> JSON response (features, selector, result)
```

## Repository Layout

| Path | Language | Role |
| --- | --- | --- |
| `gateway/main.go` | Go 1.22 (stdlib only, no external deps) | API Gateway & orchestrator, API-key auth, `/api/v1/logs` proxy |
| `feature-service/app.py` | Python / FastAPI | Image feature extraction (entropy + GLCM) |
| `selector-service/app.py` | Python / FastAPI | scikit-learn DecisionTree classifier + rule-based fallback model |
| `encryption-service/app.py` | Python / FastAPI | UHC / Blowfish / Hybrid encryption, decrypt-verify, SQLite logging |
| `client/batch_runner.py` | Python / requests | Bulk encryption runner with CSV output + resume |
| `web/` | static HTML + Tailwind CDN | Landing page (`index.html`) + analytics (`analytics.html`) |
| `docker-compose.yml` | Compose v3.9 | Multi-service orchestration |
| `.env.example` | env | All config/secrets; copy to `.env` before running |
| `README.md` | docs | Full usage docs (read it first) |

## Commands

```bash
# Build & run everything (from repo root)
docker compose up -d --build

# Status / logs
docker compose ps
docker compose logs -f gateway

# Health checks
curl localhost:8080/health   # gateway
curl localhost:8081/health   # feature-service
curl localhost:8082/health   # selector-service
curl localhost:8083/health   # encryption-service

# Single encrypt request (requires GATEWAY_API_KEY in .env)
curl -X POST http://localhost:8080/api/v1/encrypt-image \
  -H "X-API-Key: $GATEWAY_API_KEY" -F "file=@sample.jpg"

# Batch encryption (reads GATEWAY_API_KEY automatically from root .env)
python client/batch_runner.py <dataset_folder> [api_url] [output_csv]

# Inspect logs DB (volume ./data/encryption:/data)
sqlite3 data/encryption/logs.db "SELECT id, filename, method, psnr FROM encryption_logs ORDER BY id DESC LIMIT 10;"
```

There is **no test suite, no linter config, no CI** in this repo. Verify changes
by running the services (docker compose) and hitting the endpoints with curl.

## Service Contracts (must stay in sync)

The gateway hard-codes route paths and JSON shapes. If you change any service's
route or response fields, update the matching Go structs in `gateway/main.go`
and the `client/batch_runner.py` CSV mapping.

- `POST /extractor/v1/analyze` (multipart `file`) ->
  `{entropy, size_kb, glcm_correlation, glcm_contrast}`
- `POST /selector/v1/predict` (JSON) ->
  `{decision_code: 0|1|2, recommended_cipher, reasoning}`
- `POST /encryption/v1/process` (multipart `file` + form field `cipher_mode`) ->
  `{method, encryption_time, decryption_time, cipher_entropy, psnr, output_filename, cipher_base64}`
- `GET /encryption/v1/logs` -> `{status, data: [{id, filename, method, ...}]}`
- Gateway public: `GET /health`, `GET /api/v1/logs` (CORS-enabled for `web/analytics.html`)

`cipher_mode` values the encryption service accepts: `UHC`, `Blowfish`, anything
else defaults to **Hybrid**. PSNR is a string and `"∞"` means lossless.

## Key Gotchas

- **`.env` is required.** Copy `.env.example` to `.env`. `GATEWAY_API_KEY`
  guards `/api/v1/encrypt-image`; if unset the gateway returns `503` (fail-closed)
  and warns at startup.
- **`client/batch_runner.py` validates the API key is exactly 64 chars** and
  reads it by parsing the root `.env` file directly (not python-dotenv). Do not
  change the `GATEWAY_API_KEY=` line format.
- **Blowfish uses `cryptography.hazmat.decrepit`** (moved from `algorithms` in
  newer cryptography versions) — keep `cryptography==43.0.1` pinned, upgrades may
  break imports. PKCS7 block size is 64-bit.
- **UHC matrix math is done mod 256 on `int32`**, and the key matrix inverse is
  recomputed per call. Encrypt & decrypt MUST use identical
  `UHC_MATRIX_SIZE` / `UHC_PASSWORD2` from `.env` or decryption will corrupt the
  image (PSNR check catches this).
- **Selector model is a placeholder.** On startup it tries `joblib.load("ai_selector_model.pkl")`;
  if missing it trains a synthetic random DecisionTree (seed 42) and dumps it.
  The pkl is written into the container and is not in git. Real training data
  should replace `train_default_model()`.
- **`selector-service/app.py` uses `@app.on_event("startup")`** (deprecated FastAPI
  pattern). Don't "modernize" it accidentally into an async signature mismatch.
- **Logs endpoint returns only the latest 100 rows** (`LIMIT 100` in
  `encryption-service/app.py`); the analytics page shows the last 30.
- **The encryption service opens one shared SQLite connection** at import time
  with `check_same_thread=False`; the logs table is created on startup.
- **Do not commit `.env`, `*.pkl`, dataset folders, or `data/`** to git.

## Environment Variables

| Var | Used by | Purpose |
| --- | --- | --- |
| `GATEWAY_API_KEY` | gateway, batch_runner | Client auth for `/api/v1/encrypt-image` |
| `SECRET_KEY` | encryption-service | Blowfish key (must be exact byte length for CBC) |
| `UHC_MATRIX_SIZE` | encryption-service | Hill cipher matrix dimension `n` |
| `UHC_PASSWORD2` | encryption-service | Seeds logistic map: `x0 = float("0." + PWD2 + "1")` |
| `DB_PATH` | encryption-service | SQLite file (default `/data/logs.db`) |
| `*_SERVICE_URL` | gateway | Internal service URLs (overridden in compose) |

## Common Tasks

- **Add an encryption algorithm**: extend `cipher_mode` branches in
  `encryption-service/app.py`, update payload tag parsing in decrypt, add a new
  tag byte string (e.g. `b"XXX"`), and document the new mode in the gateway README.
- **Change the AI selection logic**: edit `train_default_model()` in
  `selector-service/app.py`; keep `decision_code` mapping `0/1/2` and the response
  shape or update the gateway + client CSV columns.
- **Change the CSV output columns**: update `fieldnames` in
  `client/batch_runner.py` AND the JSON parsing in `main()`. Resume logic keys
  off `relative_path` with an empty `error` column.
- **Add gateway endpoints**: register in `main()`, wrap with `requireAPIKey` if
  protected, keep `writeJSONError` for JSON errors.

## Style Notes

- Go: stdlib only (no go.mod deps), plain `net/http`, no framework.
- Python: FastAPI + pydantic v2, `async` for upload handlers, module-level
  globals for model/DB. No type-checking config.
- The `client/batch_runner.py` and web analytics UI intentionally use
  Indonesian user-facing strings — preserve that.
- UI files are hand-written Tailwind; keep the green `primary` palette and the
  `lang-block` / `?lang=id|en` bilingual mechanism in `index.html`.
- Follow existing conventions; do not introduce new frameworks or dependencies
  without strong justification.
