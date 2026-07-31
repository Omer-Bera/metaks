# CLAUDE.md

Bu dosya, deponun **`web/`** dizini (Django arayüzü) üzerinde çalışırken Claude Code
için rehberdir. Deponun tamamına dair giriş noktası kökteki `CLAUDE.md`'dir.

## Proje ve bağlam

METAKS'ın uzun vadeli (ERP niteliğinde) web arayüzü — Django + HTMX ile, 2026-07-30'da
başlatıldı. METAKS'ın toplam sistemi bugün tek bir depoda, iki dizinde:

- **`veritabani/`** — veri temizleme/normalizasyon pipeline'ı + PostgreSQL şeması
  (`sql/01_schema.sql`, `sql/migrations/`). Gerçek veri kaynağı ve şema otoritesi burada.
- **`web/`** (bu dizin) — arayüzün tamamı. Depo sayımı, stok takibi, katalog,
  ürün/lokasyon/kullanıcı yönetimi: hepsi burada.

**2026-07-31'e kadar bunlar iki ayrı repoydu** (`metaks_DB` ve `depo-web-arayuz`,
`~/` altında kardeş dizinler) ve o gün tek repoya alındı — gerekçe ve birleştirmenin
ayrıntıları kökteki `CLAUDE.md`'de. Bu dosyada bundan önce yazılmış "kardeş repo"
ifadeleri artık "kardeş dizin" olarak okunmalı.

### Neden Django + HTMX

2026-07-30'da yapılan mimari değerlendirmenin sonucu: bu ekranların ihtiyaç duyduğu
şeyler (görsel kart ızgarası galerisi, ileride kanban/timeline/barkod akışları)
düşük-kod widget modellerinde her seferinde özel widget yazmayı gerektiriyor — yani
low-code'un hız avantajı tam ihtiyaç anında tersine dönüyor. Django hem kullanıcının
mevcut Python bilgisine hem AI-destekli geliştirmeye (çok daha geniş training-data
temsili) daha iyi oturuyor.

Bu arayüz başlangıçta bir düşük-kod arayüzün (Appsmith) yanında, strangler-fig
yaklaşımıyla büyüdü. 2026-07-31'de o arayüz **projeden tamamen çıkarıldı**: yedeği
`~/arsiv-appsmith/` altında (volume tarball'ı + repo bundle'ı + geri getirme notu),
GitHub'daki reposu arşivlendi. Depoda ondan hiçbir iz kalmadı ve geri dönüş
planlanmıyor — yeni bir view'ın anlamını değiştirirken ya da migration sırası
kurarken artık korunması gereken ikinci bir tüketici yok.

## Mimari kararlar

### İki veritabanı bağlantısı (`config/settings.py`)

İkisi de Postgres, ikisi de **aynı** `depo-postgres` konteynerinde (port 5433), ama
**ayrı veritabanları**:

- **`default`** (`metaks_web`) — sadece Django'nun kendi çerçeve tabloları (auth,
  session, admin log). `python manage.py migrate` sadece buraya yazar.
- **`metaks`** (`depo_sistemi`) — gerçek METAKS verisi. Buraya **asla** `migrate`
  çalıştırılmaz; şema tamamen `veritabani/sql/01_schema.sql` + `sql/migrations/`'ın
  otoritesinde kalır.

Bu ayrımın bilinçli sebebi veritabanı **motoru** değil, **şema evrim mekanizmasıdır**:
`veritabani`'nin titizlikle sürdürdüğü ham-SQL migration disiplinini (numaralı dosyalar,
`BEGIN/COMMIT`, önce-test-sonra-uygula) Django'nun kendi ORM-migration mekanizmasıyla
aynı fiziksel veritabanında çakıştırmamak. İki ayrı veritabanı bu ayrımı, tek bir
motora inmenin bedeli olmadan sağlıyor.

#### `default` 2026-07-31'de SQLite'tan Postgres'e taşındı

Başlangıçta `default` SQLite'tı (`db.sqlite3`) — `startproject` varsayılanı. Yukarıdaki
gerekçe hiçbir zaman "SQLite iyidir" demiyordu, "iki migration mekanizması aynı DB'de
yaşamasın" diyordu; ayrı bir **veritabanı** bunu tamamen karşılıyor. Taşımanın iki
somut sebebi:

1. **Yedekleme boşluğu.** `db.sqlite3` ne git'teydi (gitignored — doğrusu da bu, parola
   hash'i içeriyor) ne de `veritabani/scripts/maintenance/yedek_al.sh`'de. Yani tüm
   kullanıcı hesapları tek diskte tek kopyaydı. Artık aynı `pg_dumpall` ikisini de
   kapsıyor.
2. **Yazma kilidi.** SQLite yazarken dosyanın tamamını kilitler; Tailscale üzerinden
   çok cihazlı erişimde oturum yazımı için gereksiz bir kısıt.

