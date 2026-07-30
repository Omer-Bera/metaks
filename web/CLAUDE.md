# CLAUDE.md

Bu dosya, bu repo (`depo-web-arayuz`) üzerinde çalışırken Claude Code için rehberdir.

## Proje ve bağlam

METAKS'ın uzun vadeli (ERP niteliğinde) web arayüzü — Django + HTMX ile, 2026-07-30'da
başlatıldı. Bu repo, iki kardeş repoyla birlikte METAKS'ın toplam sisteminin üçüncü
parçasıdır (üçü de `~/` altında ayrı, kardeş dizinler, birbirine karıştırılmamalı):

- **`metaks_DB`** — veri temizleme/normalizasyon pipeline'ı + PostgreSQL şeması
  (`sql/01_schema.sql`, `sql/migrations/`). Gerçek veri kaynağı ve şema otoritesi burada.
- **`depo-appsmith-arayuz`** — Appsmith üzerinde kurulu, hâlâ **aktif kullanılan** düşük-kod
  arayüz (StokIslemi, UrunlerKatalog, LokasyonYonetimi, StokOzet, Dashboard sayfaları).
  Devam eden depo sayımı bunun üzerinden yürütülüyor — bu repo onu **değiştirmiyor**, ona
  paralel başlıyor.
- **`depo-web-arayuz`** (bu repo) — geleceğin arayüzü. Strangler-fig yaklaşımıyla,
  modül modül Appsmith'in yerini alması planlanıyor.

### Neden Django + HTMX, neden Appsmith'i hemen bırakmıyoruz

2026-07-30'da kullanıcıyla yapılan mimari değerlendirmenin sonucu (ayrıntılar o
konuşmada, burada özet): Appsmith'in widget modeli tekrarlayan/özel UI ihtiyaçlarında
(görsel kart ızgarası galerisi, ileride kanban/timeline/barkod akışları) her seferinde
Custom Widget yazmayı gerektiriyor — bu, low-code'un hız avantajını tam ihtiyaç anında
tersine çeviriyor. Django hem kullanıcının mevcut Python bilgisine hem AI-destekli
geliştirmeye (çok daha geniş training-data temsili) daha iyi oturuyor. Ama devam eden
depo sayımı gerçek bir aciliyet olduğu için Appsmith'teki `StokIslemi` akışı **bilerek
sökülmüyor** — kademeli geçiş planı:

1. Depo sayımı + günlük stok takibi → Appsmith'te devam eder.
2. Yeni geliştirilen her şey → burada (Django) başlar. İlk modül: salt-okunur ürün
   kataloğu/galerisi (en düşük riskli, en yüksek UX-etkili başlangıç).
3. Zamanla stok giriş/çıkış/sayım formları, sipariş, üretim, numune gibi modüller
   buraya taşınır/eklenir; Appsmith'in payı sıfıra iner.

## Mimari kararlar

### İki veritabanı bağlantısı (`config/settings.py`)

- **`default`** (SQLite, `db.sqlite3`, gitignored) — sadece Django'nun kendi çerçeve
  tabloları (auth, session, admin log). `python manage.py migrate` sadece buraya yazar.
