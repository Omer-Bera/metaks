#!/usr/bin/env bash
set -euo pipefail

# METAKS DB yedekleme scripti
#
# Ne yapar:
#   1) PostgreSQL'i docker exec ile pg_dump (custom format, -Fc) kullanarak
#      tarih damgalı bir dosyaya yedekler, $RETENTION_DAYS'ten eski dump'ları siler.
#   2) images/final/products/ klasörünü rsync ile yedek hedefine aynalar
#      (yalnızca ekler/günceller, kaynağı asla silmez: --delete YOK).
#
# Şu an yalnızca YEREL yedek alır (bu Mac üzerinde, varsayılan: repo_kök/backups/).
# CLAUDE.md'deki "ayrı fiziksel lokasyon" hedefi için BACKUP_DEST'i harici bir
# diske/bağlı bir NAS yoluna ayarlayıp tekrar çalıştırmak yeterli:
#
#   BACKUP_DEST=/Volumes/YedekDisk/metaks scripts/maintenance/yedek_al.sh
#
# Geri yükleme (DB):
#   docker exec -i depo-postgres pg_restore -U depo_admin -d depo_sistemi \
#     --clean --if-exists < backups/db/depo_sistemi_YYYYmmdd_HHMMSS.dump

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DEST="${BACKUP_DEST:-$BASE_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

DB_DEST="$BACKUP_DEST/db"
IMG_DEST="$BACKUP_DEST/images"
mkdir -p "$DB_DEST" "$IMG_DEST"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="$DB_DEST/depo_sistemi_${TIMESTAMP}.dump"

echo "[1/3] PostgreSQL yedeği alınıyor -> $DUMP_FILE"
docker exec depo-postgres pg_dump -U depo_admin -Fc depo_sistemi > "$DUMP_FILE"

echo "[2/3] ${RETENTION_DAYS} günden eski dump'lar temizleniyor"
find "$DB_DEST" -name 'depo_sistemi_*.dump' -mtime "+${RETENTION_DAYS}" -print -delete

echo "[3/3] Ürün görselleri senkronize ediliyor -> $IMG_DEST"
rsync -a "$BASE_DIR/images/final/products/" "$IMG_DEST/"

echo "Tamamlandı: $TIMESTAMP"