Taşınan veri: **1 kullanıcı**. Parola hash'i `dumpdata`/`loaddata` ile birebir korundu
(SHA-256'ları karşılaştırılarak doğrulandı), yani parola değişmedi. Oturumlar bilerek
taşınmadı — tek maliyeti bir kez yeniden giriş. Taşıma öncesi anlık görüntü
`web/db.sqlite3.yedek-2026-07-31` olarak duruyor (gitignore artık `db.sqlite3*`).

**Bu taşıma cross-DB tuzaklarını ÇÖZMEZ.** Aşağıdaki `using('metaks')` tuzakları
`default`'un SQLite olmasından değil, `DATABASE_ROUTERS` bulunmamasından kaynaklanıyor;
`default` Postgres olunca yalnızca hata mesajı değişir ("no such table" yerine
`relation does not exist"`), tuzak yerinde durur.

Sonuç olarak `metaks` bağlantısına dokunan her model **`managed = False`** olmalı
(bkz. `katalog/models.py::AktifUrun`, `v_aktif_urunler` view'ının haritalaması) ve
sorgular açıkça `.objects.using('metaks')` kullanmalı — henüz bir `DATABASE_ROUTERS`
soyutlaması eklenmedi (tek app, tek bağlantı; ihtiyaç gerçek hâle gelmeden eklenmedi).

### Veri sözleşmesi

`v_aktif_urunler`, `v_lokasyon_stok_ozet`, `v_toplam_stok`, `stok_hareketi_kaydet()` —
tam alan listesi ve semantiği için **`veritabani/docs/aktif-urun-veri-sozlesmesi.md`**
otoritedir, burada tekrar edilmiyor. Arayüz veriyi asla ikinci kez modellemiyor:
okuma bu view'lardan, yazma bu fonksiyonlardan geçiyor.

Yazma işlemlerinde kural mutlak: doğrudan `stok_hareketleri`'ne INSERT yok, sadece
`stok_hareketi_kaydet()` çağrısı (bkz. `veritabani/CLAUDE.md`).

### Frontend

Şu an derleme adımı yok: Tailwind CSS ve HTMX CDN üzerinden yükleniyor
(`katalog/templates/katalog/base.html`). Bilinçli bir basitleştirme — Node/npm
toolchain'i gerçek bir ihtiyaç doğmadan (ör. Tailwind'in JIT'ini özelleştirme, offline
çalışma gereksinimi) eklenmedi. Üretime geçerken bu CDN bağımlılığı gözden geçirilmeli
(self-host edilebilir, offline/güvenlik duruşuyla daha tutarlı olur).

Bu kısıt katalog galerisi yazılırken de korundu: hiç statik dosya sunulmuyor (favicon
bile `base.html` içinde satır içi SVG data URI), Tailwind Play CDN'e özgü
`<style type="text/tailwindcss">` bloğu bilinçli olarak kullanılmadı (self-host'a
geçişte taşınması gereken bir bağımlılık olurdu — utility sınıflarıyla ifade
edilemeyen üç şey için düz `<style>` yeterli oldu). JavaScript sadece HTMX'in
yapamadığı yerde: modal kapatma/`Esc`, arka plan kaydırma kilidi, görsel yükleme
hatasında yedek yer tutucu.

#### Kart ızgarası ve görsel boyutları

Kart görsel kutusu `aspect-[4/3]` (kare değil) ve detay panelinde görsel genişliği
420px'de sınırlı. İkisi de kaynak görsel korpusunun ölçülmesinden çıktı
(`veritabani/images/final/products`, 1.799 dosya): dosyaların **%79'u yatay**
(medyan ~3:2) ve **%55'i 200px'den dar**. Kare kutu yatay fotoğrafların altında/üstünde
büyük boşluk bırakıyordu; panelde tüm sütunu doldurmak ise yarıdan fazla görseli
3-4 katına büyütüp bulanıklaştırıyordu. Görseller `object-contain` ile gösteriliyor,
`object-cover` değil — kırpma bu küçük metal aksesuarların ayırt edici kenarını kesiyor,
oysa ekranın tek işi ürünü görselden tanıtmak.

### Görsel sunucu

Ürün görselleri `veritabani`'nin kurduğu nginx `gorsel-sunucu` servisinden (port 8083)
okunuyor — burada görsel dosyası yönetimi/kopyası yok, tek kaynak orası
(`GORSEL_SUNUCU_BASE_URL` ayarı, `.env`).

## Geliştirme ortamı

```bash
cd ~/metaks/web
source venv/bin/activate        # bu dizine özel venv, veritabani/venv ile karıştırılmamalı
python manage.py runserver 0.0.0.0:8000
```

### Ağ erişimi (Tailscale) — adres argümanı şart

`runserver`'ı **argümansız** çalıştırmak `127.0.0.1:8000`'e bağlar, yani sadece Mac'in
kendisinden erişilir; Tailscale'deki telefon/masaüstünden "site açılmıyor" demektir.
Docker servisleri (`8083`, `5433`) tüm arayüzlere bağlanıyor, yani onlar uzaktan
açılıyordu da Django açılmıyordu — fark tam olarak bu.

Uzaktan erişim için üç ayarın **üçü birden** gerekiyor:

1. **Bağlanma adresi** — `runserver 0.0.0.0:8000` (yukarıda). Yalnız tailnet isteniyorsa
   `runserver 100.64.0.6:8000`; o zaman yerel ağ göremez ama `127.0.0.1` de çalışmaz.
2. **`DJANGO_ALLOWED_HOSTS`** — Tailscale adresi eklenmezse Django `DisallowedHost`
   verip 400 döner. `.env`'de: `localhost,127.0.0.1,100.64.0.6,omer-macbook,.ts.net`.
3. **`GORSEL_SUNUCU_BASE_URL`** — en kolay atlanan. Bu URL'yi **tarayıcı** çözüyor,
   Django değil; `localhost:8083` yazarsa telefondan açıldığında telefonun kendisine
   gider ve **tüm ürün görselleri kırılır**. `http://100.64.0.6:8083/urun-gorselleri/`
   hem Mac'ten hem uzaktan çalışır.

`CSRF_TRUSTED_ORIGINS` **gerekmiyor**: düz HTTP'de aynı-kaynak istekte Django,
`Origin` başlığını `request.get_host()` ile karşılaştırıyor ve eşleşiyor. Tailscale
adresinden giriş POST'u doğrulandı (302 + oturum açıldı). HTTPS'e ya da bir ters
proxy arkasına geçildiğinde bu yeniden değerlendirilmeli.

macOS uygulama güvenlik duvarı açık ama tailnet erişimini engellemiyor (ölçüldü).

`veritabani/`deki Postgres/nginx servislerinin ayakta olması gerekir
(`cd ~/metaks/veritabani && docker compose up -d`). `.env` gitignored — gerçek kimlik
bilgileri `veritabani/CLAUDE.md`'de belgelenen local bağlantı bilgileriyle aynı
(host=localhost port=5433 dbname=depo_sistemi user=depo_admin).

## Git

Git ayarları artık **depo geneli** — `web/`in ayrı bir reposu yok. Remote, branch
modeli (`master`/`dev`/`review`) ve imzalama için kökteki `CLAUDE.md`'ye bakın.

Tarihçe: bu dizin 2026-07-30'da `Omer-Bera/depo-web-arayuz` adlı ayrı bir private
repoydu ve tek branch'i (`master`) vardı; üç-branch modeline geçmek tutarlılık için
mantıklı görünüyordu ama karar verilmemişti. 2026-07-31'deki birleştirme bu soruyu
kendiliğinden kapattı — depo `veritabani/`nin üçlü modelini kullanıyor.

`web/.gitignore` kapsamı: `.env`, `db.sqlite3` (uygulama kullanıcıları burada),
`venv/`. Yani hiçbir kimlik bilgisi ve parola hash'i depoya girmiyor.

## Sayfa yapısı

| Sayfa | URL | Ne yapar |
| --- | --- | --- |
| Giriş | `/giris/` | Giriş formu + "Giriş yapmadan devam et". Girişsiz `/`'in indiği yer |
| Panel | `/` | Modüllere yönlendirme, özet sayılar, son hareketler |
| Ürün Kataloğu | `/katalog/` | Görsel galeri. **Stoktan hiç söz etmez.** |
| Stok Durumu | `/stok/` | Aynı galeri + kart başına stok durumu + "sadece stokta olanlar" anahtarı + detayda lokasyon dökümü |
| Stok işlemi | `/stok/islem/<stok_kodu>/` | Hareket kaydı (giriş zorunlu) |
| Hareket Geçmişi | `/stok/hareketler/` | `stok_hareketleri` dökümü, filtreli (salt-okunur) |
| Ürün ekle | `/urun/ekle/` | Yeni ürün (giriş zorunlu, yönetici şart değil) |
| Ürün düzenle | `/urun/<stok_kodu>/duzenle/` | Var olan ürünü düzenleme (aynı form) |
| Yönetim | `/yonetim/` | Yönetici kartları. `is_staff` şart |
| Kullanıcılar | `/yonetim/kullanicilar/` | Hesap listesi, ekleme, parola, pasife alma |
| Lokasyonlar | `/yonetim/lokasyonlar/` | Hiyerarşik liste, ekleme, pasife alma, hiç kullanılmamışsa silme |

### Yönetim paneli ve yetki

Kod `katalog/yonetim.py` + `katalog/forms.py`'de, `views.py`'de **değil**: buradaki
her şey SQLite `default`'taki Django auth tablolarıyla çalışıyor, `views.py` ise
baştan sona `metaks` Postgres'ini okuyor. İki veri kaynağı, iki sorumluluk.

Kapı `yonetici_gerekli` dekoratörü (`is_staff`). `login_required`'dan farkı, giriş
yapmış ama yetkisiz kullanıcıyı giriş ekranına **geri göndermemesi** — zaten giriş
yapmış birine boş bir giriş formu göstermek "parolamı mı yanlış girdim?" izlenimi
verir. Doğru cevap 403 ve kendi şablonu var (`templates/403.html`; Django bu şablonu
bulduğunda DEBUG açıkken bile teknik sayfa yerine onu basıyor).

`is_staff` bilinçli olarak yeni bir rol tablosuna tercih edildi: Django'da hazır,
şema değişikliği istemiyor. Gerçek rol ayrımı (fason kullanıcı, salt-okunur personel)
buradan büyütülecek — `YAPILACAKLAR.md` madde 2b.

Formlar Django'nun `UserCreationForm` / `AdminPasswordChangeForm`'undan türüyor;
parola gücü doğrulaması, karma ve Türkçe hata metinleri oradan geliyor. Elle yazmak
Django'nun kurallarının ikinci kopyası olurdu — `stok_servisi.py`'nin
`stok_hareketi_kaydet()` karşısındaki duruşunun aynısı.

Üç kural bu projeye özel:

- **Kullanıcı adı düzenlenemez, hesap silinemez** (yalnızca pasife alma).
  `stok_hareketleri.yapan_kullanici` `email or username` saklıyor ve defter
  append-only; adı değiştirmek ya da hesabı silmek geçmiş kayıtları sahipsiz bırakır.
- **E-posta zorunlu ve tekil.** Veritabanında `auth_user.email` üzerinde tekillik
  kısıtı yok; kural formda çünkü e-posta bu sistemde kimliğin kendisi — iki hesap
  aynı e-postayı taşırsa "bunu kim yaptı" sorusu kalıcı olarak belirsizleşir.
- **Yönetici kendi yetkisini kaldıramaz, kendi hesabını kapatamaz.** Aksi hâlde tek
  çıkış yolu komut satırından `createsuperuser` olurdu. Ayrıca bir "sistemde son
  aktif yönetici kalmasın" kontrolü bilerek **yok**: bu formda ulaşılamaz (düzenleme
  ekranına girmek için aktif yönetici olmak şart, dolayısıyla başkası düzenlenirken
  her zaman en az bir aktif yönetici vardır), ölü kod olurdu.

