# Yapılacaklar

Sırayla önceliklendirilmiş iş listesi. Mimari kararlar ve mevcut durum `CLAUDE.md`'de;
burası "sırada ne var" sorusunun cevabı.

Sıra kullanıcıyla kararlaştırıldı (2026-07-30):
**giriş akışı → yönetim paneli/kullanıcılar → ürün ekleme → numune takibi → CSV.**
Araya 3b (hızlı stok işlemi girişi) girdi ve 2026-07-31'de tamamlandı.

**Bugün açık kalan maddeler: 2b (rol/yetki ayrımı), 4 (numune takibi), 5 (CSV dışa
aktarma).** 1, 2a, 2c, 3 ve 3b ✅ tamamlandı. 4'ün `veritabani` tarafı da hazır
(migration 004 uygulandı, Django'nun lokasyon açılır listeleri `yaprak_mi`'ye
taşındı) — kalan iş gerçek dolap/raf satırlarının girilmesi ve arayüz rozetleri.

---

## 0. Eski düşük-kod arayüz ✅ KAPANDI (2026-07-31)

Bu arayüz bir düşük-kod arayüzün (Appsmith) yanında strangler-fig yaklaşımıyla
büyümüştü. 2026-07-31'de o arayüz **projeden tamamen çıkarıldı** — konteyner
durduruldu, compose'dan silindi, docker volume'ü kaldırıldı, GitHub reposu
arşivlendi. Yedeği `~/arsiv-appsmith/` altında duruyor (volume tarball'ı + repo
bundle'ı + geri getirme adımları); depoda hiçbir izi kalmadı ve geri dönüş
planlanmıyor.

Kapanışın tek teknik ön koşulu Django'da lokasyon yönetimi ekranıydı (madde 2c) —
o da 2026-07-31'de tamamlandı. Kazanç ölçüldü: **1,31 GiB RAM**, makinedeki 3,9
GiB'ın üçte biri (kalan iki konteyner toplam 35 MiB). Veri kaybı riski yoktu ve
olmadı: tüm iş verisi Postgres'te, o arayüzün kendi volume'ünde yalnızca ekran
tanımları vardı.

**Bunun düşürdüğü kısıtlar** (aşağıdaki maddeleri okurken geçerli): view'ların
anlamını değiştirirken ya da migration sırası kurarken korunması gereken ikinci bir
tüketici yok, migration'lardaki "önce iki arayüzü düzelt" adımı tek arayüze indi ve
rol ayrımı (madde 2b) tamamen Django'da çözülecek.

---

## 1. Giriş akışı ✅ TAMAMLANDI (2026-07-30)

Giriş kutusu ana ekranın en altında, modül kartlarının da altında kalıyordu.

Yapılanlar: `/` artık yönlendirici (`views.ana_ekran`) — giriş yapılmışsa **veya**
session'da `misafir` bayrağı varsa panel, aksi hâlde `/giris/`. Giriş formu
çoğaltılmadı, yönlendirme tercih edildi. Giriş ekranında ayraç + **"Giriş yapmadan
devam et"** (`/misafir/`, bayrağı işaretleyip panele döner). Ana ekrandaki giriş
kutusu kaldırıldı; üst çubuğa giriş yapmamış kullanıcı için **"Giriş yap"** eklendi
(ana ekran, katalog/stok, hareket geçmişi) — girişin kalıcı görünür yolu bu, asıl
keşfedilebilirlik düzeltmesi. `LoginView` artık `redirect_authenticated_user=True`.

Bilinçli detaylar:

- **Misafir seçimi session'da hatırlanıyor**, yani kapı tarayıcı başına bir kez
  çıkıyor. Katalog ön büroda müşteri karşısında hızla açılan bir ekran; her açılışta
  araya sayfa koymak günde onlarca gereksiz tıklama olurdu.
- **Çıkışta bayrak da temizleniyor** — Django'nun `logout()`'u session'ı flush ettiği
  için bedavaya geliyor, yani "Çıkış" güvenilir biçimde giriş ekranına döner.
- Katalog/stok/hareketler hâlâ **girişsiz açık**; sadece yazma sayfası
  `@login_required` ve `next` ile geri dönüş korunuyor.

Doğrulama: gerçek tarayıcıda 25/25 kontrol (kök yönlendirme, misafir devam, session
hafızası, üst çubuk her iki durumda, giriş yapmışken `/giris/`, çıkış sonrası kapının
geri gelmesi, `next` akışı, mobil, şablon sızıntısı, konsol). Test girişi için
`default` SQLite'ta geçici kullanıcı açılıp sonunda silindi — paylaşımlı Postgres'e
dokunulmadı.

---

## 2. Yönetim paneli (`/yonetim/`)

Tek bir yönetim giriş noktası; içinde **iki** kart: Kullanıcılar ve Lokasyonlar.
Sadece yetkili kullanıcıya görünür.

Başlangıçta üçüncü bir "Ürünler / Yakında" kartı vardı; **2026-07-31'de kaldırıldı**.
Ürün ekleme/düzenleme madde 3'te tamamlandı ama `@login_required` olarak, yani giriş
yapan herkese açık — yönetim paneli ise `is_staff` kapısının arkasında. Ekran hazır
olduğu hâlde "Yakında" yazması kullanıcıyı yanıltıyordu, ve zaten yönetici işi
olmadığı için o panele ait değildi. Ürünün doğru yeri katalog sayfası.

### 2a. Kullanıcı yönetimi ✅ TAMAMLANDI (2026-07-31)

`/yonetim/` (kartlar) + `/yonetim/kullanicilar/` (liste, ekleme, parola, düzenleme).
Kod `katalog/yonetim.py` ve `katalog/forms.py`'de; mimari gerekçeler CLAUDE.md'de.

Yapılanlar: `is_staff` kapısı (`yonetici_gerekli`), yetkisiz kullanıcıya kendi 403
şablonu, kullanıcı listesi + defterdeki hareket sayısı, hesap ekleme, yönetici
yetkisi, parola belirleme, pasife alma. Ana ekrandaki yönetim kartı yalnızca
yöneticiye görünüyor.

Bilinçli kısıtlar: kullanıcı adı düzenlenemez ve hesap silinemez (defter
append-only); e-posta zorunlu + tekil (kimliğin kendisi); yönetici kendi yetkisini
kaldıramaz/hesabını kapatamaz.

Doğrulama: gerçek tarayıcıda 30/30 kontrol — yetki kapısının üç durumu, zayıf parola
reddi, mükerrer e-posta reddi, kilitlenme korumaları, parola değişince yeni parolayla
giriş, pasife alınan hesabın giriş yapamaması, mobil, şablon sızıntısı, konsol. Test
hesapları çalışmaya özel zaman damgalı ön ekle açılıp pk ile siliniyor; sonda mevcut
hesapların ve paylaşımlı Postgres'in değişmediği ayrıca ölçülüyor.

**Kalan:** bugünkü tek hesabın (`omer`) parolası geliştirme sırasında konuldu.
Artık `/yonetim/kullanicilar/` üzerinden değiştirilebilir — kullanıcının kendi
yapması gereken bir iş, kod tarafında yapılacak bir şey kalmadı.

Yönetim paneline liste sayfalarının üst çubuğundan doğrudan bağlantı **yok**; yol
ana ekrandaki kart. Sekme şeridine dördüncü bir öğe eklemek mobilde daraltıyordu,
yönetim de günlük kullanımda sık gidilen bir yer değil.

### 2b. Rol/yetki ayrımı → **listenin sonuna alındı** (2026-07-31, kullanıcı kararı)

Şu an giriş yapan herkes her ürüne her işlem tipini uygulayabiliyor. İç ağda tek ekip
için bugün yeterli; **fason/dış kullanıcı girdiği anda** gözden geçirilmeli. O gün
gelene kadar beklemesine karar verildi — madde 6'ya taşındı, sıradaki iş değil.

### 2c. Lokasyon yönetimi ✅ TAMAMLANDI (2026-07-31)

`/yonetim/lokasyonlar/` (hiyerarşik liste + pasife alma) ve
`/yonetim/lokasyonlar/yeni/` (ekleme). Kod `katalog/lokasyon_yonetimi.py` +
`katalog/forms.py::LokasyonEklemeFormu`; mimari gerekçeler CLAUDE.md'de.

Yapılanlar: liste `v_lokasyonlar_detay`'dan okuyor (ham `lokasyonlar` değil) — kök
altında rafları girintili gösteriyor. Ekleme formu ad, tip (`DAHILI`/`FASON`/
`NUMUNE`), isteğe bağlı **üst lokasyon** (yalnızca aktif kökler) ve isteğe bağlı
`kod` alıyor. İlk hâlinde silme yoktu, yalnızca pasife alma (`aktif_mi = false`);
silme aynı gün ayrıca eklendi (aşağıya bakın). Yeni bir veritabanı fonksiyonu
**yok**: migration 004 kuralların tamamını bildirimsel yazmıştı (CHECK, üretilmiş
kolonlarla bileşik FK, iki tekillik kısıtı), Django doğrudan INSERT/UPDATE yapıyor.

Ayrıca üç tuzak noktası düzeltildi (bkz. aşağıdaki "Kalan tuzak" bölümünün eski
hâli): `views.py:81` (ana ekran KPI), `:453` (hareket geçmişi filtresi), `:675`
(stok işlem formu) artık `LokasyonDetay` + `yaprak_mi` kullanıyor.

**İki cross-DB tuzağı ölçülerek bulundu ve önlendi** (ikisi de proje henüz
`DATABASE_ROUTERS` eklemediği için — CLAUDE.md): (1) `ModelForm`'un FK alanı için
otomatik kurduğu açılır liste sorgusu `using('metaks')` olmadan `default`'a
gidip "no such table" ile çöküyordu — `__init__`'te queryset elle atanarak
çözüldü. (`default` o tarihte SQLite'tı; 2026-07-31'de Postgres'e alındı — tuzak
aynen duruyor, yalnızca hata metni `relation does not exist`'e döndü.) (2) `kod`'a `unique=True` koymak Django'nun otomatik `validate_unique()`'ini
yine yanlış bağlantıya sorgu attırırdı — bilerek konulmadı, kısıt ihlali gerçek
INSERT'in `IntegrityError`'ı yakalanıp `constraint_name`'e göre Türkçeleştiriliyor.

Doğrulama: gerçek tarayıcıda 31/31 kontrol — kök/raf oluşturma, mükerrer ad+tip ve
mükerrer kod reddi (Türkçe mesaj), raf eklenince dolabın kendisinin stok formundan
kaybolması (artık yaprak değil), pasife alınca hem stok formundan kaybolup hem
hareket geçmişi filtresinde kalması, raf-altına-raf denemesinin reddi (derinlik
koruması), yetki kapısı, mobil, şablon sızıntısı, konsol.

### Silme eklendi ✅ (2026-07-31)

Ekranın ilk hâlinde silme yoktu; kullanıcı "gerçekte olmayan bazı konumlar
gözüküyor" deyince eklendi. "Sil" yalnızca **hiç kullanılmamış** satırlarda
çıkıyor (defterde hareketi yok + altında rafı yok) — kararın kendisi üç
`ON DELETE RESTRICT`'te, arayüz onu yalnızca önceden hesaplayıp butonu
gizliyor; ihlal yine de olursa `IntegrityError` Türkçeye çevriliyor.
Gerekçeler CLAUDE.md'de.

Ön koşul, defterdeki test hareketlerinin temizliğiydi (aşağıdaki madde):
o 30 kayıt gerçekte var olmayan dört lokasyonu yerinde tutuyordu. Temizlik
sonrası beş lokasyon (Ana Depo, Sevkiyat Alanı, Fason Atölye 1, Depo 1,
Kaplama) ekrandan silindi; geriye kullanıcının doğruladığı üç gerçek konum
kaldı: **Metaks, Fabrika, Skor**.

Doğrulama: gerçek tarayıcıda 24/24 kontrol — geçici dolap+raf üzerinden
hiyerarşi kısıtı (rafı olan dolapta buton yok), butonsuz satıra elle POST'un
Türkçe mesajla reddi, raf silinince dolabın silinebilir hâle gelmesi, beş
lokasyonun tek tek silinmesi, kalan listenin tam olarak üç isim olması, beş
sayfanın ayakta kalması ve stok işlem formunun yalnızca o üç lokasyonu
sunması.

---

## 3. Ürün ekleme / düzenleme ✅ TAMAMLANDI (2026-07-31)

`/urun/ekle/` ve `/urun/<stok_kodu>/duzenle/` — aynı formu (`UrunFormu`) kullanıyor.
Kod `katalog/urun_servisi.py` (`stok_servisi.py` deseninde ince çağrı katmanı,
`urun_kaydet()` sarmalayıcı + görsel dosya yaz/sil), `katalog/urun_yonetimi.py`
(view'lar) ve `katalog/forms.py::UrunFormu`'da.

**Kapsam kararları (kullanıcıyla netleştirildi, 2026-07-31):** yalnızca ekleme değil
**ekleme + düzenleme** birlikte; erişim **giriş yapmış herkes** (`@login_required`,
yönetim panelindeki `is_staff` değil — stok işlemiyle aynı kapı); kategori **var olan
seçim + formdan yeni açma** birlikte; **ana ürün/varyant ilişkisi dahil** (urun_tipi
ANA_URUN/ALT_PARCA/VARYANT + üst ürün + varyant adı).

### Giriş noktaları

- Katalog/stok sayfalarında sonuç sayısının yanında **"+ Ürün ekle"** — yalnızca
  giriş yapmış kullanıcıya (`_govde.html`).
- **Boş arama sonucundan ekleme:** arama sıfır sonuç verirse "'`X`' koduyla ürün
  ekle" bağlantısı, kod forma önceden dolu gelir.
- Ürün detay panelinde **"Ürünü düzenle"** — katalog ve stok panelinde ortak
  (kategori/ölçü stokla ilgili değil, `stok_goster`'a bağlı değil).

### GUNCELLE modu KISMİ değil — en riskli kısım buydu

`urun_kaydet()` her çağrıda **tüm alanları yeniden yazıyor**; boş bırakılan alan
NULL'a döner (tek istisna görsel — verilmezse mevcut durum korunur). Bu yüzden
düzenleme formu ürünün güncel tüm alanlarını `initial=` ile dolduruyor
(`models.Urun` — ham `urunler`, `AktifUrun`/view değil, çünkü PASİF/taslak bir
ürünü de açabilmek gerekiyor). **Gerçek bir üründe (1001013) doğrulandı:** GET ile
form yüklenip hiçbir alan değiştirilmeden POST edildi, veritabanı satırı
**birebir aynı** kaldı.

### İki cross-DB tuzağı ölçülerek bulundu

Lokasyon formunda (madde 2c) düşülen tuzağın aynısı burada da pusuya yatmıştı:
`ModelChoiceField`'ların (kategori/hammadde/kaplama) `ModelForm` yerine düz
`forms.Form` içinde kullanılması ve queryset'lerin `__init__`'te elle
`using('metaks')` ile atanması bu riski baştan bertaraf etti — `UrunFormu` bilerek
`ModelForm` DEĞİL (yazmanın tek kapısı zaten `urun_kaydet()`, bir `.save()` değil).

**Kategori oluşturma büyük/küçük harf duyarsız:** `kategoriler.kategori_adi`
UNIQUE kısıtı Postgres'te harf duyarlı ("Toka" ≠ "TOKA"); duyarsız arama
(`urun_servisi.kategori_id_cozumle`) var olanı bulup kullanıyor, sessizce
neredeyse-aynı iki kategori açılmasını önlüyor.

### Bir gerçek veri tutarlılığı hatası bulundu ve düzeltildi

JS `urun_tipi` VARYANT/ALT_PARCA seçilince üst ürün alanını gösteriyor, ANA_URUN'a
dönülünce **gizliyor ama temizlemiyor** — kullanıcı önce VARYANT + üst ürün yazıp
sonra ANA_URUN'a dönerse tarayıcı gizli kalan eski değeri yine de POST eder. DB bunu
reddetmiyor bile (kısıt yalnızca VARYANT/ALT_PARCA'da üst ürünü zorunlu kılıyor,
ANA_URUN'da yasaklamıyor) — `UrunFormu.clean()`'de `urun_tipi == 'ANA_URUN'` olunca
`parent_stok_kodu`/`varyant_adi` bilerek temizleniyor.

### Doğrulama

Önce Django test client ile Python seviyesinde (taslak, görsel+kategori, varyant,
mükerrer kod, round-trip düzenleme — hızlı iterasyon için), sonra gerçek tarayıcıda
**35/35 kontrol**: taslak/AKTİF geçişleri, iki ayrı mesaj dalı (EKLE+görsel:
"eklendi ve katalogda yayına alındı" / GUNCELLE+görsel: "güncellendi"), stok kodu
kilidi (disabled alan, formda tamperlense bile yok sayılıyor), varyant
oluşturma + üst ürünsüz reddi, yetki kapısı (yönetici olmayan erişebiliyor),
mobil, şablon sızıntısı, konsol. Diğer altı takım da yeşil (toplam 202). Test
satırları UI üzerinden eklenip **doğrudan SQL + dosya sistemiyle** temizlendi
(uygulama "sil" sunmuyor — lokasyon ile aynı tasarım); sonda `urunler`/
`kategoriler`/`urun_gorselleri` satır sayılarının başlangıca döndüğü, diskteki
test görsellerinin silindiği ve `stok_hareketleri`'nin hiç değişmediği ölçüldü.

Yol boyunca iki kendi hatamı yakaladım: `urun_formu.html`'e Django mesaj çerçevesi
gösterimini eklemeyi unutmuştum (başarı mesajları sessizce kayboluyordu) ve
başlıktaki "flex-wrap emniyet kemeri" notunu yine iki satırlık `{# #}` ile yazıp
HTML'e sızdırmıştım (bu projede **4. kez** düşülen tuzak) — `stok_islem.html`'de de
aynı kopyalanan iki satırlık yorum vardı, ikisi de düzeltildi.

**Kasıtlı kapsam dışı bırakılanlar:** hammadde/kaplama için "yeni ekle" yok (bugünkü
veride ikisi de 0 dolu satır — kategori'nin aksine talep de yok); ana ürün seçimi
düz metin kutusu, arama/otomatik tamamlama yok (`urun_kaydet()` zaten "üst ürün
bulunamadı" diye kendi Türkçe hatasını veriyor, ikinci bir doğrulama katmanı
gerekmedi).

---

## 3b. Hızlı stok işlemi girişi ✅ TAMAMLANDI (2026-07-31)

`/stok/hizli/` — tek büyük, otomatik odaklanan kutu; kod girilince o ürünün
`stok_islem` formuna yönlendiriyor. Kod `views.py::hizli_islem` / `hizli_oneriler` /
`_oneriler`, şablonlar `hizli_islem.html` + `_hizli_oneriler.html`. Mimari
gerekçeler CLAUDE.md'de. Aşağıdaki tasarım notlarının **tamamı** uygulandı:
düz form (barkod okuyucu için JS'siz yol), bulunamadı dalında ön doldurulmuş "yeni
ürün oluştur" bağlantısı, kutunun altında HTMX otomatik tamamlama.

### Kapsam, uygulama sırasında büyüdü: PASİF ürünler

Yazarken ortaya çıkan gerçek eksik: `stok_islem` ürünü `AktifUrun`'dan
(`v_aktif_urunler`) okuyordu, o da yalnızca AKTİF satırları gösteriyor — yani
**2.973 ürünün 1.193'üne (kataloğun %40'ı) arayüzden hiç stok işlemi
yapılamıyordu**, devam eden sayımın ortasında. Veritabanında böyle bir kısıt yok
(`stok_hareketi_kaydet()` PASİF ürünü kabul ediyor, canlı şemada `BEGIN`/`ROLLBACK`
içinde ölçüldü); engel yalnızca Django'nun kaynak seçimiydi.

Kullanıcı onayıyla `stok_islem` ham `urunler`'e de bakacak şekilde genişletildi
(`views._islem_urunu`). PASİF ürün açıldığında görsel yerine yer tutucu ve
"katalogda pasif, sebebi görselsizlik, stok işlemine engel değil" açıklaması +
düzenleme bağlantısı basılıyor. Ayrıntı CLAUDE.md.

### Aynı gün tek sayfaya çevrildi (kullanıcı geri bildirimi)

İlk sürüm yalnızca bir yönlendiriciydi: kod alıp `stok_islem` sayfasına atıyordu.
Kullanıcı "bu sayfayı depocunun kullanacağı şekilde düşünmüştüm — mal geldiğinde
hemen işlesin" deyince tek sayfaya çevrildi. Bugün: kodu okut → ürün ve form aynı
ekranda → kaydet → kutu temizlenip odaklanır → sıradaki ürün. Sayfa hiç değişmiyor.

Form kopyalanmadı; `_stok_islem_govde.html` + `views._islem_baglami()` iki ekranda
ortak. Yol boyunca gerçek bir yarış hatası yakalandı (iki HTMX tetikleyicisi aynı
hedefe yazıyordu, Enter'ın getirdiği formu bayat öneri isteği eziyordu) —
yalnızca gerçek tarayıcıda görülüyordu, ayrıntı ve çözüm CLAUDE.md'de.

### Doğrulama

Python 39/39, gerçek tarayıcı 27/27, yarış/artık senaryoları 7/7, odak döngüsü 4/4
— listeler CLAUDE.md'de. Geçici test hesapları zaman damgalı ön ekle açılıp sonda
silindi; `stok_hareketleri` 0 satırda kaldı, `urunler`/`urun_gorselleri`/
`lokasyonlar` hiç değişmedi. Defter yazan yol bilinçli olarak uçtan uca
ölçülmedi: `hareket_id` 1 ilk gerçek harekete saklı, test satırı onu tüketirdi.

### Yapılmayan (bilinçli)

Telefon kamerasıyla QR okuma: `getUserMedia` "secure context" (HTTPS) istiyor, site
düz HTTP — aşağıdaki HTTPS maddesi çözülmeden zaten çalışmaz. Donanım okuyucular
(USB/Bluetooth, klavye gibi davranırlar) bugünkü kutuyla ek kod olmadan çalışıyor,
yani gerçek ihtiyaç karşılanıyorsa kamera taraması hiç gerekmeyebilir.

### Özgün tasarımdan sapılan tek nokta

Not, önerilerin `arama_metni` üzerinden yapılmasını söylüyordu. Uygulanmadı: o kolon
yalnızca `v_aktif_urunler`'da var (1.780/2.973) ve bu kutu PASİF ürünleri de bulmak
zorunda; ayrıca buraya kod yazılıyor, açıklama değil. Arama ham
`urunler.stok_kodu` üzerinde yapılıyor. Geri kalan her şey nottaki gibi.

---

## 4. Numune takibi (dolap / raf)

**Karar:** ayrı veritabanı **yok**, ayrı tablo **yok**. Numune, fiziksel olarak ürünün
bir adedinin bir yerde durması demek — sistemde bunun adı zaten **lokasyon**. Mevcut
altyapı (`lokasyonlar` + `stok_hareketleri` + TRANSFER + detay panelindeki lokasyon
dökümü) işi büyük ölçüde karşılıyor: numune dolabı bir lokasyon olarak tanımlandığı
anda "bu ürünün numunesi Vitrin'de, 2 adet" bilgisi neredeyse yeni ekran yazmadan
çıkıyor, numune ödünç alınıp geri konduğunda kaydı da bedavaya geliyor.

Ayrı veritabanı elendi: `urunler` ile join edilemez, iki bağlantı, iki yedekleme,
bütünlük sadece gelenekle korunur. Aynı iş, aynı ürünler — aynı veritabanı.

### Adresleme: kütüphane düzeni (karar verildi)

Kullanıcının istediği "kütüphanede kitap bulur gibi" düzen → **iki seviyeli hiyerarşi +
kısa kod**: dolap (`N1`) → raf (`N1-R3`). `lokasyonlar`'a `ust_lokasyon_id` (self-FK) ve
`kod` kolonları eklenir; mevcut 8 lokasyon ikisi de NULL kalarak etkilenmez.

Düz isimlendirme ("Numune Dolabı 1 – Raf 3" tek satır) elendi: dolap sayısı belirsiz ve
yeniden düzenleneceği söylendi — düz isimde bir dolabı yeniden adlandırmak N satır,
hiyerarşide tek satır; ayrıca "Dolap 1'de ne var" sorgusu string önekine bağlı kalmaz.
Derinlik bilerek 2 seviyede sabit, genel amaçlı ağaç kurulmuyor.

### Django tarafında yapılacak

- Numune lokasyonları için stok işlemi formunda **iki adımlı seçim** (dolap → raf) ya da
  aranabilir kutu; onlarca rafı düz bir `<select>`'e dökmek kullanılamaz olur.
- Detay panelinde numune satırları ayrı gösterilsin: **"478 adet · 2 numunede"**.
- Ürün detayında "Numunesi nerede?" doğrudan görünür olsun — asıl sorulan soru bu.

### Zamanlama

Sıralamada 3'ten sonra ama **iş yükü olarak çok daha küçük** (iki migration + birkaç
lokasyon satırı + rozet), gerekirse araya girebilir. Ek gerekçe: **sayım hâlâ sürüyor**
ve numune dolabını açıp 3 adet bulan kişinin bunu yazacağı dürüst bir yer bugün yok —
ya hiç yazılmıyor ya bir depo lokasyonuna karışıyor. Sayımın doğruluğunu etkileyen bir
eksik, sonradan eklenen bir süs değil.

---

## 5. Hareket geçmişinde CSV / Excel dışa aktarma

Sayım denetimi için: `/stok/hareketler/` üzerindeki **aktif filtrelerle** aynı sonucu
dosya olarak indirme. Filtre çubuğuna bir "Dışa aktar" butonu.

Dikkat edilecekler:

- Tarihler **yerel saatle** yazılmalı — `yerel_tarih()` kullanılmazsa dosyada 3 saat
  geri değerler olur (bkz. CLAUDE.md, zaman dilimi tuzağı).
- Excel'in Türkçe yerel ayarı CSV'de **`;` ayracı** ve **UTF-8 BOM** bekler; virgül +
  BOM'suz dosya açıldığında hem Türkçe karakterler bozulur hem her satır tek hücreye düşer.
  Gerçek Excel'de açıp doğrulanmalı.
- Sayfalama yok, filtrelenmiş kümenin tamamı; `StreamingHttpResponse` ile satır satır
  akıtılmalı (bugün 30 satır ama defter append-only, sürekli büyüyecek).
- Salt-okunur iş, `stok_hareketi_kaydet()` disiplinine dokunmuyor.

Bağımsız iş. Küçük.

---

## veritabani tarafı — ✅ TAMAMLANDI (2026-07-30)

Migration 004 (numune lokasyonları) ve 005 (`urun_kaydet()`) canlı `depo_sistemi`'ne
uygulandı ve doğrulandı; öncesi/sonrası birebir aynı (o günkü hâliyle 8 lokasyon,
30 hareket, 1780 AKTİF, `v_toplam_stok` 8 satır / 478 adet — lokasyonlar ve defter
2026-07-31'de temizlendi, bkz. aşağısı). Sözleşmenin güncel/tam hâli
`veritabani/docs/aktif-urun-veri-sozlesmesi.md`'de; migration'ların uygulanma
kayıtları `veritabani/CLAUDE.md`'nin "Database schema" bölümünde.

Sonuçta kullanılabilir hâle gelenler:

- `v_lokasyonlar_detay` — açılır listelerin **tek kaynağı**; `kod`, `tam_ad`
  ("Numune Dolabı 1 · Raf 3"), `yaprak_mi`.
- `v_toplam_stok` artık **satılabilir** stok (NUMUNE hariç), `v_fiziksel_stok` hepsi.
- `v_numune_konumlari` — "bu ürünün numunesi nerede?" doğrudan buradan.
- `v_lokasyon_stok_ozet`'e `lokasyon_kodu` + `lokasyon_tam_adi` eklendi (sona; mevcut
  kolonların adı/sırası korundu, `LokasyonStok` modeli etkilenmedi).
- `urun_kaydet(p_mod, p_stok_kodu, p_yapan_kullanici, …, p_ana_gorsel_dosya_adi)` →
  `(stok_kodu, katalog_durumu, gorsel_id, mesaj)`; `urun_sonraki_gorsel_sirasi()`.
- `urunler`'e `olusturan_kullanici` / `guncelleyen_kullanici`; `aktif_mi` varsayılanı
  FALSE'a düzeltildi.
- `stok_hareketi_kaydet()` artık sadece **yaprak** lokasyona yazıyor.

### ✅ Lokasyon sorguları düzeltildi (2026-07-31, madde 2c ile birlikte)

Django'daki üç yer `v_lokasyonlar_detay` + `yaprak_mi` filtresine taşındı:
`views.py:81` (ana ekran KPI), hareket geçmişi filtresi ve stok işlem formu
(bkz. madde 2c). **Tipe göre dışlanmadı** — numune dolabını açıp 3 adet bulan
kişi o rafı seçebiliyor, çözülmek istenen problem buydu.

Artık gerçek NUMUNE dolap/raf satırları girilebilir; ön koşul (Django tarafı)
tamamlandı.

---

## Sırası gelmemiş / arka planda duranlar

- **Otomatik test yok** (`katalog/tests.py` boş). Django test runner'ı `metaks` bağlantısı
  için test veritabanı oluşturmaya çalışır — paylaşımlı `depo_sistemi`'ne karşı istenmeyen
  davranış. Muhtemel yol: `SimpleTestCase` / `databases = {'default'}` + fixture katmanı.
- **Test hareketleri temizlendi ✅ (2026-07-31)** — `veritabani` migration 006 defterdeki
  30 test kaydının tamamını sildi, sequence 1'e alındı. Rollback dosyası uygulanmadan
  önce ölçüldü (uygula → geri al → checksum birebir aynı). Defter bugün boş; ilk gerçek
  sayım hareketi 1 numarayı alacak.
- **Çoklu görsel galerisi yok** — 1.780 ürünün sadece 19'unda ikinci aktif görsel var,
  kazanç küçük.
- **Otomatik tazeleme yok** — açık duran sekme yenilenene kadar eski veriyi gösterir.
  Canlı stok ekranında `hx-trigger="every 30s"` mantıklı olur, katalogda gereksiz.
- **Üretim ayarları** (DEBUG, SECRET_KEY, HTTPS) ve hosting kararı. Giriş eklendiği
  için artık kritik: parolalar bugün HTTP üzerinden gidiyor, **dışarı açılmadan önce**
  HTTPS ve gerçek bir `SECRET_KEY` şart. 2026-07-31'de sunucu `0.0.0.0:8000`'e alındığı
  için (bkz. CLAUDE.md, Ağ erişimi) uygulama artık yerel ağa da açık — Tailscale trafiği
  şifreli ama LAN trafiği değil. `DJANGO_DEBUG=true` da ağ üzerinden hata sayfası (kaynak
  kod, SQL, dosya yolları) gösteriyor. İkisi de "sadece kendi cihazlarım" varsayımına
  dayanıyor; ofis ağında başkaları varsa **`100.64.0.6:8000`'e bağlanmak** (yalnız
  tailnet arayüzü) tek kelimelik düzeltme.
- ~~**Branch modeli**~~ — ✅ 2026-07-31: iki repo tek `metaks` deposunda birleşti,
  düzen artık depo geneli geçerli. 2026-07-31'de `review` silindi, model `master` +
  `dev`'e indi: Furkan ikinci bir Mac'ten `dev`'e devam ediyor (kök `CLAUDE.md`).
