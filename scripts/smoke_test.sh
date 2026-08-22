#!/usr/bin/env bash
#
# smoke_test.sh — Gerbang verifikasi PRA-PUSH untuk AgroCipher.
#
# Push ke branch `main` = auto-deploy produksi via GitHub Actions
# (.github/workflows/deploy.yml -> deploy/deploy.sh). JANGAN push/merge
# ke main sebelum script ini lulus semua langkah (exit 0).
#
# Usage:
#   bash scripts/smoke_test.sh [--no-build]
#
#   --no-build  lewati rebuild image (pakai container yang sudah jalan);
#               untuk iterasi cepat, bukan untuk gerbang final pra-push.
#
# Yang diverifikasi:
#   1. .env ada & GATEWAY_API_KEY terisi (idealnya tepat 64 karakter)
#   2. docker compose build + start sukses (perintah yang sama dengan deploy)
#   3. /health OK di keempat service (8080 gateway, 8081 feature,
#      8082 selector, 8083 encryption)
#   4. Fail-closed auth: POST /api/v1/encrypt-image tanpa key -> 401,
#      dengan key salah -> 401
#   5. Happy path round-trip: features lengkap, decision_code 0/1/2,
#      method terisi, cipher_entropy tinggi, PSNR lossless/tinggi
#      (PSNR rendah = dekripsi merusak gambar)
#
# Prasyarat: docker, docker compose, curl, python3. Tidak butuh file gambar —
# test image PNG noise di-embed di dalam script ini.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

GATEWAY_URL="http://localhost:8080"
COMPOSE_LOG="/tmp/agrocipher_smoke_compose.log"
RESP_FILE="$(mktemp)"
IMG_FILE="/tmp/agrocipher_smoke_noise.png"
trap 'rm -f "$RESP_FILE" "$IMG_FILE"' EXIT

PASS=0
FAIL=0

ok()  { PASS=$((PASS + 1)); printf '  [PASS] %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  [FAIL] %s\n' "$1"; }

summary() {
    echo "============================================="
    printf '  SMOKE TEST: %d PASS, %d FAIL\n' "$PASS" "$FAIL"
    if [ "$FAIL" -eq 0 ]; then
        echo "  Aman untuk merge/push ke main."
    else
        echo "  JANGAN push ke main sebelum semua FAIL diperbaiki."
    fi
    echo "============================================="
    [ "$FAIL" -eq 0 ] || exit 1
    exit 0
}

echo "==> [1/5] Validasi .env"
if [ ! -f .env ]; then
    bad ".env tidak ditemukan di root repo — jalankan: cp .env.example .env"
    summary
fi
ok ".env ditemukan"

API_KEY="$(grep -E '^GATEWAY_API_KEY=' .env | head -n1 | cut -d= -f2- | tr -d '\"' | tr -d '[:space:]')"
if [ -z "$API_KEY" ]; then
    bad "GATEWAY_API_KEY kosong — gateway akan fail-closed 503"
    summary
fi
if [ "${#API_KEY}" -ne 64 ]; then
    bad "GATEWAY_API_KEY harus tepat 64 karakter (sekarang: ${#API_KEY}) — client/batch_runner.py menolaknya"
    summary
fi
ok "GATEWAY_API_KEY valid (64 karakter)"

echo "==> [2/5] Build & start containers (docker compose)"
if [ "${1:-}" = "--no-build" ]; then
    if docker compose up -d >"$COMPOSE_LOG" 2>&1; then
        ok "compose start sukses (--no-build)"
    else
        bad "docker compose gagal — lihat log: $COMPOSE_LOG"
        summary
    fi
else
    if docker compose up -d --build >"$COMPOSE_LOG" 2>&1; then
        ok "compose build & start sukses"
    else
        bad "docker compose gagal — lihat log: $COMPOSE_LOG"
        tail -n 20 "$COMPOSE_LOG" || true
        summary
    fi
fi

echo "==> [3/5] Health checks (max ~60 detik)"
ALL_HEALTHY=0
for _ in $(seq 1 30); do
    ALL_OK=1
    for port in 8080 8081 8082 8083; do
        curl -fsS "http://localhost:${port}/health" >/dev/null 2>&1 || ALL_OK=0
    done
    if [ "$ALL_OK" -eq 1 ]; then
        ALL_HEALTHY=1
        break
    fi
    sleep 2
