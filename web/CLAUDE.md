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
(`metaks_DB/images/final/products`, 1.799 dosya): dosyaların **%79'u yatay**
(medyan ~3:2) ve **%55'i 200px'den dar**. Kare kutu yatay fotoğrafların altında/üstünde
büyük boşluk bırakıyordu; panelde tüm sütunu doldurmak ise yarıdan fazla görseli
3-4 katına büyütüp bulanıklaştırıyordu. Görseller `object-contain` ile gösteriliyor,
`object-cover` değil — kırpma bu küçük metal aksesuarların ayırt edici kenarını kesiyor,
oysa ekranın tek işi ürünü görselden tanıtmak.

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

`metaks_DB` ve `depo-appsmith-arayuz` ile aynı desen: repo-scoped `user.name`/`user.email`
(global değil), commit signing global 1Password SSH agent config'inden miras alınıyor.

Remote **2026-07-30'da eklendi**: `Omer-Bera/depo-web-arayuz`, **private** (kardeş iki
repo da private; bu iç iş yazılımı, şema ayrıntıları ve iş mantığı içeriyor).

Şu an tek branch (`master`) var. Kardeş repolarda `master`/`dev`/`review` üç-branch
modeli kullanılıyor; buraya da uygulamak tutarlılık için mantıklı olur ama **henüz
karar verilmedi**, o yüzden bilerek oluşturulmadı.

`.gitignore` kapsamı: `.env`, `db.sqlite3` (uygulama kullanıcıları burada), `venv/`.
Yani hiçbir kimlik bilgisi ve parola hash'i repoya girmiyor.

## Sayfa yapısı

| Sayfa | URL | Ne yapar |
| --- | --- | --- |
| Giriş | `/giris/` | Giriş formu + "Giriş yapmadan devam et". Girişsiz `/`'in indiği yer |
| Panel | `/` | Modüllere yönlendirme, özet sayılar, son hareketler |
| Ürün Kataloğu | `/katalog/` | Görsel galeri. **Stoktan hiç söz etmez.** |
| Stok Durumu | `/stok/` | Aynı galeri + kart başına stok durumu + "sadece stokta olanlar" anahtarı + detayda lokasyon dökümü |
| Stok işlemi | `/stok/islem/<stok_kodu>/` | Hareket kaydı (giriş zorunlu) |
| Hareket Geçmişi | `/stok/hareketler/` | `stok_hareketleri` dökümü, filtreli (salt-okunur) |

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

**2026-07-30 itibarıyla gerçek stok verisi yok:** `stok_hareketleri`'ndeki 21 kaydın
tamamı 29 Temmuz'daki test girişleri (her GİRİŞ'in peşinde bir ÇIKIŞ, yuvarlak rakamlar),
hepsi net 0'a iniyor — yani stoğu >0 olan tek ürün bile yok ve "sadece stokta olanlar"
bugün boş sonuç veriyor. Ayrıca 30 Temmuz 09:06'da lokasyonlar değişmiş: eski üçü
(Ana Depo, Sevkiyat Alanı, Fason Atölye 1) pasife alınmış, gerçekleri açılmış —
**Metaks, Depo 1, Fabrika** (DAHİLİ), **Kaplama, Skor** (FASON). Test hareketlerinin
hepsi artık pasif olan eski lokasyonlara bağlı. Sayfa sayım ilerledikçe kendiliğinden
dolacak, kodda değişiklik gerekmiyor.

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

- `stok_servisi` entegrasyonu `BEGIN`/`ROLLBACK` içinde (metaks_DB'nin kendi
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

Bu denemelerin bıraktığı satırlar `stok_hareketleri`'nde duruyor (ledger append-only,
silinmiyor); açıklama alanlarından ayırt edilebilirler.

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
  ihtiyacının bugünkü tek yaklaşımı — gerçek çözüm için `metaks_DB` tarafında satır
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

## Durum (2026-07-30)

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
(giriş akışı, CSV dışa aktarma, yönetim paneli, ürün ekleme, numune takibi). Burada
sadece o listeyi okurken bilinmesi gereken kalıcı kısıtlar:

