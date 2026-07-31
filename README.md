# METAKS

METAKS'ın depo/katalog sistemi. Tek depo, iki dizin:

- **`veritabani/`** — PostgreSQL şeması ve migration'lar, veri temizleme/normalizasyon
  pipeline'ı, docker servisleri (Postgres + görsel sunucu), ürün görselleri.
  Şema ve verinin otoritesi burası.
- **`web/`** — Django + HTMX web arayüzü: ürün kataloğu, stok durumu, stok işlemleri,
  hareket geçmişi, ürün ve lokasyon/kullanıcı yönetimi.

Ayrıntılı mimari bağlam ve kararlar her iki dizinin kendi `CLAUDE.md`'sinde; depo
geneli için kökteki `CLAUDE.md`.

## Hızlı başlangıç

```bash
cd veritabani && docker compose up -d      # Postgres (5433) + görsel sunucu (8083)

cd ../web
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000    # adres argümanı Tailscale erişimi için şart
```

## Tarihçe

2026-07-31'e kadar bu iki dizin ayrı repolardı (`metaks_DB` ve `depo-web-arayuz`);
her ikisinin geçmişi de korunarak tek depoda birleştirildi. Aynı gün, bir süre
`web/`in yanında çalışan düşük-kod arayüz projeden tamamen çıkarıldı; yedeği
`~/arsiv-appsmith/` altında.
