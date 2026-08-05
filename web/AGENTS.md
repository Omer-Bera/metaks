# AGENTS.md — METAKS web arayüzü

Bu dosya `web/` altındaki Django + HTMX uygulaması için kalıcı geliştirme
kurallarını içerir. Depo genelindeki branch, şema ve dosya paylaşımı kuralları için
önce [kök AGENTS.md](../AGENTS.md) dosyasını okuyun. Yayın, Raspberry Pi, sırlar,
HTTPS ve yedekleme kararlarının tek kaynağı
[Güvenlik ve yayına hazırlık](../GUVENLIK_VE_YAYINA_HAZIRLIK.md) belgesidir.

Sıradaki arayüz işleri [YAPILACAKLAR.md](YAPILACAKLAR.md) içinde izlenir. Bu
dosyaya geçici canlı veri sayıları, tek kullanımlık test günlükleri veya tamamlanan
işlerin uzun tarihçesi eklenmez.

## Uygulama sınırı

- `web/`, METAKS'ın Django arayüzüdür; şema ve iş verisinin otoritesi
  `../veritabani/` dizinidir.
- Tek Django app'i `katalog/`dur. URL'ler `katalog/urls.py`, genel okuma ve stok
  akışları `views.py`, kullanıcı yönetimi `yonetim.py`, lokasyon yönetimi
  `lokasyon_yonetimi.py`, ürün yazma akışları `urun_yonetimi.py` içindedir.
- Şema sözleşmesi için
  [`aktif-urun-veri-sozlesmesi.md`](../veritabani/docs/aktif-urun-veri-sozlesmesi.md)
  ve migration 008 sonrasındaki stok yüzeyleri için
  [`stok-urun-veri-sozlesmesi.md`](../veritabani/docs/stok-urun-veri-sozlesmesi.md)
  otoritedir. Django aynı kuralları ikinci kez tanımlamaz.

## Geliştirme komutları

Bu dizinin venv'i `veritabani/venv` ile karıştırılmamalıdır:

