# Yapılacaklar

Sırayla önceliklendirilmiş iş listesi. Mimari kararlar ve mevcut durum `CLAUDE.md`'de;
burası "sırada ne var" sorusunun cevabı.

Sıra kullanıcıyla kararlaştırıldı (2026-07-30):
**giriş akışı → yönetim paneli/kullanıcılar → ürün ekleme → numune takibi → CSV.**

4 ve 5 numaralı işler `metaks_DB` tarafında şema hazırlığı bekliyor; o iş paralel
yürüyebilir, 1 ve 2 hiçbir şeye bağlı değil.

---

## 0. Appsmith'in emekliye ayrılması (2026-07-31 kararı)

Kullanıcı kararı: Appsmith artık atıl; Django arayüzü onun kapsamını geçti, görsel
kalite ve kullanılabilirlikte de gerisinde kaldı. Bundan sonra **hem veritabanı hem
arayüz geliştirmeleri Appsmith düşünülmeden** yürüyecek.

Bu ayrı bir "proje" değil — aşağıdaki maddelerin içine dağılıyor. Buradaki tek amacı
neyin gerçekten gerektiğini ve neyin kendiliğinden düştüğünü tek yerde tutmak.

### Kapsam karşılaştırması (ölçüldü)

| Appsmith sayfası | Django karşılığı | Durum |
| --- | --- | --- |
| `YonetimAnaSayfasi` | `/` (Panel) | ✅ karşılanıyor |
| `UrunlerKatalog` | `/katalog/` | ✅ karşılanıyor |
| `StokOzet` | `/stok/` | ✅ karşılanıyor |
| `StokIslemi` | `/stok/islem/<stok_kodu>/` | ✅ karşılanıyor |
| `Page1` | — | iskelet artığı (`Query1` ve `Query2` birebir aynı SQL), karşılığı gereksiz |
| `LokasyonYonetimi` | **yok** | ❗ **tek gerçek boşluk** |

### Tek gerçek boşluk: lokasyon yönetimi

Lokasyon ekleme/pasife alma bugün **yalnızca** Appsmith'ten yapılabiliyor; Django'da
hiç karşılığı yok. Bu, Appsmith'i kapatmanın tek teknik ön koşulu.

Ama bu iş zaten yapılacaktı ve Appsmith'te **zaten yapılamıyordu.** `LokasyonEkle`
sorgusunun tamamı şu:

```sql
INSERT INTO lokasyonlar (lokasyon_adi, tip)
VALUES ({{ YeniLokasyonAdiInput.text }}, {{ YeniLokasyonTipiSelect.selectedOptionValue }});
```

`ust_lokasyon_id` ve `kod` yok — yani migration 004'ten sonra bu ekranla **bir numune
dolabı da rafı da açılamıyor**; üstelik tip açılır listesi `Dahili`/`Fason`'u sabit
gömüyor, `NUMUNE` orada hiç görünmüyor. Yani madde 4 (numuneler) için lokasyon ekranı
nasılsa sıfırdan yazılacaktı. **Appsmith'i bırakmak yeni iş çıkarmıyor, var olan işin
yerini değiştiriyor.**

Yeri: madde **2c** (yönetim panelinin üçüncü kartı) — orada anlatıldı.

### Kapatma sırası (her adımı geri alınabilir)

1. **Django lokasyon yönetimi** (madde 2c) + üç lokasyon sorgusunun
   `v_lokasyonlar_detay` / `yaprak_mi`'ye taşınması (aşağıdaki tuzak bölümü).
2. **Önce kontrol:** sayıma ait bir giriş hâlâ Appsmith'ten yapılıyor mu? (Sayım verisi
   Excel'de tutuluyor, bu yüzden büyük ihtimalle hayır — ama kapatmadan önce sorulacak
   tek soru bu.)
3. `docker compose stop appsmith` — **silme, durdur.** Geri dönüş `start` ile anında.
   Kazanç ölçüldü: **1,31 GiB RAM**, yani makinedeki 3,9 GiB'ın üçte biri (`depo-postgres`
   27 MiB, `depo-gorsel-sunucu` 8 MiB — Appsmith tek başına ikisinin ~40 katı).
