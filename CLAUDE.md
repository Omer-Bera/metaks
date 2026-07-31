# CLAUDE.md — METAKS (kök)

Bu dosya deponun tamamı için giriş noktasıdır. Asıl ayrıntı **alt dizinlerin kendi
`CLAUDE.md`'lerinde**; burada tekrarlanmıyor:

| Dizin | Ne var | Dili |
| --- | --- | --- |
| `veritabani/` | Veri temizleme/normalizasyon pipeline'ı, PostgreSQL şeması ve migration'lar, docker servisleri, ürün görselleri | İngilizce |
| `web/` | Django + HTMX web arayüzü (ERP) | Türkçe |

Bir işe başlarken hangisinin içinde çalışıyorsan **o dizinin `CLAUDE.md`'sini** oku;
ikisine birden dokunan bir iş (çoğu iş öyle) ikisini de gerektirir.

## Bu depo 2026-07-31'de iki repodan birleştirildi

Öncesinde `~/metaks_DB` ve `~/depo-web-arayuz` ayrı repolardı. Birleştirmenin
sebebi, kendi commit geçmişlerinde görünen bir olgu: son üç özelliğin **üçü de**
iki repoyu birden değiştirdi (migration 004 → Django'nun `yaprak_mi` filtresi,
005 → ürün ekleme ekranı, 006 → lokasyon silme) ve her biri iki ayrı repoda,
aralarında hiçbir bağ olmayan iki ayrı commit olarak düştü. Ayrıca veri sözleşmesi
`veritabani/docs/` altında ama `web/` kodunun otoritesi, ve `web/config/settings.py`
zaten "iki repo yan yana klonlanmış" varsayımıyla çalışıyordu.

İki geçmiş de **tamamen korundu** — yalnızca yollar alt dizine taşındı; her branch
için yeniden yazılmış ağaç hash'i eski repodaki kök ağaç hash'iyle birebir aynı
doğrulandı. Eski iki repo GitHub'da **arşivlendi, silinmedi**.

Bir üçüncü repo daha vardı: `depo-web-arayuz`'un yanında bir süre çalışan düşük-kod
arayüz (Appsmith). O **2026-07-31'de projeden tamamen çıkarıldı** — konteyneri
durduruldu, compose'dan silindi, docker volume'ü kaldırıldı, GitHub reposu
arşivlendi. Tam yedeği bu deponun **dışında**, `~/arsiv-appsmith/` altında
(volume tarball'ı + repo bundle'ı + geri getirme adımları). Geri dönüş
planlanmıyor; yeni bir view'ın anlamını değiştirirken ya da migration sırası
kurarken korunması gereken ikinci bir tüketici yok.

## Branch modeli

`veritabani/`nin belgelenmiş üçlü modeli tüm depo için geçerli:

- `master` — onaylanmış/stabil. **Yalnızca kullanıcının açık onayıyla** ileri sarılır.
- `dev` — çalışılan uç. Commit buraya.
- `review` — bilerek bir kontrol noktası geride; kullanıcının baktığı branch.
  Yeni bir iş birimine başlanırken `dev`'in bir önceki durağına yükseltilir.

Üçü ileri sarılabilir bir zincir: `master` → `review` → `dev`.

## İki tarafı birden ilgilendiren kalıcı kurallar

Bunlar tek bir dizinin meselesi olmadığı için burada duruyor:

- **Şema otoritesi `veritabani/sql/`'dir.** `01_schema.sql` + numaralı
  `sql/migrations/` dosyaları (`00N_x.sql` + `00N_x_rollback.sql`, her biri
  `BEGIN`/`COMMIT` içinde, önce-test-sonra-uygula). Django o veritabanına
  **asla** `migrate` çalıştırmaz; `metaks` bağlantısındaki her model
  `managed = False`.
- **Yazma tek kapıdan.** `stok_hareketleri`'ne doğrudan INSERT yok
  (`stok_hareketi_kaydet()`), `urunler`'e doğrudan INSERT/UPDATE yok
  (`urun_kaydet()`). İş kuralları veritabanı fonksiyonlarında; Django sadece
  parametre geçirip dönen Türkçe mesajı taşıyor.
- **Docker proje adı `veritabani/docker-compose.yml` içinde sabitlenmiştir**
  (`name: metaks_db`). Compose normalde projeyi dizin adından türetir ve
  volume'leri o önekle açar; bu birleştirmede dizin adı değiştiği için sabit ad
  olmasa var olan `metaks_db_pg_data` yerine **boş yeni bir volume** açılırdı.
  Compose komutları `veritabani/` içinden çalıştırılır.
- **Görsel dizini iki taraftan da kullanılıyor.** `veritabani/images/final/products`
  nginx tarafından `:ro` sunuluyor (port 8083, okuma) ve Django tarafından
  yazılıyor (`web/config/settings.py::URUN_GORSEL_DIZINI`). Dizin git'e girmiyor
  (`veritabani/.gitignore`), manuel yedekle korunuyor.

## Geliştirme ortamı

İki ayrı venv var, ayrı kalmalı (biri pandas/psycopg2 pipeline'ı, diğeri Django):

```bash
cd ~/metaks/veritabani && source venv/bin/activate      # pipeline script'leri
cd ~/metaks/web        && source venv/bin/activate      # Django

cd ~/metaks/veritabani && docker compose up -d          # Postgres + görsel sunucu
cd ~/metaks/web && python manage.py runserver 0.0.0.0:8000
```

`runserver`'ın adres argümanı Tailscale erişimi için şart — sebebi
`web/CLAUDE.md`'de.
