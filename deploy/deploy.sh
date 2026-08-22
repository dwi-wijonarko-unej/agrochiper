#!/usr/bin/env bash
#
# deploy.sh — Deploy AgroCipher ke server.
#
# Dipanggil otomatis oleh GitHub Actions (.github/workflows/deploy.yml)
# tapi juga bisa dijalankan manual via SSH di server:
#     cd /opt/agrochiper && bash deploy/deploy.sh
#
set -euo pipefail

DEPLOY_DIR="/opt/agrochiper"
GIT_REMOTE="origin"
GIT_BRANCH="main"

cd "$DEPLOY_DIR"

if [ ! -f .env ]; then
  echo "ERROR: .env tidak ada di $DEPLOY_DIR." >&2
  echo "       Salin dari .env.example lalu isi secret asli:" >&2
  echo "         cp .env.example .env" >&2
  echo "       Jangan deploy dengan secret placeholder." >&2
  exit 1
fi

echo "==> Menarik kode terbaru dari ${GIT_REMOTE}/${GIT_BRANCH}"
git fetch "$GIT_REMOTE" "$GIT_BRANCH"
git reset --hard "$GIT_REMOTE/$GIT_BRANCH"

# Hapus container sisa dari compose project lain yang memegang nama
# "coffee-*" (mis. hasil clone di direktori berbeda). Nama-nama ini hanya
# didefinisikan di docker-compose.yml repo ini, jadi pemegangnya pasti
# milik aplikasi ini — tanpa pembersihan ini 'compose up' gagal dengan
# "Conflict. The container name ... is already in use".
# JANGAN lupa sinkron dengan container_name di docker-compose.yml.
echo "==> Membersihkan container bentrokan nama (jika ada)"
for c in coffee-gateway coffee-feature-service coffee-selector-service coffee-encryption-service coffee-web; do
  docker rm -f "$c" >/dev/null 2>&1 || true
done

echo "==> Build & start container"
docker compose up -d --build

# Bersihkan image lama yang tidak terpakai (opsional)
docker image prune -f >/dev/null 2>&1 || true

echo "==> Menunggu health check semua service (max 60s)"
for _ in $(seq 1 30); do
  ok=1
  for port in 8080 8081 8082 8083; do
    if ! curl -fsS "http://localhost:${port}/health" >/dev/null 2>&1; then
      ok=0
      break
    fi
  done
  if [ "$ok" = "1" ]; then
    echo "==> Semua service sehat (gateway, feature, selector, encryption)."
    echo "==> Deploy berhasil."
    exit 0
  fi
  sleep 2
done

echo "ERROR: Timeout menunggu health check. Cek 'docker compose logs'." >&2
exit 1