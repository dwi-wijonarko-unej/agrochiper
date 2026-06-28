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