Kullanıcı listesindeki "N hareket" sayısı iki veritabanı arasında JOIN gerektirdiği
için tek bir GROUP BY sorgusuyla toplanıp Python'da eşleştiriliyor (kullanıcı başına
sorgu değil). Hesabı kapatmadan önce "bu kimdi, bir şey yapmış mı" sorusunun cevabı.

### Lokasyon yönetimi ve iki cross-DB tuzağı

Kod `katalog/lokasyon_yonetimi.py` + `katalog/forms.py::LokasyonEklemeFormu`.
Kullanıcı yönetiminden farklı: bu, **`metaks` Postgres'e yazan** tek yönetim
ekranı. Ekleme formu `(lokasyon_adi, tip)`'in ötesine geçmek zorunda: migration
004'ün dolap/raf hiyerarşisi ancak `ust_lokasyon` + `kod` ile açılıyor, yalnızca
ad+tip yazan bir yol ne raf ne numune lokasyonu yaratabiliyor. Yeni bir veritabanı
fonksiyonu yok — migration 004
lokasyon kurallarının tamamını bildirimsel yazmıştı (`tip` CHECK'i, `kok_mu`/
`ust_kok_mu` üretilmiş kolonlarla bileşik FK, iki tekillik kısıtı); kapı zaten
kısıtların kendisi, Django doğrudan INSERT/UPDATE yapıyor.

Liste `LokasyonDetay` (`v_lokasyonlar_detay`'ın haritalaması) üzerinden okunuyor,
ham `Lokasyon` (`lokasyonlar`) üzerinden değil — `kod`, `tam_ad`, `yaprak_mi`
oradan geliyor. `views.py`'deki üç yer de (ana ekran KPI, hareket geçmişi
filtresi, stok işlem formu) aynı sebeple `LokasyonDetay` + `yaprak_mi` kullanıyor;
`Lokasyon` artık yalnızca **yazma** için var (ekleme formunun `ModelForm` tabanı).

Proje henüz `DATABASE_ROUTERS` eklemediği için (tek app, tek bağlantı; CLAUDE.md'nin
başındaki mimari not) `Lokasyon.objects` gibi `using('metaks')` içermeyen her sorgu
sessizce SQLite `default`'a gider. Bu, `ModelForm` kullanırken iki farklı yerde ölçülerek
bulunan gerçek tuzaklara yol açtı:

1. **FK alanının otomatik açılır listesi.** Django bir `ForeignKey` için form alanı
   üretirken (`ust_lokasyon`) queryset'i `Model._default_manager` üzerinden kurar —
   `using('metaks')` olmadan. Elle üzerine yazılmazsa form **render'a hiç gerek
   kalmadan, sadece oluşturulurken bile** `OperationalError: no such table:
   lokasyonlar` ile çöküyor (boş bir `ModelForm()` çağrısıyla doğrulandı). Çözüm:
   `LokasyonEklemeFormu.__init__`'te `self.fields['ust_lokasyon'].queryset`'i elle
   `Lokasyon.objects.using('metaks')...` ile değiştirmek — opsiyonel bir iyileştirme
   değil, formun çalışması için zorunlu.
