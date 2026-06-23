#!/bin/sh
# Actualización segura en servidor: preserva media/ subida en disco.
# Uso: ./scripts/deploy.sh

set -e
cd "$(dirname "$0")/.."

echo ">>> Asegurando carpetas de media..."
for dir in home_banner home_popup profile_images transaction_vouchers; do
  mkdir -p "media/$dir"
done

if [ ! -f media/profile_images/placeholder.svg ]; then
  echo "ERROR: falta media/profile_images/placeholder.svg"
  exit 1
fi

if ! grep -q './media:/app/media' docker-compose.yml; then
  echo "ERROR: docker-compose.yml debe montar ./media:/app/media"
  exit 1
fi

echo ">>> Actualizando código..."
git pull --ff-only

echo ">>> Reconstruyendo y reiniciando API..."
docker compose up -d --build api

echo ">>> Deploy completado. Media en disco: $(find media -type f | wc -l | tr -d ' ') archivos"