4. Bir süre sorunsuz geçerse: `metaks_DB/docker-compose.yml`'den `appsmith` servisi ve
   `appsmith_data` volume'ü kaldırılır, `depo-appsmith-arayuz` reposu GitHub'da
   **arşivlenir** (silinmez — sorgu geçmişi ve alınan kararların kaydı orada).

### Ne kaybetmiyoruz

Appsmith stateless: tüm iş verisi Postgres'te. Kendi volume'ü sadece uygulama tanımını
ve Appsmith'e özel kullanıcı hesaplarını tutuyor; uygulama tanımı da zaten
`depo-appsmith-arayuz` reposunda. Kapatmak veri kaybettirmiyor.

### Kendiliğinden düşen kısıtlar

- `depo-appsmith-arayuz`'da bekleyen iş (`StokIslemi/LokasyonlariGetir` ve
  `LokasyonYonetimi/LokasyonlarListele`'ye yaprak filtresi) → **iptal**.
- `metaks_DB` migration'larındaki "önce iki arayüzü düzelt, sonra veri gir" adımı
  **tek arayüze** iner.
- View'ların anlamını değiştirirken dört Appsmith tüketicisini koruma zorunluluğu kalkar.
  (`v_toplam_stok`'un "satılabilir stok" olması kendi başına da doğru karardı, geri
  almaya gerek yok — fiziksel toplam için `v_fiziksel_stok` var.)
- `metaks_DB/CLAUDE.md`'deki "rol ayrımı gerekirse ayrı Appsmith uygulamalarıyla
  çözülür" planı düşer; rol ayrımı Django'da yapılacak (madde 2b).

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

Tek bir yönetim giriş noktası; içinde üç kart: **Kullanıcılar**, **Ürünler**,
**Lokasyonlar**. Diğer sayfalarla aynı tasarım dili. Sadece yetkili kullanıcıya görünür.

### 2a. Kullanıcı yönetimi

Kullanıcılar Django'nun **SQLite `default`** bağlantısında (paylaşımlı METAKS
Postgres'ine dokunulmuyor) — yani bu iş `metaks_DB` tarafında hiçbir şey beklemiyor.

- Kullanıcı listesi, ekleme, parola değiştirme, pasife alma.
- Django'nun hazır `/admin/`'i bugün de çalışıyor ve bu işi yapabilir; ama çerçeve
  gürültüsü (log kayıtları, izin matrisi, İngilizce terimler) ekip için uygun değil.
  `/admin/` kaçış yolu olarak açık kalsın, günlük kullanım sade ekrandan olsun.
- **Bunun içinde halledilecek:** bugünkü tek hesabın (`omer`) parolası geliştirme
  sırasında konuldu, değiştirilmeli.

### 2b. Rol/yetki ayrımı (bu adımda değil, ama buradan doğacak)

Şu an giriş yapan herkes her ürüne her işlem tipini uygulayabiliyor. İç ağda tek ekip
için bugün yeterli; **fason/dış kullanıcı girdiği anda** gözden geçirilmeli. Kullanıcı
ekranı yapılırken en azından "yönetici mi" ayrımının yeri hazırlansın.

### 2c. Lokasyon yönetimi — Appsmith'i kapatmanın ön koşulu

Bugün lokasyon eklemenin/pasife almanın tek yolu Appsmith; Django'da hiç yok
(bkz. madde 0). Liste + ekleme + pasife alma.

- **Liste kaynağı `v_lokasyonlar_detay`** (ham `lokasyonlar` değil): `kod`, `tam_ad`,
  `yaprak_mi` oradan geliyor. Dolap→raf hiyerarşisi girintili gösterilsin.
- **Ekleme formu**: ad, tip (`DAHILI`/`FASON`/`NUMUNE` — sabit gömme yok, kısıttan
  okunur), isteğe bağlı **üst lokasyon** (seçilirse raf, seçilmezse dolap/depo) ve `kod`.