2. **`unique=True`'nun otomatik doğrulaması.** `Lokasyon.kod`'a `unique=True`
   konulsaydı, Django'nun `validate_unique()`'i yine `_default_manager` üzerinden
   (yanlış bağlantıya) bir sorgu atardı. Bu yüzden model alanına bilerek
   `unique=True` konulmadı; `uq_lokasyonlar_kod` ve `uq_lokasyonlar_ust_ad_tip`
   kısıtlarının ihlali formda önceden sorgulanmıyor, gerçek `INSERT`'in
   `IntegrityError`'ı (`psycopg2` `diag.constraint_name` üzerinden) yakalanıp
   Türkçe mesaja çevriliyor (`lokasyon_yonetimi.py::_kisit_mesaji`).

Aynı sebeple `kok_mu`/`ust_kok_mu` (GENERATED ALWAYS kolonlar) `Lokasyon` modeline
hiç eklenmedi — Django INSERT'te modeldeki her alana değer yazmaya çalışır, üretilmiş
bir kolona yazmak Postgres'te hata verir.

Doğrulama: gerçek tarayıcıda 31/31 kontrol (kök/raf oluşturma, mükerrer ad+tip ve
mükerrer kod reddi, raf eklenince dolabın kendisinin stok formundan kaybolması,
pasife alınca stok formundan kaybolup hareket geçmişinde kalması, derinlik
koruması, yetki kapısı, mobil).

#### Silme: pasife almanın yerine değil, yanına (2026-07-31)

Pasife alma "artık buraya iş yapılmıyor" demek ve geçmişi korur; çözemediği tek
durum, **gerçekte hiç var olmamış** bir satırın listede kalıcı olarak durması —
pasife alınsa bile görünmeye devam eder. `lokasyon_sil` bunun için var.

"Sil" butonu yalnızca veritabanının gerçekten silmeye izin verdiği satırlarda
basılıyor: defterde hareketi olmayan **ve** altında rafı olmayanlar. Karar üç
`ON DELETE RESTRICT`'in kendisinde (`stok_hareketleri`'nin iki FK'sı +
`lokasyonlar_ust_lokasyon_fkey`); `_silinebilir_kimlikler` bunu yalnızca önceden
hesaplıyor, çünkü silinemeyecek bir satırda buton gösterip kullanıcıya
tıklattıktan sonra hata vermek olurdu. Defterdeki kullanım alan başına tek
DISTINCT sorgusuyla toplanıyor, lokasyon başına sorgu değil.

Buton yine de tek savunma değil: `IntegrityError` yakalanıp Türkçeye çevriliyor
(`_SILME_KISIT_MESAJLARI`) — liste basıldıktan sonra araya bir hareket girerse
oraya düşülür. Bu yol tarayıcıda gerçekten ölçüldü (butonsuz satıra elle POST →
"altında raf var" mesajı, satır yerinde kaldı). Django cascade denemiyor: ilgili
FK'ların hepsi modelde `DO_NOTHING`, yani atılan tek sorgu `DELETE` ve son sözü
veritabanı söylüyor.

### Ana ekran

Özet sayılar bilinçli olarak **grafiksiz**: hepsi tek anlık değer, yani doğru biçim
stat tile — tek çubuklu grafik değil. Sayım ilerlemesi bir orana karşı tek değer
olduğu için meter (dolgu ve boş yolak aynı rampanın iki adımı). Uydurma metrik yok;
hepsi doğrudan `v_aktif_urunler` / `v_toplam_stok` / `lokasyonlar`'dan sayılıyor.

"Sayım ilerlemesi" ölçüsü **`v_toplam_stok`'ta satırı olan ürün** sayısı — "stoğu >0
olan" değil, çünkü sayılıp boş çıkan ürün de sayılmış sayılır.

**Yerelleştirme tuzağı (yaşandı):** `LANGUAGE_CODE='tr'` olduğu için `0.4` şablonda
varsayılan olarak `0,4` basılıyor. Bu bir CSS/HTML özniteliğine girdiğinde
(`style="width: 0,4%"`) geçersiz oluyor, tarayıcı yok sayıp genişliği `auto`'ya
düşürüyor ve çubuk **%0,4 yerine tam dolu** görünüyordu. Sayı bir stile veya
`aria-*` özniteliğine yazılacaksa `{% load l10n %}` + `|unlocalize` şart; metin
olarak gösterilirken virgüllü hâli doğru olduğu için orada dokunulmuyor.

### Liste sayfaları

Katalog ve stok aynı galeri altyapısını paylaşıyor; ikisi de `ListeFiltresi` +
`_liste_context` üzerinden çalışıyor, aralarındaki tek fark stok.

Ayrılmalarının sebebi kullanım senaryosu: katalog sayfası ön büroda müşteriye ürün
göstermek için — orada ilgilenilen şey ürünün kendisi, deposu değil; stok rakamı
gereksiz gürültü (ve müşteriye gösterilmesi istenmeyen bilgi) olurdu. Depo tarafı
sorularının yeri ayrı sayfa.

### View'ın üç yanıt biçimi

Her iki liste view'ı da aynı URL'den üç farklı yanıt üretiyor (`_liste_yanit`):

| İstek | Yanıt | Neden |
| --- | --- | --- |
| Normal | tam sayfa (`liste.html`) | ilk yükleme, yenileme, paylaşılan link |
| HTMX, `sayfa == 1` | `_govde_yanit.html` | filtre değişikliği |
| HTMX, `sayfa > 1` | `_urun_kartlari.html` (sadece kartlar) | sonsuz kaydırma, ızgaranın sonuna eklenir |

### Filtre durumunun taşınması (JS'siz)

Sticky başlıktaki üç kontrol, HTMX'in takas ettiği `#katalog-govde` bloğunun **dışında**
duruyor — her biri ayrı bir sebeple:

- **Arama kutusu** — DOM'dan sökülmediği için kullanıcı yazarken odak ve imleç kaybolmuyor.
- **Kategori paneli** — çoklu seçimde her tıklamada kapanmaması gerekiyor.
- **Sıralama seçimi** — `sirala` değerinin tek kaynağı orası, bayatlaması mümkün değil.

Bunlar diğer filtrelerin güncel değerini `hx-include="#filtre-durumu input"` ile canlı
DOM'dan okuyor. `#filtre-durumu`, `_govde.html` içinde her takasta sunucudan yeniden
basılan hidden input'lar (seçili her kategori için bir tane + `stok`), dolayısıyla hiç
eskimiyor ve filtre durumunu JS ile taşımaya gerek kalmıyor.

Bir `<form>` + submitter yaklaşımı denenmedi çünkü arama kutusuna yazarken submitter
olmadığından `kategori` gönderilmez ve filtre her tuş vuruşunda sıfırlanırdı.

### Kategori paneli ve out-of-band takas

