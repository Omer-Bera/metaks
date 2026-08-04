# web — METAKS arayüzü

METAKS'ın Django + HTMX arayüzü. Teknik geliştirme kuralları
[AGENTS.md](AGENTS.md), güvenlik ve Raspberry Pi düzeni
[kök güvenlik belgesi](../GUVENLIK_VE_YAYINA_HAZIRLIK.md), şema kurulumu ise
[`veritabani/README.md`](../veritabani/README.md) içinde açıklanır.

## Var olan geliştirme ortamını çalıştırma

Önce veri servislerinin nerede çalışacağını seçin:

- **Yerel Postgres/nginx:** `veritabani/` servislerini bu makinede başlatın.
- **Raspberry Pi geliştirme kopyası:** yerel Docker başlatmayın; `web/.env` içindeki
  `WEB_DB_HOST`, `METAKS_DB_HOST` ve `GORSEL_SUNUCU_BASE_URL` değerlerini Pi'ye
  yöneltin. Güncel adresler ve veri akışı kök güvenlik belgesindedir.

Yerel servisler için önce:

```bash
cd ~/metaks/veritabani
docker compose up -d
docker compose ps
```

Ardından web süreci:

```bash
cd ~/metaks/web
source venv/bin/activate
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

`runserver` geliştirme sunucusudur. `0.0.0.0:8000` Tailscale/başka cihaz erişimi
için gereklidir; gerçek kullanıma açılırken production sunucusu ve HTTPS gerekir.

## Yeni çalışma makinesi, mevcut merkezi veritabanı

Yeni makinede veritabanı kurmak gerekmiyorsa yalnız Python ortamını hazırlayın:

```bash
cd ~/metaks/web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` içindeki `change-me` değerleri çalışır parola değildir. İki DB bağlantısını
mevcut sunucunun gerçek bilgileriyle doldurun; sırları Git'e yazmayın. Pi'ye bağlanan
bir örnekte görsel URL'si de Pi adresini göstermelidir, çünkü bu URL'yi Django değil
tarayıcı açar.

Bağlantıyı doğrulayın:

```bash
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

Mevcut merkezi kopyıya bağlanan her çalışma makinesinde yeniden `migrate` çalıştırmak
gerekmez. Gerçek bir Django migration'ı uygulanacaksa hedef kopyıyı bilerek seçin ve
komutu `python manage.py migrate --database=default` olarak açık yazın.
`depo_sistemi` bağlantısında asla Django migration'ı çalıştırmayın.

## Tamamen temiz veritabanı sunucusu

Boş Docker volume ile `docker compose up -d`, yalnız temel `depo_sistemi`
veritabanını `veritabani/sql/01_schema.sql` üzerinden oluşturur. Güncel ve kullanılabilir
bir ortam için bundan sonra iki yoldan biri seçilmelidir:

1. **Önerilen: doğrulanmış yedeği geri yüklemek.** `depo_sistemi` ve `metaks_web`
   dump'larını birlikte geri yükleyin; ürün görsellerini de ayrı dosya yedeğinden
   taşıyın.
2. **Boş ortam kurmak.** `depo_sistemi` için uygulanabilir numaralı SQL
   migration'ları ve veri yükleyicilerini
   [`veritabani/AGENTS.md`](../veritabani/AGENTS.md) içindeki yeniden üretim sırasına
   göre çalıştırın. Bu işlem düz bir `001`–`007` döngüsü değildir: migration 001
   ürün/görsel verisine göre backfill yapar, 006 ise boş veritabanında uygulanmayan
   tarihsel veri temizliğidir. `metaks_web` veritabanını ayrıca oluşturup Django
   migration'larını çalıştırın.

Compose, temiz kurulumda `metaks_web` veritabanını kendiliğinden oluşturmaz. Önce
varlığını kontrol edin:

```bash
docker exec depo-postgres psql -U depo_admin -d postgres \
  -tAc "SELECT 1 FROM pg_database WHERE datname = 'metaks_web';"
```

Çıktı boşsa yalnız bir kez oluşturun:

```bash
docker exec depo-postgres createdb -U depo_admin metaks_web
```

Sonra `web/.env` bağlantı bilgilerini doldurup yalnız `default` şemasını kurun:

```bash
cd ~/metaks/web
source venv/bin/activate
python manage.py migrate --database=default
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

Mevcut bir volume veya merkezi Pi kopyısı üzerinde `createdb`, restore ya da SQL
migration adımlarını körlemesine tekrarlamayın. Önce hangi kopyanın veri otoritesi
olduğunu belirleyin; dump/restore ve görsel aktarımı kuralları kök güvenlik
belgesindedir.