done
if [ "$ALL_HEALTHY" -eq 1 ]; then
    ok "/health 200 pada 8080 (gateway), 8081 (feature), 8082 (selector), 8083 (encryption)"
else
    for port in 8080 8081 8082 8083; do
        curl -fsS "http://localhost:${port}/health" >/dev/null 2>&1 \
            || bad "service di port $port tidak sehat (timeout health check)"
    done
    echo "  Hint: docker compose ps && docker compose logs --tail=50"
    summary
fi

# Test image: PNG grayscale 64x64 noise (entropi tinggi), di-embed agar
# script self-contained.
base64 -d <<'B64EOF' > "$IMG_FILE"
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
AABJRU5ErkJggg==
B64EOF

echo "==> [4/5] Negative test autentikasi"
CODE_NOKEY=$(curl -s -o /dev/null -w '%{http_code}' \
    -X POST "$GATEWAY_URL/api/v1/encrypt-image" -F "file=@$IMG_FILE")
if [ "$CODE_NOKEY" = "401" ]; then
    ok "POST tanpa API key ditolak 401"
else
    bad "POST tanpa API key harus 401, dapat HTTP $CODE_NOKEY"
fi
CODE_BADKEY=$(curl -s -o /dev/null -w '%{http_code}' \
    -X POST "$GATEWAY_URL/api/v1/encrypt-image" \
    -H "X-API-Key: $(printf 'x%.0s' $(seq 64))" \
    -F "file=@$IMG_FILE")
if [ "$CODE_BADKEY" = "401" ]; then
    ok "POST dengan API key salah ditolak 401"
else
    bad "POST dengan API key salah harus 401, dapat HTTP $CODE_BADKEY"
fi

echo "==> [5/5] Happy path: encrypt round-trip via gateway"
HTTP_CODE=$(curl -sS -o "$RESP_FILE" -w '%{http_code}' \
    -X POST "$GATEWAY_URL/api/v1/encrypt-image" \
    -H "X-API-Key: $API_KEY" \
    -F "file=@$IMG_FILE")
if [ "$HTTP_CODE" != "200" ]; then
    bad "gateway balas HTTP $HTTP_CODE (harus 200). Body:"
    head -c 500 "$RESP_FILE"; echo
    summary
fi

python3 - "$RESP_FILE" <<'PYEOF'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)

errors = []
features = data.get("features") or {}
selector = data.get("selector") or {}
result = data.get("result") or {}

decision_code = selector.get("decision_code")
if decision_code not in (0, 1, 2):
    errors.append(f"selector.decision_code invalid: {decision_code!r} (harus 0/1/2)")

method = result.get("method")
if not method:
    errors.append("result.method kosong")

psnr_raw = result.get("psnr")
psnr_str = "" if psnr_raw is None else str(psnr_raw)
if not psnr_str:
    errors.append("result.psnr hilang")
elif "\u221e" in psnr_str or "inf" in psnr_str.lower():
    pass  # lossless
else:
    try:
        if float(psnr_str) < 30.0:
            errors.append(f"result.psnr rendah ({psnr_str} dB) — indikasi dekripsi merusak gambar")
    except ValueError:
        errors.append(f"result.psnr tidak dikenal: {psnr_str!r}")

cipher_entropy = result.get("cipher_entropy")
if not isinstance(cipher_entropy, (int, float)):
    errors.append(f"result.cipher_entropy hilang/tidak numerik: {cipher_entropy!r}")
elif cipher_entropy < 7.0:
    print(f"  [WARN] cipher_entropy rendah: {cipher_entropy} (< 7.0)")
    errors.append(f"result.cipher_entropy terlalu rendah: {cipher_entropy}")

for key in ("entropy", "size_kb", "glcm_correlation", "glcm_contrast"):
    if key not in features:
        errors.append(f"features.{key} hilang dari respons")

print(
    f"  method={method}  decision_code={decision_code}  "
    f"psnr={psnr_str}  cipher_entropy={cipher_entropy}"
)

if errors:
    for err in errors:
        print(f"  ERROR: {err}")
    sys.exit(1)
sys.exit(0)
PYEOF

if [ $? -eq 0 ]; then
    ok "Round-trip encrypt valid (features + selector + result, PSNR & entropy sehat)"
else
    bad "Validasi respons gagal — lihat detail ERROR di atas"
fi

summary