Kategori filtresi **çoklu seçim** (`?kategori=TOKA&kategori=RİVET`, `getlist`). Panel
sticky başlıkta, takas hedefinin dışında olduğu için içeriği `hx-swap-oob` ile
tazeleniyor (`_govde_yanit.html`): bir kategori işaretlendiğinde asıl yanıt
`#katalog-govde`'yi değiştirirken, iki out-of-band parça da `#kategori-listesi` ile
`#kategori-sayaci`'nı günceller. Panelin kendisine dokunulmadığı için **açık kalır** ve
kullanıcı üst üste kategori seçebilir — bu davranış çoklu seçimin bütün noktası.

Panel satırlarının URL'leri sunucuda üretiliyor (`ListeFiltresi.kategori_degistir`) ve
o kategorinin eklenmiş/çıkarılmış hâlini taşıyor; seçim durumu istemcide hiç tutulmuyor.
Panel içi arama ise tamamen istemci tarafında (35 kategoriyi süzmek için sunucuya gitmek
gereksiz gecikme olurdu). Sayılar aramaya göre daralıyor ama kategori seçimine göre
daralmıyor (faceted search) — kullanıcı "toka" yazınca her kategoride kaç sonuç olduğunu
görüyor.

### Stok verisinin üç durumu

`v_toplam_stok`'ta **satırı olmayan** ürün ile **0 yazan** ürün aynı şey değil; arayüz
ikisini ayrı gösteriyor (`_stok_bilgisini_ekle` → `urun.stok_durumu`):

| Durum | Anlamı | Kartta |
| --- | --- | --- |
| `var` | toplam > 0 | yeşil "N adet" |
| `sifir` | sayıldı, boş çıktı | kehribar "Stok yok" |
| `sayilmadi` | `v_toplam_stok`'ta satır yok | gri "Sayılmadı" |

Bu ayrım devam eden depo sayımında anlamlı: "daha neye bakmadık?" sorusunun cevabı
üçüncü durum. "Sadece stokta olanlar" anahtarı yalnızca `var` durumunu bırakıyor
(`toplam_miktar > 0` alt sorgusu).

**2026-07-31 itibarıyla defter tamamen boş.** Daha önce buradaki 30 kaydın tamamı
test girişiydi (29 Temmuz düşük-kod arayüz denemeleri + 30 Temmuz Django doğrulamaları);
`veritabani` migration 006 hepsini sildi ve sequence'i 1'e aldı. Yani `v_toplam_stok`
sıfır satır, her ürün "Sayılmadı" durumunda ve "sadece stokta olanlar" boş sonuç
veriyor. Sayfa sayım ilerledikçe kendiliğinden dolacak, kodda değişiklik gerekmiyor.
(Devam eden sayımın verisi hâlâ Excel'de tutuluyor, veritabanında değil.)

**Lokasyonlar da aynı gün üçe indi:** kullanıcının doğruladığı gerçek konumlar
**Metaks, Fabrika** (DAHİLİ) ve **Skor** (FASON). Geri kalan beşi (Ana Depo,
Sevkiyat Alanı, Fason Atölye 1, Depo 1, Kaplama) gerçekte yoktu ve yönetim
ekranından silindi — defter temizlendiği için `RESTRICT` artık engellemiyordu.
Yeni konumlar gerektiğinde ekleme formundan açılacak.

## Stok işlemi (ilk yazma modülü)

`/stok/islem/<stok_kodu>/` — stok sayfasındaki detay panelinden "Stok işlemi yap"
butonuyla açılıyor. GİRİŞ / ÇIKIŞ / TRANSFER / SAYIM / DÜZELTME.

### İş kuralları burada tekrarlanmıyor

`katalog/stok_servisi.py` yalnızca parametreleri geçiriyor ve dönen Türkçe mesajı
taşıyor. Yeterli stok kontrolü, işlem tipine göre lokasyon zorunlulukları,
SAYIM_DEVRI'nin fark hesabı ve mükerrer gönderim koruması **tamamen**
`stok_hareketi_kaydet()` içinde. Aynı kuralları Python'da (ya da JS'te) da
doğrulasaydık iki kopya zamanla ayrışırdı; tek otorite veritabanı.

Formdaki JS de bu yüzden sadece sunum yapıyor: seçilen işlem tipine göre hangi lokasyon
alanının görüneceğini ve etiketleri ayarlıyor, hiçbir şeyi doğrulamıyor. Kullanıcıya
gösterilen hata metinleri doğrudan fonksiyonun `RAISE EXCEPTION` mesajları
(ör. "Yetersiz stok: bu lokasyonda 0 adet var, 999999 adet çıkış isteniyor.").

### SAYIM: fark değil, toplam

Sözleşmedeki kesinleşmiş kural formda görünür kılındı: alan etiketi "Sayılan toplam
miktar", altında "Farkı değil, saydığınız TOPLAMI girin" açıklaması. Personelin
sistemdeki mevcut rakamı bilip çıkarma yapması istenmiyor (önyargı + elle hata payı);
farkı fonksiyon hesaplıyor. Sayılan miktar mevcutla aynıysa **hiç satır yazılmıyor**
ve kullanıcıya bunu söyleyen bir bilgi mesajı çıkıyor — bu bir hata değil.

### Mükerrer gönderim

Form her basıldığında yeni bir `istemci_islem_kimligi` (UUID) gömülüyor; başarılı
kayıttan sonra da yenisi üretiliyor, yoksa sonraki gönderim "zaten kaydedilmiş" diye
atlanırdı. Çift tıklama/ağ tekrarı aynı kimliği gönderirse veritabanındaki
`uq_stok_hareketleri_istemci_kimligi` ikinci satırı engelliyor.

### Giriş (auth)

Kullanıcılar Django'nun kendi auth tablolarında, yani **SQLite `default`** bağlantısında
— paylaşımlı METAKS Postgres'ine dokunulmuyor. Sadece yazma sayfası `@login_required`;
katalog ve stok listeleri girişsiz açık kalıyor (iç ağ, salt-okunur, ön büroda hızla
açılması gereken ekranlar).

**Kök URL bir yönlendirici** (`views.ana_ekran`): giriş yapılmışsa ya da session'da
`MISAFIR_ANAHTARI` varsa panel, aksi hâlde `/giris/`. Giriş ekranındaki "Giriş yapmadan
devam et" (`/misafir/`) bu bayrağı işaretliyor, dolayısıyla **kapı tarayıcı başına bir
kez** çıkıyor — katalog ön büroda müşteri karşısında açılan bir ekran, her seferinde
araya bir sayfa koymak gereksiz sürtünme olurdu. Bayrağı ayrıca temizlemeye gerek yok:
Django'nun `logout()`'u session'ı flush ediyor, yani "Çıkış" güvenilir biçimde giriş
ekranına döndürüyor.