```bash
cd ~/metaks/web
source venv/bin/activate
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

`0.0.0.0:8000` geliştirme sırasında Tailscale veya başka bir cihazdan erişim için
gereklidir. Gerçek kullanıma açılırken `runserver` kullanılmaz; yayın koşulları kök
güvenlik belgesindedir.

Yerel servisler kullanılacaksa `../veritabani/` içinden `docker compose up -d`
çalıştırılır. Raspberry Pi'deki ortak geliştirme kopyısına bağlanılıyorsa iki DB
host'u ve görsel URL'si `.env` ile değiştirilir; ayrıntı `README.md` ve kök güvenlik
belgesindedir.

## İki veritabanı, iki şema evrim yolu

`config/settings.py` iki Postgres bağlantısı tanımlar:

- `default` (`metaks_web`): Django auth, session, admin ve Django migration'ları.
- `metaks` (`depo_sistemi`): ürün, stok, lokasyon ve iş verisi. Şeması yalnız
  `../veritabani/sql/01_schema.sql` ile numaralı SQL migration'lar tarafından
  yönetilir.

Kesin kurallar:

- `python manage.py migrate` yalnız `default` için çalıştırılır. Tercihen komutta
  `--database=default` açıkça yazılır.
- `metaks` bağlantısında asla Django migration'ı çalıştırılmaz.
- `metaks` tablolarını/view'larını eşleyen bütün modeller `managed = False` kalır.
- Projede `DATABASE_ROUTERS` yoktur. Bu nedenle her METAKS sorgusu açıkça
  `.using('metaks')` kullanmalıdır; aksi hâlde sorgu sessizce `default`a gider.
- İki veritabanı arasında ORM JOIN kurulmaz. Gereken özetler toplu sorgularla
  alınır ve Python'da eşleştirilir; kullanıcı başına N+1 sorgu yazılmaz.

## Yazma kapıları

- `stok_hareketleri`ne doğrudan `INSERT` yoktur. Django yalnız
  migration 008 sonrasında `stok_servisi.stok_islemi_kaydet()` üzerinden
  `stok_islemi_kaydet()` çağırır ve
  veritabanının döndürdüğü Türkçe mesajı taşır.
- `urunler`e doğrudan `INSERT/UPDATE` yoktur. Yazma yolu
  `urun_servisi` üzerinden `urun_kaydet()` fonksiyonudur.
- Yeterli stok, işlem amacına göre defter etkisi, lokasyon, SKU/parti/durum,
  SAYIM_DEVRİ farkı ve mükerrer istek gibi iş kuralları Python veya JavaScript'te
  kopyalanmaz.
- Lokasyon ekleme/pasife alma/silme bu iki fonksiyonun dışında kalan bilinçli
  istisnadır. Kurallar SQL kısıtlarındadır; `IntegrityError` kısıt adına göre
  kullanıcı mesajına çevrilir.
- Django auth kullanıcıları yalnız `default` bağlantısında yönetilir.

## Cross-DB form tuzakları

`ModelForm` ve `ModelChoiceField`, varsayılan manager üzerinden otomatik sorgu
üretebilir. Router olmadığı için bu sorgular yanlış veritabanına gidebilir.

- METAKS modelini kullanan seçim alanlarının queryset'i `__init__` içinde açıkça
  `.using('metaks')` ile atanır.
- `unique=True` veya otomatik `validate_unique()` eklemeden önce hangi bağlantıda
  sorgu üreteceği kontrol edilir. Lokasyon tekilliğinin otoritesi Postgres
  kısıtlarıdır.
- `Lokasyon` yazma modelidir; okunur `kod`, `tam_ad` ve `yaprak_mi` gereken yerlerde
  `LokasyonDetay` (`v_lokasyonlar_detay`) kullanılır.
- Generated-always kolonlar Django yazma modeline eklenmez; Django `INSERT`
  sırasında bu kolonlara değer göndermeye çalışabilir.

## Ürün güncelleme ve görsel dosyaları

`urun_kaydet(..., mod='GUNCELLE')` kısmi güncelleme yapmaz; ürünün bütün alanlarını
yeniden yazar. Düzenleme formu mevcut alanların tamamını doğru `initial` değerlerle
doldurmalıdır. Yeni alan eklenirken formun GET→POST round-trip'i boş bırakılan başka
alanları `NULL`a çevirmemelidir.

Ürün görsellerinde iki ayrı erişim yolu vardır:

- `GORSEL_SUNUCU_BASE_URL`: tarayıcının nginx üzerinden okuduğu HTTP adresi.
- `URUN_GORSEL_DIZINI`: Django sürecinin yeni görsel yazdığı dosya sistemi yolu.

Görsel dosyası önce yazılır, DB fonksiyonu reddederse yalnız o isteğin yeni dosyası
geri alınır. Var olan görseller kendiliğinden silinmez. Django başka bir cihazda
çalışıp Pi veritabanına bağlanıyorsa yerel dosyaya yazılan görsel Pi nginx'inde
görünmez; böyle bir ortamda ürün görseli yazma işlemi yapılmamalı veya açıkça ortak
bir yazma yolu yapılandırılmalıdır.

## Stok ve lokasyon semantiği

- Ürün kodu tasarım/model kimliğidir; fiziksel olarak birbirinin yerine sevk
  edilemeyen kaplama, boya/mine ve montaj kombinasyonu `stok_kalemleri` içindeki
  SKU'dur. Eski aynı kodlu SKU `BELIRSIZ` varyanttır, ham sayılmaz.
- `v_stok_bakiye` SKU × lokasyon × durum × parti bakiyesidir. Sayım alanı fark
  değil, personelin saydığı toplamdır; farkı `stok_islemi_kaydet()` hesaplar.
- Fiziksel konum ile kullanılabilirlik bağımsızdır. Durum `SERBEST`,
  `KALITE_BEKLIYOR` veya `BLOKE`; parti/lot ise yalnız ihtiyaç olan akışlarda
  seçilir.
- Numune ayrı ürün veya ayrı veritabanı değildir; `NUMUNE` tipli lokasyondaki
  fiziksel stoktur. Fason mal da ayrı veritabanında değil, iş emrine bağlı FASON
  lokasyonunda METAKS mülkiyetinde kalır.
- Sahip olunan, tesis içi, satışa hazır, fasonda, numunede, kalite bekleyen ve
  bloke toplamların otoritesi `v_stok_urun_ozet`tir; eski `v_toplam_stok` bu
  ayrımlar için kullanılmaz.
- Hareket yalnız aktif `yaprak_mi=True` lokasyona yazılır. Pasif lokasyon geçmişte
  gösterilebilir ama yeni harekette seçilemez.

## Zaman, HTMX ve frontend

`stok_hareketleri.islem_tarihi` naive UTC değer tutar. Gösterim ve tarih filtresi
`models.yerel_tarih()` üzerinden yapılır; ham kolonu yerel gün sınırı gibi
yorumlamak üç saatlik kayma üretir.

Katalog/stok liste view'ları normal istek, ilk HTMX takası ve sonsuz kaydırma için
farklı parçalar döndürür. Filtre durumu canlı DOM'daki `#filtre-durumu` üzerinden
taşınır; kategori paneli out-of-band takasla güncellenir. Bu yapıyı değiştirirken
arama odağı, çoklu kategori seçimi ve sonsuz kaydırma birlikte doğrulanmalıdır.

Hızlı stok ekranında öneri listesi ile işlem formunun hedefleri ayrıdır. İkisini
aynı HTMX hedefine bağlamak gecikmiş öneri isteğinin açılan formu ezmesine yol açar.

Tailwind ve HTMX şu anda CDN'den gelir; Node/derleme adımı yoktur. CDN, HTTPS,
SECRET_KEY, DEBUG ve servis sunucusu konuları yayın öncesi güvenlik listesinin
parçasıdır; burada ikinci bir güvenlik listesi tutulmaz.

## Yetki ve test disiplini

- Katalog anonim kalabilir; stok ve hareket verileri `stok_goruntule` /
  `hareket_goruntule` izinleri olmadan sorgulanmaz veya gösterilmez.
- Stok yazma, sayım, düzeltme ve fason yönetimi ayrı Django izinleridir. Hazır
  gruplar görüntüleyici, operatör, fason sorumlusu ve stok yöneticisidir; `is_staff`
  geçiş süresince bütün stok izinlerine sahiptir.
- `katalog/tests.py` veritabanısız yetki/yönlendirme testleri içerir. Django test
  runner'ını canlı/paylaşılan `depo_sistemi`ne karşı çalıştırmayın ve onun için
  otomatik test DB'si oluşturmasına izin vermeyin.
- Yazma entegrasyonu gerekiyorsa geçici/test veritabanı veya geri alınan transaction
  kullanın; canlı deftere test satırı bırakmayın.

## Belge güncelleme alışkanlığı

Bir arayüz işi tamamlandığında `YAPILACAKLAR.md` içindeki açık maddeyi kapatın ve
karar kaydı tablosuna tarih + kısa gerekçe ekleyin. Canlı satır sayıları, kişisel
makine durumu ve tek seferlik test kontrol listeleri belgeye yazılmaz; gerektiğinde
veritabanından ölçülür veya Git geçmişinden bulunur.