- **Silme yok, pasife alma var** (`aktif_mi = false`) — Appsmith'in zaten yaptığı şey ve
  doğrusu bu: `stok_hareketleri`'nden gelen FK `ON DELETE RESTRICT`, geçmiş silinmemeli.

**Yeni bir veritabanı fonksiyonu gerekmiyor** — bu, `stok_hareketleri` ve `urunler`'den
farklı. Orada kural fonksiyonda çünkü tek bir INSERT'le ifade edilemiyordu (yeterli stok
hesabı, üç tabloya yayılan tek transaction). Lokasyonda migration 004 kuralların
**tamamını bildirimsel** yazdı: `tip` CHECK'i, `kok_mu`/`ust_kok_mu` üretilmiş
kolonlarıyla bileşik FK (derinlik 2'de sabit), `uq_lokasyonlar_kod`, üst lokasyona
kapsamlanmış `uq_lokasyonlar_ust_ad_tip`. Yani kapı zaten kısıtların kendisi; hatalı
satırı veritabanı reddediyor. Django formu doğrudan yazabilir.

⚠️ Tek teknik detay: `kok_mu` ve `ust_kok_mu` **GENERATED** kolonlar — `Lokasyon`
modeline alan olarak eklenmemeli, yoksa Django INSERT'te onlara da yazmaya çalışır.

Orta boy iş. Bağımsız.

---

## 3. Ürün ekleme / düzenleme

Kendi sayfası (`/urun/ekle/`), yönetim panelinden ve liste sayfalarından erişilir.

> **Ön koşul karşılandı (2026-07-30):** `urun_kaydet()` canlıda. Django tarafı artık
> `katalog/stok_servisi.py` deseninde ince bir çağrı katmanı yazacak — iş kuralı
> tekrarlanmayacak, dönen Türkçe mesaj olduğu gibi taşınacak.

### Giriş noktaları

- **Ürün sayısının yanına "+ Ürün ekle" butonu** (katalog ve stok sayfalarında),
  yalnızca **giriş yapmış** kullanıcıya görünür — müşteriye ürün gösterirken açılan
  katalog sayfasında yazma butonu görünmesin.
- **Boş arama sonucundan ekleme:** kullanıcı bir stok kodu arayıp bulamadığında
  "Bu koda ait ürün yok — `1005120` ile ürün ekle" bağlantısı çıksın. İhtiyacın gerçekten
  doğduğu an burası; kod da forma önceden doldurulmuş gelir.

### Form alanları

Zorunlu olan tek kolon `urunler.stok_kodu`; kalanların hepsi NULL kabul ediyor ya da
varsayılanı var. Ama pratikte kataloğun işe yaraması için gereken çekirdek: **stok kodu,
kategori, ürün tipi, ölçü ve ana görsel.**

Form ikiye ayrılsın: kısa bir **temel** bölüm + katlanır **detay** bölümü. Sebebi ölçüm:
`boya_mine`, `montaj_durumu`, `hammadde_adi`, `kaplama_adi` bugün **1.780 ürünün
hiçbirinde** dolu değil — hepsini öne koymak formu kimsenin doldurmadığı alanlarla
şişirirdi (detay panelinin "sadece dolu alanları göster" mantığının aynısı).

### Bu iş neden stok işleminden zor — ölçülmüş sebepler

1. **Satır eklemek yetmiyor, ürün görünmez kalır.** `urunler`'e INSERT edilen kayıt
   `katalog_durumu` varsayılanı olan `PASIF` ile doğar ve **öyle kalır**: bu değeri
   yöneten hiçbir trigger yok (kontrol edildi — `urunler` üzerinde trigger sıfır),
   AKTİF ataması migration 001'deki **tek seferlik backfill UPDATE**'ti. Ayrıca
   `chk_urunler_katalog_durumu_aktif_mi_tutarli` kısıtı `katalog_durumu` ile `aktif_mi`'nin
   birlikte hareket etmesini zorunlu kılıyor.
   Yani ekleme akışı bir bütün: görsel yükle → `urun_gorselleri`'ne
   `ana_gorsel_mi=true, aktif_mi=true` satırı → `urunler`'i `AKTIF` + `aktif_mi=true` yap.
   Üçü **tek transaction'da**, yoksa yarım ürün kalır.
2. **Görsel dosyası nereye yazılacak?** Görselleri nginx `gorsel-sunucu` servisi
   `<stok_kodu>_<sira_no>.<uzantı>` adlandırmasıyla sunuyor ve dizinin
   (`metaks_DB/images/final/products`) sahibi `metaks_DB`; nginx'e `:ro` bağlı, yazan
   taraf host. Bu repo bugün hiç dosya yazmıyor — Django'ya o dizine yazma yetkisi
   vermek gerçek bir bağlantı kararı.

**Sıralama kararı:** önce dosya, sonra DB. Fonksiyon hata verirse yazılan dosya silinir.
Ters sırada çökme olursa var olmayan dosyayı gösteren kırık ürün kalır; bu sırada en
kötü ihtimalle sahipsiz bir dosya kalır, o da zararsız.

Büyük iş, ön koşullu.

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

## metaks_DB tarafı — ✅ TAMAMLANDI (2026-07-30)

Devir metni `docs/metaks-db-istekleri.md`'de. Migration 004 (numune lokasyonları) ve
005 (`urun_kaydet()`) canlı `depo_sistemi`'ne uygulandı ve doğrulandı; öncesi/sonrası
birebir aynı (8 lokasyon, 30 hareket, 1780 AKTİF, `v_toplam_stok` 8 satır / 478 adet).

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

### ⚠️ Kalan tuzak: lokasyon sorguları (numune satırları GİRİLMEDEN önce)

Bugün hiçbir NUMUNE satırı yok, o yüzden hiçbir şey bozuk değil. Ama gerçek dolap/raf
satırları girilmeden **önce** her iki arayüz de `v_lokasyonlar_detay`'a taşınıp
`yaprak_mi` filtresi almalı. **Tipe göre dışlamak yanlış olur** — numune dolabını açıp
3 adet bulan kişi o rafı seçemezse çözülmek istenen problem yerinde kalır.

Django'da üç yer (dördüncüsü `views.py:577`, dokunulmasa da doğru — dolaplara hareket
yazılamadığı için `v_lokasyon_stok_ozet`'te hiç görünmezler):

| Yer | Bugünkü hâli | Numune girilince |
| --- | --- | --- |
| `views.py:651` (stok işlem formu) | `filter(aktif_mi=True)` | dolaplar seçilebilir görünür, fonksiyon reddeder |
| `views.py:431` (hareket geçmişi filtresi) | `.all()` — hiç filtre yok | aynı, üstelik pasifler de dahil |
| `views.py:81` (ana ekran KPI) | `filter(aktif_mi=True).count()` | **"Aktif lokasyon" rafları depo sayar** (5 → 23) |

Appsmith'teki iki yer (`StokIslemi/LokasyonlariGetir`,
`LokasyonYonetimi/LokasyonlarListele`) **artık düzeltilmeyecek** — madde 0, Appsmith
emekliye ayrılıyor. Bu, düzeltilecek yer sayısını beşten üçe indiriyor.

---

## Sırası gelmemiş / arka planda duranlar

- **Otomatik test yok** (`katalog/tests.py` boş). Django test runner'ı `metaks` bağlantısı
  için test veritabanı oluşturmaya çalışır — paylaşımlı `depo_sistemi`'ne karşı istenmeyen
  davranış. Muhtemel yol: `SimpleTestCase` / `databases = {'default'}` + fixture katmanı.
- **Test hareketleri ledger'da duruyor** (`1001013`, `1001020`) — ürün tamamlandığında
  `metaks_DB` tarafında numaralı migration ile temizlenecek (kararlaştırıldı).
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
- **Branch modeli** — kardeş repolardaki `master`/`dev`/`review` düzeni buraya
  uygulanmadı, karar bekliyor.