Giriş formu **tek yerde** (`giris.html`); kök URL onu kopyalamak yerine yönlendiriyor.
Girişin kalıcı görünür yolu ise üst çubuktaki "Giriş yap" bağlantısı (giriş yapmamış
kullanıcıya, tüm sayfalarda) — giriş kutusu eskiden ana ekranın en altında, modül
kartlarının da altında kalıyordu ve sayfayı kaydırmadan görünmüyordu.

Yazma tarafında giriş bir tercih değil **zorunluluk**: `stok_hareketleri.yapan_kullanici`
NOT NULL ve Postgres'e tek bir paylaşılan `depo_admin` kullanıcısıyla bağlanıldığı için
`current_user`'a güvenilemez — değer uygulamadan açıkça geçiriliyor
(`request.user.email or username`).

### Pasif lokasyonlar

`v_lokasyon_stok_ozet`, artık kullanılmayan lokasyonlardaki geçmiş hareketleri de
gösteriyor. Form ve detay panelindeki stok dökümünde bu satırlar gizlenmiyor (geçmişi
saklamak olurdu) ama **"pasif" etiketiyle** işaretleniyor — yoksa kullanıcı listede
gördüğü lokasyonu aşağıdaki seçim kutusunda bulamayınca kafası karışıyordu.

### Bu modül nasıl doğrulandı

Paylaşımlı `depo_sistemi`'ne **hiçbir kalıcı satır yazılmadan**:

- `stok_servisi` entegrasyonu `BEGIN`/`ROLLBACK` içinde (veritabani'nin kendi
  "önce-test-sonra-uygula" disiplininin aynısı): GİRİŞ, TRANSFER, mükerrer gönderim,
  yetersiz stok, eksik lokasyon, kullanıcısız işlem, SAYIM'ın fark hesabı.
  Hata bekleyen senaryolar iç `atomic()` (SAVEPOINT) içinde — `RAISE EXCEPTION` dış
  transaction'ı bozuyor.
- Üretim yolunun (autocommit, `atomic` yok) iş kuralı hatasından sonra bağlantıyı
  bozmadığı ayrıca ölçüldü.
- Uçtan uca tarayıcı testi, satır yazmayan iki senaryo üzerinden: SAYIM'ın farkı sıfır
  olduğu durum (`atlandi`) ve yetersiz stok (istisna). İkisi de tanım gereği
  `stok_hareketleri`'ne dokunmuyor, testin sonunda satır sayısı doğrulanıyor.

**Gerçek yazma denemesi (2026-07-30, kullanıcı izniyle** — devam eden sayımın verisi
veritabanında değil, Excel'de tutuluyor**):** `1001013` üzerinde uçtan uca doğrulandı.
GİRİŞ 500 → Metaks, TRANSFER 200 → Depo 1, SAYIM 250. Sayım kaydı ledger'a
**50'lik azaltma** olarak düştü, yani fonksiyon farkı gerçekten kendisi hesapladı;
sonuç Metaks 250 / Depo 1 200. Mükerrer gönderim de canlı doğrulandı: aynı
`istemci_islem_kimligi` ile iki POST → veritabanında tek satır.

Bu denemelerin bıraktığı satırlar 2026-07-31'de `veritabani` migration 006 ile
temizlendi (defter uygulama üzerinden append-only; silmenin yolu numaralı migration).
Defter bugün boş.

## Ürün ekleme/düzenleme (2026-07-31)

`/urun/ekle/` ve `/urun/<stok_kodu>/duzenle/` aynı formu (`katalog/forms.py::
UrunFormu`) paylaşıyor. Kod `katalog/urun_servisi.py` (yazma katmanı — `urun_kaydet()`
sarmalayıcı + görsel dosya yaz/sil, `stok_servisi.py` ile aynı desen) ve
`katalog/urun_yonetimi.py`'de (view'lar). Erişim `@login_required` — **yönetici şart
değil**, stok işlemiyle aynı kapı; kullanıcı/lokasyon yönetiminden (`is_staff`) burada
bilinçli olarak ayrışıyor.

### GUNCELLE modu KISMİ değil — tasarımın en riskli noktası

`urun_kaydet()` (veritabani migration 005) her çağrıda `urunler`'in **tüm alanlarını**
yeniden yazıyor; boş bırakılan alan NULL'a döner (tek istisna görsel — verilmezse
mevcut ana görsel ve AKTİF/PASİF durumu dokunulmadan kalır). Bu, "kısmi güncelleme"
alışkanlığıyla yazılırsa **veri kaybına** yol açar. Çözüm: düzenleme view'ı formu HER
ZAMAN ürünün güncel tüm alanlarıyla `initial=` dolduruyor; form normal bir HTML formu
olduğu için değiştirilmeyen alanlar zaten mevcut değerleriyle geri gönderiliyor —
ayrıca bir "değişmeyenleri koru" mantığı yok, doğruluk tamamen doğru ön doldurmaya
dayanıyor. **Gerçek bir üründe (1001013) doğrulandı**: GET ile form yüklenip hiç
değiştirilmeden POST edildi, veritabanı satırı önce/sonra **birebir aynı** kaldı.

