#!/bin/sh
# Actualización segura en servidor con almacenamiento en Cloudflare R2.
# Uso: ./scripts/deploy.sh

set -e
cd "$(dirname "$0")/.."

echo ">>> Verificando configuración R2 en .env..."
for var in R2_ENDPOINT_URL R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_BUCKET_NAME; do
  if ! grep -q "^${var}=" .env; then
    echo "ERROR: falta ${var} en .env"
    exit 1
  fi
done

echo ">>> Actualizando código..."
git pull --ff-only

echo ">>> Reconstruyendo y reiniciando API..."
docker compose up -d --build api

echo ">>> Deploy completado. Archivos en Cloudflare R2 (bucket: $(grep '^R2_BUCKET_NAME=' .env | cut -d= -f2))."