- **`metaks`** (Postgres, `metaks_DB`'deki **aynı** paylaşımlı `depo_sistemi` veritabanı,
  `.env`'den okunan kimlik bilgileriyle) — gerçek METAKS verisi. Buraya **asla**
  `migrate` çalıştırılmaz; şema tamamen `metaks_DB/sql/01_schema.sql` +
  `sql/migrations/`'ın otoritesinde kalır.

Bu ayrımın bilinçli sebebi: `metaks_DB`'nin titizlikle sürdürdüğü ham-SQL migration
disiplinini (numaralı dosyalar, `BEGIN/COMMIT`, önce-test-sonra-uygula) Django'nun kendi
ORM-migration mekanizmasıyla aynı veritabanında çakıştırmamak. İki ayrı şema-evrim
mekanizması aynı fiziksel DB'de yaşamıyor.

Sonuç olarak `metaks` bağlantısına dokunan her model **`managed = False`** olmalı
(bkz. `katalog/models.py::AktifUrun`, `v_aktif_urunler` view'ının haritalaması) ve
sorgular açıkça `.objects.using('metaks')` kullanmalı — henüz bir `DATABASE_ROUTERS`
soyutlaması eklenmedi (tek app, tek bağlantı; ihtiyaç gerçek hâle gelmeden eklenmedi).

### Veri sözleşmesi

`v_aktif_urunler`, `v_lokasyon_stok_ozet`, `v_toplam_stok`, `stok_hareketi_kaydet()` —
tam alan listesi ve semantiği için **`metaks_DB/docs/aktif-urun-veri-sozlesmesi.md`**
otoritedir, burada tekrar edilmiyor. Appsmith de aynı sözleşmeyi okuyor; bu iki arayüz
aynı view/fonksiyon katmanını paylaşıyor, veri asla iki kez modellenmiyor.

Yazma işlemleri (stok hareketi) ileride buraya eklendiğinde de kural aynı kalacak:
doğrudan `stok_hareketleri`'ne INSERT yok, sadece `stok_hareketi_kaydet()` çağrısı
(Appsmith'in zaten uyduğu kural, bkz. `metaks_DB/CLAUDE.md`).

### Frontend

Şu an derleme adımı yok: Tailwind CSS ve HTMX CDN üzerinden yükleniyor
(`katalog/templates/katalog/base.html`). Bilinçli bir basitleştirme — Node/npm
toolchain'i gerçek bir ihtiyaç doğmadan (ör. Tailwind'in JIT'ini özelleştirme, offline
çalışma gereksinimi) eklenmedi. Üretime geçerken bu CDN bağımlılığı gözden geçirilmeli
(self-host edilebilir, offline/güvenlik duruşuyla daha tutarlı olur).

### Görsel sunucu

Ürün görselleri `metaks_DB`'nin kurduğu nginx `gorsel-sunucu` servisinden (port 8083)
okunuyor — burada görsel dosyası yönetimi/kopyası yok, tek kaynak orası
(`GORSEL_SUNUCU_BASE_URL` ayarı, `.env`).

## Geliştirme ortamı

```bash
cd ~/depo-web-arayuz
source venv/bin/activate        # bu repoya özel venv, metaks_DB/venv ile karıştırılmamalı
python manage.py runserver
```

`metaks_DB`'deki Postgres/nginx servislerinin ayakta olması gerekir
(`cd ~/metaks_DB && docker compose up -d`). `.env` gitignored — gerçek kimlik bilgileri
`metaks_DB/CLAUDE.md`'de belgelenen local bağlantı bilgileriyle aynı
(host=localhost port=5433 dbname=depo_sistemi user=depo_admin).

## Git

`metaks_DB` ve `depo-appsmith-arayuz` ile aynı desen izlenmesi planlanıyor: repo-scoped
`user.name`/`user.email` (global değil, zaten ayarlı), commit signing global 1Password
SSH agent config'inden miras alınıyor. GitHub remote'u henüz eklenmedi (2026-07-30
itibarıyla bilinçli olarak sadece lokal) — eklendiğinde `master`/`dev`/`review`
üç-branch modelinin buraya da uygulanması, diğer iki repoyla tutarlılık için mantıklı
olur ama henüz karar verilmedi.

## Durum (2026-07-30)

İlk iskelet kuruldu ve uçtan uca doğrulandı: Django ↔ `metaks` Postgres bağlantısı
gerçek veriyi okuyor (1.780 aktif ürün, `v_aktif_urunler` üzerinden), `katalog` app'i
tek bir sayfa sunuyor (`/`) — arama kutusu (HTMX, `arama_metni` üzerinden) + kart
ızgarası (görsel + stok kodu + kategori). Bu, tasarlanmış "kullanıcı dostu görsel
katalog" özelliğinin **başlangıç noktası**, henüz tam hâli değil — kategori filtresi,
sayfalama/infinite-scroll, detay paneli gibi asıl özellikler henüz yok.

Henüz yapılmadı: auth/yetkilendirme (henüz gerekmiyor, iç ağ + salt-okunur), hosting
(local'de geliştiriliyor, bulut VPS'e taşıma kullanıcı kararına bağlı), production
ayarları (DEBUG, SECRET_KEY, ALLOWED_HOSTS şu an sadece local dev için).
