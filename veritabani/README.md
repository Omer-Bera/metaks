# veritabani — METAKS veri ve şema katmanı

Bu dizin ürün kataloğunu temizleyen/normalleştiren veri hattını, PostgreSQL baz
şemasını ve migration'ları, veri aktarım araçlarını, Docker servislerini ve ürün
görsellerini içerir. Django + HTMX arayüzü kardeş `web/` dizinindedir.

- Çalışma kuralları: [`AGENTS.md`](AGENTS.md)
- Güncel durum ve yol haritası: [`docs/INFO.md`](docs/INFO.md)
- Arayüz veri sözleşmesi:
  [`docs/aktif-urun-veri-sozlesmesi.md`](docs/aktif-urun-veri-sozlesmesi.md)
- Karışık stok kodu kuralı:
  [`docs/karisik_stok_kodu_kurali.md`](docs/karisik_stok_kodu_kurali.md)

## Geliştirme araçlarını ve servisleri başlatma

Pipeline sanal ortamı Django'nunkinden ayrıdır:

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
source venv/bin/activate
```

Servisleri bu dizinden başlatın:

```bash
docker compose up -d
docker compose ps
```

İki servis açılır:

- `depo-postgres`: PostgreSQL 16, host portu `5433`;
- `depo-gorsel-sunucu`: ürün görsellerini salt-okunur sunan nginx, host portu
  `8083`.

Compose proje adı `name: metaks_db` ile sabittir. Bu ad mevcut
`metaks_db_pg_data` volume'ünü bulmak için gereklidir; değiştirmeyin. Portların
hangi host adresine bağlanacağı ignored `.env` içindeki `TAILSCALE_BIND_ADDRESS`
ile belirlenebilir; örnek için `.env.example` dosyasına bakın.

Elle veritabanı bağlantısı:

```bash
docker exec -it depo-postgres psql -U depo_admin -d depo_sistemi
```

## Şema modeli

Şema otoritesi `sql/01_schema.sql` ile `sql/migrations/` altındaki numaralı
migration'ların sıralı birleşimidir. `01_schema.sql` yalnızca yeni volume'e
kurulan baz şemadır ve canlı şemanın tek başına tam görüntüsü değildir.
Migration'lar Docker tarafından otomatik uygulanmaz.

Migration 006, belirli 30 tarihsel test hareketini silen koşullu bir veri
temizliğidir; fresh/boş kurulumda körlemesine uygulanmaz. Ayrıntılı uygulama ve
test kuralları `AGENTS.md` içindedir.

Boş ortamı güncel hâle getirmek düz bir `001`–`007` döngüsü değildir: migration
001 ürün/görsel verisine göre backfill yapar, 006 ise yalnız tarihsel canlı veriyi
temizler. Doğrulanmış dump geri yüklemek tercih edilir; sıfırdan yeniden üretim
sırası ve önkoşulları için `AGENTS.md` izlenmelidir.

Django, `depo_sistemi` bağlantısına `migrate` çalıştırmaz; bu şemaya bağlı tüm
modeller `managed = False` durumundadır.

Yazma kapıları:

- `stok_hareketleri` → yalnız `stok_hareketi_kaydet()`;
- `urunler` → yalnız `urun_kaydet()`.

## Dizinler

| Yol | İçerik |
| --- | --- |
| `sql/01_schema.sql` | Yeni kurulumun baz şeması |
| `sql/migrations/` | Sıralı ileri migration'lar ve rollback dosyaları |
| `scripts/cleaning/` | İlk temizlik aşamaları |
| `scripts/normalization/` | Tekilleştirme ve karışık stok kodu çözümü |
| `scripts/maintenance/` | Arşivleme, kalıp yedeği, tekrar temizliği ve yedek |
| `scripts/database/` | Yükleme, arama ve CSV/Excel dışa aktarma |
| `scripts/images/` | Excel görsellerini stok kodlarıyla eşleme ve raporlama |
| `data/raw/` | Gömülü görselli ham Excel kaynağı (gitignored) |
| `data/interim/` | Pipeline ara çıktıları |
| `data/processed/` | DB yükleme kaynağı ve üretilebilir çıktılar |
| `data/reference/` | Kalıcı referans ve arşiv kayıtları |
| `images/final/products/` | DB ile eşleşen, Django/nginx tarafından paylaşılan görseller |
| `images/arsiv/products/` | Aktif kapsam dışında tutulan görseller |
| `reports/excel/` | Dönüşüm ve denetim raporları |
| `backups/` | Yerel dump ve görsel kopyaları (gitignored) |

## Koruma ve yedek

Ham Excel, nihai yükleme dosyası, kalıp yedeği, aktif görsel dizini, baz şema ve
`scripts/database/yukle.py` yedeksiz silinmemeli veya toplu değiştirilmemelidir.
`yukle.py` katalog tablolarını temizleyip yeniden yüklediği için yıkıcı kabul edilir.

İki veritabanının dump'ını ve görsel kopyasını almak için:

```bash
scripts/maintenance/yedek_al.sh
```

Varsayılan `backups/` aynı disktedir; gerçek yedek için `BACKUP_DEST` ayrı bir
disk veya NAS yolunu göstermelidir.