- **Otomatik test yok** (`katalog/tests.py` boş). Doğrulama tek kullanımlık tarayıcı
  script'leriyle yapıldı. Kalıcı test yazmak düşünmeyi gerektiriyor: Django test
  runner'ı `metaks` bağlantısı için test veritabanı oluşturmaya çalışır — paylaşımlı
  `depo_sistemi`'ne karşı istenmeyen bir davranış. Muhtemel yol:
  `SimpleTestCase`/`databases = {'default'}` + `v_aktif_urunler`'ı taklit eden bir
  fixture katmanı, ya da salt-okunur bir test şeması.
- **Ürün ekleme, stok işleminden belirgin şekilde daha zor.** `urunler`'e elle INSERT
  edilmez; tek kapı `metaks_DB` migration 005'in eklediği **`urun_kaydet()`**
  (`stok_hareketi_kaydet()` ile aynı desen). Sebep: `katalog_durumu` AKTİF'e kendi
  kendine geçmiyor (bu kolonu yöneten trigger yok, AKTİF ataması migration 001'deki
  tek seferlik backfill'di) ve `chk_urunler_katalog_durumu_aktif_mi_tutarli`,
  `katalog_durumu` ile `aktif_mi`'nin birlikte hareket etmesini şart koşuyor.
  Ekleme bu yüzden bölünemez: görsel dosyası → `urun_gorselleri` (`ana_gorsel_mi`)
  → `urunler` AKTİF, hepsi tek transaction'da.
  **Düzeltme (2026-07-30):** daha önce burada "yeni satır PASİF doğar ve öyle kalır"
  yazıyordu — yanlıştı. Varsayılanlara güvenen bir INSERT *görünmez ürün* bırakmıyor,
  doğrudan **patlıyordu**: `aktif_mi` varsayılanı TRUE, `katalog_durumu` varsayılanı
  PASİF, ikisi de yukarıdaki CHECK ile çelişiyordu. Migration 005 `aktif_mi`
  varsayılanını FALSE yaparak bu çelişkiyi giderdi.
  Görsel dizininin sahibi `metaks_DB` (nginx `gorsel-sunucu`, `:ro` bağlı — yazan
  taraf host); bu repo bugün hiç dosya yazmıyor. Sıralama **önce dosya, sonra DB**:
  fonksiyon hata verirse dosya silinir; ters sırada var olmayan görseli gösteren
  kırık ürün kalırdı.
- **Test hareketleri ledger'da duruyor**: 2026-07-30'daki doğrulama kayıtları
  (`1001013` ve `1001020` üzerinde, açıklamalarından ayırt edilebilir) silinmedi —
  defter append-only. Kullanıcıyla kararlaştırılan yol: **ürün tamamlandığında
  `metaks_DB` tarafında numaralı bir migration ile temizlenecek** (şema otoritesi
  orası). O zamana kadar hareket geçmişinde görünmeye devam edecekler.
- **Çoklu görsel galerisi yok**: `v_aktif_urunler` sadece `ana_gorsel_dosya_adi`
  veriyor; 1.780 ürünün 19'unda ikinci bir aktif görsel var (`urun_gorselleri`).
  Kazanç 19 üründe olduğu için ikinci bir unmanaged model eklenmedi.
- **Yetkilendirme yok** (giriş var ama rol/izin ayrımı yok): giriş yapan herkes her
  ürüne her işlem tipini uygulayabiliyor. İç ağda tek ekip için bugün yeterli;
  fason/dış kullanıcı girdiği anda gözden geçirilmeli.
- hosting (local'de geliştiriliyor, bulut VPS'e taşıma kullanıcı kararına bağlı),
  production ayarları (DEBUG, SECRET_KEY, ALLOWED_HOSTS şu an sadece local dev için).
  **Giriş eklendiği için bunlar artık daha kritik**: parolalar HTTP üzerinden gidiyor,
  dışarı açılmadan önce HTTPS ve gerçek bir `SECRET_KEY` şart.
