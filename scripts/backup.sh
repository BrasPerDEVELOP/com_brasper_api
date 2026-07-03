#!/bin/sh
# Backup diario de com_brasper: base de datos (pg_dump) + media/ subida en disco.
# Pensado para correr por cron como root. Ejecutar manual: ./scripts/backup.sh
#
# Restaurar base de datos:
#   pg_restore --clean --if-exists -d com_brasper /var/backups/com_brasper/db_com_brasper_YYYYMMDD_HHMMSS.dump
# Restaurar media:
#   tar xzf /var/backups/com_brasper/media_YYYYMMDD_HHMMSS.tar.gz -C /var/www/com_brasper_api
#
# Off-site (recomendado): define BACKUP_REMOTE con un destino rsync/ssh
#   ej. BACKUP_REMOTE="usuario@otro-host:/ruta/backups"  o un bucket montado.
# Sin BACKUP_REMOTE los backups quedan SOLO en este servidor (mejor que nada, pero no
# protege ante perdida del disco/VPS).

set -eu

# --- Configuracion (sobreescribible por variables de entorno) ---
DB_NAME="${BACKUP_DB_NAME:-com_brasper}"
DB_OS_USER="${BACKUP_DB_OS_USER:-postgres}"                 # peer auth como usuario del SO
MEDIA_DIR="${BACKUP_MEDIA_DIR:-/var/www/com_brasper_api/media}"
DEST="${BACKUP_DEST:-/var/backups/com_brasper}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
REMOTE="${BACKUP_REMOTE:-}"                                 # opcional: destino rsync off-site

STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DEST"

DB_FILE="$DEST/db_${DB_NAME}_${STAMP}.dump"
MEDIA_FILE="$DEST/media_${STAMP}.tar.gz"

echo ">>> [$STAMP] Backup de base de datos ($DB_NAME)..."
if command -v sudo >/dev/null 2>&1 && [ "$(id -u)" -ne 0 ] 2>/dev/null; then
  sudo -u "$DB_OS_USER" pg_dump -Fc "$DB_NAME" > "$DB_FILE"
elif [ "$(id -un)" = "$DB_OS_USER" ]; then
  pg_dump -Fc "$DB_NAME" > "$DB_FILE"
else
  sudo -u "$DB_OS_USER" pg_dump -Fc "$DB_NAME" > "$DB_FILE"
fi

echo ">>> Backup de media ($MEDIA_DIR)..."
if [ -d "$MEDIA_DIR" ]; then
  tar czf "$MEDIA_FILE" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
else
  echo "AVISO: no existe $MEDIA_DIR, se omite backup de media"
fi

echo ">>> Rotando backups de mas de ${RETENTION_DAYS} dias en $DEST..."
find "$DEST" -type f \( -name 'db_*.dump' -o -name 'media_*.tar.gz' \) -mtime +"$RETENTION_DAYS" -delete

if [ -n "$REMOTE" ]; then
  echo ">>> Copiando off-site a $REMOTE..."
  rsync -az "$DB_FILE" ${MEDIA_FILE:+"$MEDIA_FILE"} "$REMOTE"/
else
  echo "AVISO: BACKUP_REMOTE no definido -> backup SOLO local en $DEST (sin copia off-site)"
fi

echo ">>> Backup completado. Ultimos archivos:"
ls -lh "$DEST" | tail -5
