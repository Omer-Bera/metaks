#!/usr/bin/env bash
set -euo pipefail

# METAKS DB yedekleme scripti
#
# Ne yapar:
#   1) İKİ veritabanını da docker exec ile pg_dump (custom format, -Fc) kullanarak
#      tarih damgalı dosyalara yedekler, $RETENTION_DAYS'ten eski dump'ları siler:
#        - depo_sistemi : METAKS verisi (ürünler, görseller, defter, lokasyonlar)
#        - metaks_web   : Django'nun kendi tabloları (KULLANICI HESAPLARI, oturumlar)
#      metaks_web 2026-07-31'de eklendi. Öncesinde Django'nun auth verisi
#      web/db.sqlite3'teydi ve HİÇBİR yedeğe girmiyordu (git'te de yok, gitignored) —
#      yani tüm hesaplar tek diskte tek kopyaydı. Postgres'e taşınmasının asıl
#      sebebi buydu; bkz. web/CLAUDE.md.
#   2) images/final/products/ klasörünü rsync ile yedek hedefine aynalar
#      (yalnızca ekler/günceller, kaynağı asla silmez: --delete YOK).
#
# Şu an yalnızca YEREL yedek alır (bu Mac üzerinde, varsayılan: repo_kök/backups/).
# DİKKAT: varsayılan hedef kaynakla AYNI DİSKTE, yani bu bir kopyadır, yedek değil —
# "yanlışlıkla sildim"e karşı korur, "Mac öldü"ye karşı korumaz. CLAUDE.md'deki
# "ayrı fiziksel lokasyon" hedefi için BACKUP_DEST'i harici bir diske/bağlı bir NAS
# yoluna ayarlayıp tekrar çalıştırmak yeterli:
#
#   BACKUP_DEST=/Volumes/YedekDisk/metaks scripts/maintenance/yedek_al.sh
#
# Geri yükleme (DB):
#   docker exec -i depo-postgres pg_restore -U depo_admin -d depo_sistemi \
#     --clean --if-exists < backups/db/depo_sistemi_YYYYmmdd_HHMMSS.dump
#   docker exec -i depo-postgres pg_restore -U depo_admin -d metaks_web \
#     --clean --if-exists < backups/db/metaks_web_YYYYmmdd_HHMMSS.dump

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DEST="${BACKUP_DEST:-$BASE_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

DB_DEST="$BACKUP_DEST/db"
IMG_DEST="$BACKUP_DEST/images"
mkdir -p "$DB_DEST" "$IMG_DEST"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Her veritabanı ayrı dump: birini geri yüklemek diğerine dokunmasın.
for DB in depo_sistemi metaks_web; do
  DUMP_FILE="$DB_DEST/${DB}_${TIMESTAMP}.dump"
  echo "[1/3] PostgreSQL yedeği alınıyor ($DB) -> $DUMP_FILE"
  docker exec depo-postgres pg_dump -U depo_admin -Fc "$DB" > "$DUMP_FILE"
done

echo "[2/3] ${RETENTION_DAYS} günden eski dump'lar temizleniyor"
find "$DB_DEST" \( -name 'depo_sistemi_*.dump' -o -name 'metaks_web_*.dump' \) \
  -mtime "+${RETENTION_DAYS}" -print -delete

echo "[3/3] Ürün görselleri senkronize ediliyor -> $IMG_DEST"
rsync -a "$BASE_DIR/images/final/products/" "$IMG_DEST/"

echo "Tamamlandı: $TIMESTAMP"