Bu yüzden düzenleme formu `AktifUrun` (`v_aktif_urunler`) üzerinden değil yeni
`models.Urun` (ham `urunler`, salt-okunur, yalnızca ön doldurma için) üzerinden
yükleniyor: `v_aktif_urunler` yalnızca `katalog_durumu='AKTIF'` satırları gösteriyor,
ama düzenlemenin asıl anlamlı olduğu durumlardan biri PASİF bir **taslağı**
tamamlamak (eksik görseli ekleyip AKTİF'e geçirmek) — o satır view'da hiç yok.

### İki cross-DB tuzağı — lokasyon formundakiyle aynı aile

`UrunFormu` bilerek `ModelForm` DEĞİL, düz `forms.Form`: yazmanın tek kapısı bir
fonksiyon çağrısı (`urun_kaydet()`), `Model.save()` değil, ve kategori oluşturma ayrı
bir adım. Bu, `LokasyonEklemeFormu`'nda (madde 2c) ölçülüp bulunan riski —
`ModelForm`'un FK alanları için `using('metaks')` olmadan otomatik kurduğu queryset'in
SQLite `default`'a gidip çökmesi — baştan gereksiz kılıyor. Kategori/hammadde/kaplama
`ModelChoiceField`'larının queryset'leri yine de `__init__`'te elle `using('metaks')`
ile atanıyor (aksi hâlde form OLUŞTURULURKEN bile "no such table" ile çöktüğü ölçüldü).

**Kategori oluşturma büyük/küçük harf duyarsız.** `kategoriler.kategori_adi` UNIQUE
kısıtı Postgres'te harf duyarlı ("Toka" ≠ "TOKA"); `unique=True` model alanına
konulmadı (aynı cross-DB riski) ve tekillik `urun_servisi.kategori_id_cozumle()`'de
elle, duyarsız aranıyor — var olanla sadece harf durumunda ayrışan bir isim yeni
kategori açmıyor, var olanı kullanıyor.

### Bulunan gerçek hata: JS'in gizlediği alan temizlenmiyordu

`urun_tipi` VARYANT/ALT_PARCA seçilince üst ürün + varyant adı alanlarını gösterip
ANA_URUN'a dönülünce **gizleyen** JS, değeri hiç temizlemiyordu — tarayıcı gizli
kalan eski değeri yine de POST eder. `urun_kaydet()` bunu reddetmiyor bile (kısıt
yalnızca VARYANT/ALT_PARCA'da üst ürünü zorunlu kılıyor, ANA_URUN'da yasaklamıyor),
yani tutarsız bir satır ("ana ürün" ama yine de bir üst ürüne bağlı) sessizce
kaydedilebilirdi. `UrunFormu.clean()`'de `urun_tipi == 'ANA_URUN'` olunca bu iki
alan bilerek temizleniyor.

### Görsel dosyası

Sıra **önce dosya, sonra DB**: `urun_kaydet()` reddederse az önce yazılan dosya
(`urun_servisi.gorsel_sil`) geri alınır. Ters sırada çökme olsaydı var olmayan bir
dosyayı gösteren kırık ürün kalırdı. Dosya adı (`<stok_kodu>_<sıra>.<uzantı>`)
diske yazılmadan ÖNCE `urun_sonraki_gorsel_sirasi()`'yle hesaplanıyor — sıralamanın
gereği. Kabul edilen uzantılar jpg/jpeg/png (kaynak korpusun tamamı bu üçü); doğrulama
`forms.ImageField` üzerinden (Pillow gerektiriyor, `requirements.txt`'e eklendi) —
gerçek bir resim olmayan dosya kabul edilmiyor.

Yazma yolu `settings.URUN_GORSEL_DIZINI` (varsayılan: sibling-repo düzeni,
`veritabani/images/final/products`) — `GORSEL_SUNUCU_BASE_URL`'in **yazma tarafı**
karşılığı; nginx aynı dizini `:ro` sunuyor, yazan taraf host (bu Django süreci).
Görseli değiştirmek eskisini silmiyor: `urun_kaydet()` eski ana görseli
`ana_gorsel_mi=FALSE` yaparak ikincil bir görsele düşürüyor, dosya diskte kalıyor —
uygulama hiçbir zaman var olan bir görsel dosyasını silmiyor, yalnızca kendi bu
istekte yazdığı (ve DB'nin reddettiği) dosyayı geri alıyor.

### Kasıtlı kapsam dışı

Hammadde/kaplama için "yeni ekle" yok (kategori'nin aksine) — bugünkü 1.780 ürünün
hiçbirinde ikisi de dolu değil, talep de yok. Üst ürün seçimi düz metin kutusu,
arama/otomatik tamamlama yok — `urun_kaydet()` zaten "üst ürün bulunamadı" diye
kendi Türkçe hatasını veriyor, ikinci bir ön-doğrulama katmanı gerekmedi.

## Hareket geçmişi ve zaman dilimi tuzağı

`/stok/hareketler/` — `stok_hareketleri` dökümü; ürün/açıklama araması, işlem tipi,
lokasyon (kaynak **veya** hedef), kullanıcı ve tarih aralığı filtreleri. Salt-okunur;
yazmanın tek yolu hâlâ `stok_hareketi_kaydet()`. `StokHareketi` modeli bu yüzden
bilinçli olarak yalnızca okuma için var.

Filtrelerin hepsi gerçek form alanı olduğu için burada tek bir `<form>` yeterli:
HTMX form üzerinden istek attığında içindeki tüm alanları kendiliğinden gönderiyor,
katalogdaki `hx-include` düzenine gerek kalmıyor (orada kategori şeritleri buton
olduğu için form yaklaşımı çalışmıyordu).

### Zaman dilimi: kolon naive UTC tutuyor (dikkat)

`stok_hareketleri.islem_tarihi` / `created_at` **`timestamp without time zone`** ve
Postgres oturumu UTC olduğu için `CURRENT_TIMESTAMP` buraya **UTC duvar saatini naive
olarak** yazıyor. Yani 17:41'de yapılan işlem tabloda `14:41` görünüyor. Django
`USE_TZ=True` ile çalıştığından bu değer olduğu gibi basılırsa kullanıcıya **3 saat
geri** gösterilir — ana ekranda tam olarak bu olmuştu.

Çözüm `models.py::yerel_tarih()`: Postgres'in `timezone('UTC', ts)` fonksiyonuyla
değeri UTC kabul edip `timestamptz`'ye çeviriyor, Django da şablonda `TIME_ZONE`
(Europe/Istanbul) değerine göre yerelleştiriyor. Bu ifade **hem gösterimde hem tarih
aralığı filtresinde** kullanılmalı; ham kolona göre filtrelemek gün sınırlarında
3 saatlik kaymaya yol açar. Üretilen SQL doğru:
`django_datetime_cast_date(timezone(UTC, islem_tarihi), Europe/Istanbul, UTC)`.

Sonsuz kaydırma nöbetçisi burada bir `<tr>`; `<tbody>` içine `<div>` koymak geçersiz
HTML olduğu için tarayıcı onu tablonun dışına taşır ve `revealed` hiç tetiklenmez.
Bu yol sayfa boyutu geçici olarak 10'a düşürülüp gerçek tarayıcıda doğrulandı
(nöbetçinin `<tbody>` içinde kaldığı ve eklenen satırların 7 hücreli geçerli `<tr>`
olduğu dahil).

### Verinin arayüzü şekillendirdiği yerler

Bunlar `v_aktif_urunler`'ın 1.780 satırı üzerinde ölçüldü (2026-07-30). Veri girildikçe
davranış kendiliğinden değişir, kodda düzeltme gerekmez:

- **Detay paneli sadece dolu alanları listeliyor** (`_detay_alanlari`). Sabit bir alan
  tablosu panelin çoğunu "—" ile dolduruyordu: `boya_mine`, `montaj_durumu`,
  `hammadde_adi`, `kaplama_adi` **hiçbir** satırda dolu değil, `aciklama` 1.780'in
  30'unda dolu ve bunların 26'sı yer tutucu ("yok", "E"). `kritik_stok_esigi` listede
  bilinçli olarak yok: ürünü tanımlayan bir özellik değil ve her satırda 0.
- **"En son eklenen modeller" görünümü yok, sıralama stok koduna göre.** Ürün başına
  gerçek bir ekleme zamanı **yok**: `urunler.created_at` tüm satırlarda toplu yüklemenin
  tek timestamp'i (`2026-07-28 21:31:10`) ve `v_aktif_urunler`'da hiç görünmüyor. Sipariş
  verisi de henüz yok. Azalan stok kodu, yöneticinin "yeni modelleri gözden geçirme"
  ihtiyacının bugünkü tek yaklaşımı — gerçek çözüm için `veritabani` tarafında satır
  bazlı bir tarih (ve/veya sipariş verisi) gerekiyor.
- **Ana ürün bağlantısı koşullu.** `parent_stok_kodu` katalogda olmayan bir ürünü
  gösterebiliyor: ana ürün geçerli ana görseli yoksa PASİF kalıyor. 2026-07-30 verisinde
  parent'ı olan 4 satırın ana ürünlerinin **ikisi de** (`2108`, `1805012`) PASİF, yani
  koşulsuz basılan buton 404 alıp sessizce hiçbir şey yapıyordu. Panel artık ürün
  gerçekten `v_aktif_urunler`'daysa buton, değilse düz metin + açıklama basıyor.
- **Kategorisi olmayan 31 ürün** için `kategori` parametresinde `__kategorisiz__`
  sentinel'i var (boş string "tüm kategoriler" anlamına geldiği için ayrı bir değer
  gerekti).

Sayfa boyutu 48 (`SAYFA_BOYUTU`) — ızgaranın 2/3/4/6 kolonlu tüm breakpoint'lerine tam
bölünüyor, son satır yarım kalmıyor.

## Durum (2026-07-31)

Bugün ayakta olan sayfaların listesi yukarıdaki "Sayfa yapısı" tablosunda; sıradaki
işler ve gerekçeleri **`YAPILACAKLAR.md`**'de (açık maddeler: rol/yetki ayrımı, hızlı
stok işlemi girişi, numune takibi, CSV dışa aktarma). Şema/pipeline tarafının yol
haritası ise `veritabani/docs/INFO.md`'nin "Güncel Çalışma Noktası" bölümünde.

Aşağısı ilk iki liste sayfasının (2026-07-30) ölçüm kaydı — performans ve sorgu
sayıları o günden beri değişmedi.

İki liste sayfası (katalog + stok) tamamlandı ve gerçek tarayıcıda (kurulu Chrome,
puppeteer-core ile sürülerek) uçtan uca doğrulandı: arama, çoklu kategori seçimi,
panelin seçim sırasında açık kalması, out-of-band tazeleme, sıralama, sonsuz kaydırma,
stok anahtarı, iki ayrı detay paneli, boş durum, mobil görünüm, ürün görsellerinin
`gorsel-sunucu`'dan HTTP 200 dönmesi. Django ↔ `metaks` Postgres bağlantısı gerçek
veriyi okuyor (1.780 aktif ürün). Tüm yanıtlar 75 ms altında; katalog sayfası yükü
başına 3 sorgu (COUNT + LIMIT/OFFSET + kategori dağılımı GROUP BY), stok sayfası 4
(sayfadaki 48 ürünün stoğu tek ek sorguda, N+1 yok).

**Veri tazeliği:** hiçbir önbellek yok, her istek Postgres'e taze gidiyor. Ama sayfa
kendiliğinden de yenilenmiyor — açık duran sekme, kullanıcı yenileyene/arama yapana
kadar eski veriyi gösterir. Otomatik tazeleme gerekirse HTMX'te tek satır
(`hx-trigger="every 30s"`); katalogda gereksiz, canlı stok ekranında mantıklı olur.

Henüz yapılmadı — sıradaki işlerin listesi ve gerekçeleri **`YAPILACAKLAR.md`**'de
(CSV dışa aktarma, numune takibi; giriş akışı/yönetim paneli/ürün ekleme artık ✅
tamamlandı). Burada sadece o listeyi okurken bilinmesi gereken kalıcı kısıtlar:

- **Otomatik test yok** (`katalog/tests.py` boş). Doğrulama tek kullanımlık tarayıcı
  script'leriyle yapıldı. Kalıcı test yazmak düşünmeyi gerektiriyor: Django test
  runner'ı `metaks` bağlantısı için test veritabanı oluşturmaya çalışır — paylaşımlı
  `depo_sistemi`'ne karşı istenmeyen bir davranış. Muhtemel yol:
  `SimpleTestCase`/`databases = {'default'}` + `v_aktif_urunler`'ı taklit eden bir
  fixture katmanı, ya da salt-okunur bir test şeması.
- **Ürün ekleme/düzenleme ✅ tamamlandı (2026-07-31)** — bkz. yukarıdaki "Ürün
  ekleme/düzenleme" bölümü. Tek yazma kapısı `urun_kaydet()` (`stok_hareketi_kaydet()`
  ile aynı desen); Django artık ona bir çağrı katmanı (`urun_servisi.py`) yazdı.
- **Test hareketleri temizlendi ✅ (2026-07-31)**: kararlaştırılan yol izlendi —
  `veritabani/sql/migrations/006_test_hareketlerini_temizle.sql` (şema/veri otoritesi
  orası) defterdeki 30 test kaydının tamamını sildi. Tetikleyen ihtiyaç lokasyon
  silme oldu: `ON DELETE RESTRICT` yüzünden o kayıtlar gerçekte var olmayan dört
  lokasyonu yerinde tutuyordu. Rollback dosyası 30 satırı `hareket_id` ve
  `istemci_islem_kimligi`'leriyle geri yazıyor ve uygulanmadan önce gerçekten
  ölçüldü (uygula → geri al → satır checksum'ı birebir aynı). Migration'ın başındaki
  sayım kontrolü, araya gerçek bir kayıt girmişse durmasını sağlıyor.
- **Çoklu görsel galerisi yok**: `v_aktif_urunler` sadece `ana_gorsel_dosya_adi`
  veriyor; 1.780 ürünün 19'unda ikinci bir aktif görsel var (`urun_gorselleri`).
  Kazanç 19 üründe olduğu için ikinci bir unmanaged model eklenmedi.
- **Stok işlemlerinde rol ayrımı yok** (`is_staff` yalnızca yönetim panelini kapatıyor
  — bkz. "Yönetim paneli ve yetki"): giriş yapan herkes, yönetici olsun olmasın, her
  ürüne her işlem tipini uygulayabiliyor. İç ağda tek ekip için bugün yeterli;
  fason/dış kullanıcı girdiği anda gözden geçirilmeli (madde 2b).
- hosting (local'de geliştiriliyor, bulut VPS'e taşıma kullanıcı kararına bağlı),
  production ayarları (DEBUG, SECRET_KEY, ALLOWED_HOSTS şu an sadece local dev için).
  **Giriş eklendiği için bunlar artık daha kritik**: parolalar HTTP üzerinden gidiyor,
  dışarı açılmadan önce HTTPS ve gerçek bir `SECRET_KEY` şart.
