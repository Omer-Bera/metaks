# veritabani — METAKS veri ve şema katmanı

`metaks` deposunun iki dizininden biri (diğeri `web/`). Şemanın ve verinin otoritesi
burasıdır: ürün kataloğunu temizleyip normalleştiren pipeline, PostgreSQL şeması ve
migration'ları, docker servisleri ve ürün görselleri.

- **Nerede kaldık, sırada ne var:** `docs/INFO.md` ("Güncel Çalışma Noktası", "Sonraki Fazlar").
- **Mimari bağlam ve kalıcı kurallar:** buradaki `CLAUDE.md`, depo geneli için kökteki `CLAUDE.md`.
- **Arayüzün okuduğu view/fonksiyon sözleşmesi:** `docs/aktif-urun-veri-sozlesmesi.md`.

## Servisler

```bash
docker compose up -d      # bu dizinden çalıştırılır
```

İki servis kalkar: `depo-postgres` (Postgres 16, port **5433**) ve `depo-gorsel-sunucu`
(nginx, port **8083**, `images/final/products`'ı salt-okunur sunar).

Compose projesi `docker-compose.yml`'de `name: metaks_db` ile **sabitlenmiştir** —
canlı veritabanı `metaks_db_pg_data` volume'ünde duruyor, bu satır silinirse compose
dizin adından yeni ve boş bir volume türetir. Elle bağlanmak için:

```bash
docker exec -it depo-postgres psql -U depo_admin -d depo_sistemi
```

## Klasörler

| Yol | İçerik |
| --- | --- |
| `sql/01_schema.sql` | **Güncel şema.** docker-compose bunu `docker-entrypoint-initdb.d`'ye mount eder |
| `sql/migrations/` | Numaralı migration'lar (`00N_x.sql` + `00N_x_rollback.sql`), elle uygulanır |
| `sql/legacy/init_db.sql` | Eski/basit şema, hiçbir yerde kullanılmıyor — yalnızca referans |
| `scripts/cleaning/` | Aşama 1: temizle, olcu_temizle, duzelt, ayir |
| `scripts/normalization/` | Aşama 2–3: birleşik/karışık stok kodu çözümü, final Excel |
| `scripts/maintenance/` | Tekrar silme, kalıp yedeği, arşivleme, `yedek_al.sh` |
| `scripts/database/` | `yukle.py`, `gorselleri_yukle.py`, CSV/Excel dışa aktarma, `urun_ara.py` |
| `scripts/images/` | Excel içindeki gömülü görselleri stok koduyla eşleyen hat |
| `data/raw/` | `urun_listesi.xlsx` — görsel gömülü ham kaynak (~195 MB, gitignored) |
| `data/interim/` | Pipeline ara çıktıları |
| `data/processed/` | `temiz_urunler_final_v2.xlsx` — DB'ye yüklenen nihai veri |
| `data/reference/` | Kalıp yedeği, arşivlenen ürün listesi, manuel eşlemeler |
| `images/final/products/` | Aktif ürün görselleri (DB ile eşleşen, 1.799 dosya) |
| `images/arsiv/products/` | Yeni stok kodlarıyla eşleşmeyen arşiv görselleri (934 dosya) |
| `images/working/products/` | Çalışma kopyası + ham eşleme raporu |
| `reports/excel/` | Denetim ve dönüşüm raporları, `veritabani_guncel_durum.xlsx` (canlı DB aynası) |
| `docker/nginx/` | Görsel sunucusunun nginx yapılandırması |
| `docs/` | INFO.md (durum/yol haritası), veri sözleşmesi, karışık stok kodu kuralı |
| `archive/` | Aktif hattın dışında kalan eski script/veri/notebook'lar (gitignored) |
| `backups/` | `yedek_al.sh` çıktısı: pg_dump + görsel aynası (gitignored) |

## Ortam

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
source venv/bin/activate
```

Bu venv `web/venv` ile **karıştırılmamalıdır** — biri pandas/psycopg2 pipeline'ı, diğeri Django.

## Dosya koruma

Yedek almadan silinmemesi/toplu değiştirilmemesi gerekenler:

```text
data/raw/urun_listesi.xlsx            # Excel yeniden kaydı görsel anchor'larını kaydırabilir
data/processed/temiz_urunler_final_v2.xlsx
data/reference/kalip_bilgileri_yedek.xlsx
images/final/products/
sql/01_schema.sql
scripts/database/yukle.py
```

Yazma tek kapıdan: `stok_hareketleri`'ne doğrudan INSERT yok (`stok_hareketi_kaydet()`),
`urunler`'e doğrudan INSERT/UPDATE yok (`urun_kaydet()`). Ayrıntı kökteki `CLAUDE.md`'de.
