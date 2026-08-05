# METAKS veritabanı — durum ve yol haritası

Bu belge veri/pipeline/şema tarafında “nerede kaldık, sırada ne var?” sorusunun
cevabıdır. Çalıştırma kuralları `../AGENTS.md`, arayüzün bağlayıcı veri sözleşmesi
`aktif-urun-veri-sozlesmesi.md`, ekran işleri ise `../../web/YAPILACAKLAR.md`
içindedir.

Canlı satır sayıları kalıcı gerçekler değildir. Aşağıdaki sayılar
**2026-08-04 tarihli salt-okunur denetim snapshot'ıdır**; karar vermeden önce
yeniden sorgulanmalıdır.

## Güncel çalışma noktası — 2026-08-06

Veri temizleme, normalizasyon, karışık stok kodu çözümü, PostgreSQL yüklemesi ve
görsel eşleme tamamlandı. **Migration 001–009 ortak `depo_sistemi` veritabanına
(Raspberry Pi, 100.64.0.7:5433) uygulanmış durumdadır.** 008 ve 009 2026-08-05'te,
kullanıcının açık onayı ve güncel yedekle uygulandı; ayrıntı aşağıdaki tabloda.

**Migration 010 ve 011 yazıldı, ortak veritabanına UYGULANMADI.** 010 SKU kimliğine
lak, vernik ve işçilik niteliklerini ekliyor ve montaj hali `HAM` değerini `DEMONTE`
yapıyor. 011 `stok_islemi_kaydet()`'e iki iş kuralı ekliyor: iadelerde karşı taraf
zorunlu ve rollü, ve amaç ↔ lokasyon tipi eşlemesi.

**İkisi bir arada uygulanır ve Django hizalanmadan uygulanmaz.** 011, 010'un üstüne
gelir; ikisinin de dosyaları hazır ve tek kullanımlık kopyada tam tur geçti
(010 ileri → 011 ileri → kabul testi → 011 rollback → 010 rollback). Uygulama ayrı
bir oturumda, güncel yedek ve kullanıcının açık onayıyla yapılacak.

**Django tarafı henüz hizalanmadı** — `web/` içinde `HAM` sabiti ve altı parametreli
`stok_kalemi_kaydet()` çağrısı duruyor. 010 Django hizalanmadan uygulanırsa varyant
ekleme ekranı kırılır. 011 mevcut ekranları kırmaz (yalnız yeni yazımlarda kural
uygular) ama arayüzün bu kuralları "ayna" olarak göstermesi gerekir; aksi hâlde
kullanıcı ancak kaydete bastıktan sonra reddedildiğini görür.

### İki ayrı `depo_sistemi` var, ikisi de güncel şemada

Bu bir hata değil, `web/AGENTS.md`'deki kurulumun sonucu: geliştirme makinesindeki
Docker (`localhost:5433`) varsayılan, Raspberry Pi'deki (`100.64.0.7:5433`) ortak
kopya, ve hangisine bağlanılacağı `web/.env` ile seçiliyor. **Şemaları aynı,
DEFTER İÇERİKLERİ ayrı** — biri diğerinin replikası değil, ikisi de kendi
hareketlerini biriktiriyor. Migration uygularken ikisini de saymak gerekir; bir
tarafta uygulayıp diğerini atlamak, `.env`'i çeviren kişide sessiz hatalar üretir.

| Ölçüt | Snapshot |
| --- | ---: |
| Ürün | 2.973 |
| AKTİF ürün | 1.780 |
| PASİF ürün | 1.193 |
| ANA_URUN | 2.968 |
| ALT_PARCA | 3 |
| VARYANT | 2 |
| Görsel kaydı / aktif görsel dosyası | 1.799 |
| Kategori | 35 |
| Hammadde | 7 |
| Boya/mine rengi | 13 |
| Kaplama rengi | 11 |
| Miras (BELIRSIZ) SKU | 2.973 |
| Lokasyon | 4 |
| Stok hareketi | 5 |

Stok snapshot'ında `v_lokasyon_stok_ozet` 2 satır ve toplam 1.000 adet,
`v_toplam_stok` ise 1 ürün ve toplam 1.000 adet döndürüyordu. Bu değerler depo
işlemleriyle değişir; belgeyi sayaç olarak kullanmayın.

Canlı lokasyonlar:

| ID | Ad | Tip | Kod | Üst | Yaprak mı? |
| ---: | --- | --- | --- | --- | --- |
| 6 | Metaks | DAHILI | — | — | Hayır |
| 8 | Fabrika | DAHILI | — | — | Evet |
| 10 | Skor | FASON | — | — | Evet |
| 44 | 21-1 | DAHILI | — | Metaks | Evet |

`Metaks`, altında `21-1` bulunduğu için artık hareket seçilebilen bir yaprak
değildir. Henüz `NUMUNE` tipinde gerçek dolap/raf satırı yoktur.

## Uygulanmış migration'lar

| No | Durum | Getirdiği ana değişiklik |
| --- | --- | --- |
| 001 | Uygulandı | `katalog_durumu`, `v_aktif_urunler`, arama indeksleri |
| 002 | Uygulandı | `v_lokasyon_stok_ozet`, `v_toplam_stok` |
| 003 | Uygulandı | İdempotent `stok_hareketi_kaydet()` ve kullanıcı izi |
| 004 | Uygulandı | İki seviyeli lokasyon hiyerarşisi, NUMUNE tipi ve ilgili view'lar |
| 005 | Uygulandı | `urun_kaydet()`, görsel sıra fonksiyonu ve ürün denetim alanları |
| 006 | Uygulandı | Tarihsel 30 test hareketinin koşullu temizliği |
| 007 | Uygulandı | Stok partisi için kaplama/montaj kovaları ve 11 kaplama rengi |
| 008 | Uygulandı (2026-08-05) | Ürün/SKU ayrımı, belge başlığı, stok durumu, parti, iş ortağı ve fason iş emri |
| 009 | Uygulandı (2026-08-05) | 13 standart renk ve 7 hammadde çeşidi başlangıç verisi |
| 010 | **Yazıldı, ortak DB'ye uygulanmadı** (2026-08-06) | SKU kimliğine lak/vernik/işçilik ikili nitelikleri, montaj hali `HAM` → `DEMONTE`, `ham` kaplamasının pasife alınması |
| 011 | **Yazıldı, ortak DB'ye uygulanmadı** (2026-08-06) | `stok_islemi_kaydet()`: iadelerde karşı taraf zorunlu ve rollü, amaç ↔ lokasyon tipi eşlemesi |

Migration 009 yalnız veri ekler (tablo/kolon/kısıt/view değiştirmez) ve 008'in
`renkler` tablosuna bağımlıdır, yani 008'den SONRA uygulanır. İleri yönü
`ON CONFLICT DO NOTHING` ile tekrar çalıştırılabilir. 2026-08-05'te stub tablolu
disposable bir veritabanında ileri + tekrar + rollback turu yapıldı; doğrulanan
üç davranış: (1) ikinci çalıştırma 0 satır ekliyor, (2) harf duyarsız
`uq_renkler_adi_ci` sayesinde önceden farklı yazımla girilmiş bir renk (`siyah`)
korunuyor ve rollback ona dokunmuyor, (3) rollback kullanıma girmiş (SKU'ya veya
ürüne bağlanmış) tohum satırlarını yerinde bırakıyor.

Şema otoritesi `../sql/01_schema.sql` ile `../sql/migrations/` altındaki sıralı
migration'ların birleşimidir. `01_schema.sql` yalnızca baz şemadır; Compose yeni
volume'de numaralı migration'ları otomatik çalıştırmaz.

Migration 006 yapısal bir adım değildir. Yalnız tam olarak 30 bilinen test
hareketini temizlemek için yazılmış ve bu önkoşulu denetleyen tarihsel bir veri
migration'ıdır. Fresh/boş kurulumda veya gerçek hareket içeren bir defterde
körlemesine uygulanmamalıdır.

Canlı yüzeyler `v_aktif_urunler`, stok/lokasyon/numune view'ları,
`stok_hareketi_kaydet()` ve `urun_kaydet()` fonksiyonlarıdır. Alanlar ve iş
kuralları `aktif-urun-veri-sozlesmesi.md` içinde belgelenir.

Migration 008 sonrası yüzeyler ve geçiş kuralları
[`stok-urun-veri-sozlesmesi.md`](stok-urun-veri-sozlesmesi.md) içindedir.

### 008 + 009'un ortak veritabanına uygulanması — 2026-08-05

Sıra şuydu: ortak veritabanının `pg_dump -Fc` yedeği alındı, **o yedekten**
kurulan tek kullanımlık kopyada tam tur çalıştırıldı, sonra Pi'ye uygulandı.
Disposable turda doğrulananlar:

- 008 ileri: 2.973 miras (BELIRSIZ) SKU açıldı, 9 hareketin tamamı SKU'ya ve
  belge başlığına bağlandı, sahipsiz satır kalmadı;
- `sql/tests/008_stok_urun_modeli_test.sql` (17 assertion) hatasız geçti — testin
  sessizce geçmediği, 008 uygulanmamış bir kopyada hata verdirilerek doğrulandı;
- 009 ileri (13 renk + 7 hammadde) ve 009 rollback;
- 008 rollback: nesneler düştü, 007'nin `stok_hareketi_kaydet` gövdesi geri geldi
  ve kopya özgün hâline (2.973 ürün / 9 hareket / 11 kaplama / 4 lokasyon) döndü.

Uygulama sonrası ortak veritabanında ölçülenler: ürün/hareket/kategori/lokasyon/
kaplama sayıları yedekle birebir aynı, SKU'suz ve belgesiz hareket sıfır, altı
yazma kapısının altısı da yerinde, ve defter neti ile `v_stok_bakiye` toplamı
eşit (2.022). Django arayüzü Pi'ye bağlanarak on iki sayfada denendi.

### 010 — SKU nitelik modeli, uygulama BEKLİYOR

010, SKU kimliğini kaplama + boya + mine + montaj hali dörtlüsünden yedi niteliğe
çıkarır: `lak_mi`, `vernik_mi`, `iscilik_mi` eklenir, boya ve mine rengi kontrollü
referans olarak korunur. Montaj hali `HAM` değeri `DEMONTE` olur — bu projede "ham"
kaplanmamış demektir ve aynı kelimenin iki anlamı karışıyordu. `kaplamalar`
tablosundaki `ham` satırı silinmez, pasife alınır.

`stok_kalemi_kaydet()` imzası değiştiği için `CREATE OR REPLACE` yerine 008'in
`stok_hareketi_kaydet` için kullandığı desen izleniyor: eski gövde
`stok_kalemi_kaydet_v008` adına RENAME edilip park ediliyor, yeni imza sıfırdan
yaratılıyor, rollback adı geri alıyor. Böylece eski gövde ne rollback dosyasına
kopyalanıyor ne de çağrılabilir bir aşırı yükleme olarak açıkta kalıyor.

Rollback bir güvenlik kapısı taşır: yalnız lak/vernik/işçilik farkıyla ayrılmış
`TANIMLI` SKU varsa en başta durur, çünkü kolonlar düşerse o SKU'lar aynı kimliğe
inerdi.

Uygulanmadan önce iki şey netleşmeli: (1) `web/` tarafındaki `HAM` sabitleri ve
`web/katalog/stok_servisi.py` içindeki altı parametreli `stok_kalemi_kaydet()`
çağrısı hizalanmalı; (2) hem yerel Docker hem Pi kopyasına uygulanmalı — ikisinin
şeması aynı, defterleri ayrı.

### 011 — stok işlemi kuralları, uygulama BEKLİYOR

011 `stok_islemi_kaydet()` gövdesine iki eksik iş kuralı ekler. İmza değişmediği
için `CREATE OR REPLACE` yeterlidir; rollback 008 gövdesini birebir geri yazar.

Birinci kural iadeleri alış/satışla aynı hizaya getirir: `MUSTERI_IADE` aktif
`MUSTERI` rollü, `TEDARIKCI_IADE` aktif `TEDARIKCI` rollü iş ortağı ister. Defter
etkileri 008'den beri doğrulanıyordu; eksik olan karşı tarafın kendisiydi.

İkinci kural amacı lokasyon tipine bağlar:

| Amaç | İzinli kaynak tipi | İzinli hedef tipi |
| --- | --- | --- |
| `SATIN_ALMA_KABUL` | — | `DAHILI` |
| `URETIM_GIRIS` | — | `DAHILI` |
| `MUSTERI_IADE` | — | `DAHILI` |
| `SATIS_SEVKI` | `DAHILI` | — |
| `TEDARIKCI_IADE` | `DAHILI` | — |
| `SAYIM` | — | `DAHILI`, `NUMUNE` |
| `IC_TRANSFER` | `DAHILI`, `NUMUNE` | `DAHILI`, `NUMUNE` |
| `DUZELTME` | kısıt yok | kısıt yok |
| `FASON_SEVK` / `FASON_DONUS` / `FIRE` | 008 kontrolleri | 008 kontrolleri |

`DUZELTME`'nin kısıtsız kalması karardır: fason lokasyonundaki bir hatanın da
düzeltilebilmesi gerekiyor. `STOK_SINIFLANDIRMA` ve `MIRAS_HAREKET` de kapsam
dışıdır. Kurallar yalnız yeni yazımlarda çalışır; backfill yoktur.

Sıradaki arayüz turu bu tabloyu aynalamalıdır — kural veritabanında olduğu için
Django'da kopyalanmaz, ama kullanıcıya seçenek olarak sunulmayan bir lokasyon
tipi hiç denenmemiş olur.

## Veri hattının sonucu

Güvenilir ana girdiler/çıktılar:

```text
data/raw/urun_listesi.xlsx
data/processed/temiz_urunler_final_v2.xlsx
data/reference/kalip_bilgileri_yedek.xlsx
images/final/products/
```

`temiz_urunler_final_v2.xlsx` 2.973 tekil ürünü içerir ve
`scripts/database/yukle.py` tarafından okunur. Canlı DB daha sonra arayüzden
değişebildiği için bu dosya tarihsel yükleme kaynağıdır; canlı DB'nin sürekli
güncel aynası değildir. Güncel tablo dökümü gerektiğinde
`scripts/database/tablolari_disa_aktar.py` kullanılmalıdır.

Karışık stok kodu aşamasında:

- 857 kaynak satır incelendi;
- 1.142 varyant otomatik çözüldü ve nihai veriye eklendi;
- 216 varyant elle inceleme/arşiv kapsamına ayrıldı;
- nihai kod, aile + token ayraçsız birleştirilerek üretildi.

Kuralın kanıtı ve istisnaları `karisik_stok_kodu_kurali.md` içindedir.

2026-07-28 kapsam kararıyla standartlaştırılmayan uzun kuyruk silinmedi, arşive
alındı:

- 216 çözülemeyen karışık varyant;
- 66 ölçü-karmaşık satır;
- 6 stoksuz satır;
- yeni stok kodlarıyla eşleşmeyen 934 görsel.

Ürün kayıtları `data/reference/arsivlenen_eski_urunler.xlsx`, görseller
`images/arsiv/products/` altındadır. Aktif görsel dizinindeki dosyalar DB ile
eşleşir; fotoğrafın doğru ürünü gösterdiği yalnız dosya adı ve dosya bütünlüğüyle
tam olarak kanıtlanamaz.

## Kalıcı kapsam ve mimari kararları

- `urunler` tasarım/model ana verisidir; stoklanan/sevk edilen kaplama, boya, mine
  ve montaj kombinasyonu `stok_kalemleri` içindeki SKU'dur.
- Kalıp göz sayısı `urunler` dışında, `kalip_bilgileri_yedek.xlsx` içinde Faz 3'ü
  bekler.
- Kaplama rengi, kontrollü boya/mine rengi ve montaj hali SKU niteliğidir. Askıda/
  dolap kaplama sevk edilen malı değiştirmiyorsa fason iş emri yöntemidir.
- Parti/lot SKU'nun belirli üretim veya kabul miktarını izler; SKU kodunun yerine
  geçmez ve yalnız ihtiyaç olan akışlarda kullanılır.
- Dışarıdaki METAKS malı ayrı veritabanına çıkmaz: FASON lokasyonunda, aynı stok
  defterinde ve `fason_is_emirleri` bağlantısıyla tutulur.
- Fiziksel lokasyon ile kullanılabilirlik bağımsızdır; stok durumu `SERBEST`,
  `KALITE_BEKLIYOR` veya `BLOKE` olur.
- Numune ayrı ürün değildir: ürünün `NUMUNE` tipindeki bir lokasyonda duran fiziksel
  adedidir; hareket geçmişi normal stok defterinden gelir.
- Migration 008 sonrasında `v_stok_urun_ozet`; sahip olunan, tesis içi, satışa
  hazır, fason, numune, kalite ve bloke toplamlarını ayrı verir. Eski
  `v_toplam_stok` bu ayrımların otoritesi değildir.
- Stok ve ürün iş kuralları Django'da kopyalanmaz; stok için
  `stok_islemi_kaydet()`, ürün için `urun_kaydet()` tek yazma kapısıdır.
- Görsel dosyasının fiziksel otoritesi `images/final/products/` dizinidir. Django
  yazar, nginx aynı dizini salt-okunur sunar, DB yalnız dosya adını tutar.
- Ham kaynak, nihai yükleme dosyası, kalıp yedeği ve aktif görsel dizini yedeksiz
  toplu değiştirilmez.

## Sıradaki işler

### Yakın dönem

0. Migration 010 + 011'i Django hizalamasıyla birlikte planlayıp ortak veritabanına
   uygulayın. Sıra bağlayıcıdır: 010 uygulanmadan varyant ekleme ekranı yeni
   nitelikleri gönderemez, Django hizalanmadan 010 uygulanırsa aynı ekran kırılır;
   011 de 010'un üstüne gelir. Arayüz turu 011'in amaç ↔ lokasyon tipi tablosunu
   aynalamalıdır. Uygulama hem yerel Docker hem Pi kopyasına yapılır.
1. Eski/belirsiz SKU bakiyesini ham varsaymadan fiziksel sayımla gerçek SKU'lara
   sınıflandırın. 008 ortak veritabanına uygulandığı için **2.973 ürünün tamamı
   şu an tek bir miras (BELIRSIZ) SKU taşıyor**; gerçek kaplama/montaj varyantları
   `/stok/varyant/yeni/` üzerinden açılıp bakiye oraya taşınmalı.
2. Gerçek numune dolabı ve raflarını `NUMUNE` hiyerarşisi olarak girin.
3. Arayüzde ürün detayına numune konumu/miktarı görünümünü ekleyin.

Üç maddenin de uygulama durumu `../../web/YAPILACAKLAR.md` tarafından izlenir.
Türkçe Excel uyumlu CSV/XLSX dışa aktarma (katalog, stok ve hareket geçmişi) ve
rol/işlem yetkisi ayrımı tamamlandı.

### Faz 3 — Kalıp modülü

- `kaliplar` tablosu ve ürün-kalıp ilişkisi;
- göz sayısı yedeğinin kontrollü aktarımı;
- kalıp durum/bakım geçmişi.

### Faz 6 — Barkod ve sipariş

- barkod üretme/okutma;
- müşteri, sipariş ve sipariş kalemleri;
- rezervasyon, kullanılabilir stok, kısmi hazırlama ve sevkiyat.

Bu faz depo ve ürün akışı yeterince oturmadan başlatılmayacaktır.

### Faz 7 — Üretim takibi

- sipariş kaleminden iş emri;
- aşama, makine, kalıp, operatör, sağlam/fire miktarı kayıtları;
- ilk sürümde basit pano/tablo, otomatik çizelgeleme yok.

Faz 7, kalıp modülünün temel varlıklarına bağımlıdır.

### Operasyonel sağlamlaştırma

- fresh kurulumda baz şema + gerekli veri yükleme + migration sırasını otomatik ve
  tekrar üretilebilir hâle getirin;
- büyüyen stok defterinde sorgu planlarını ölçüp yalnız ihtiyaç varsa indeks ekleyin;
- günlük yedek zamanlaması ve ayrı fiziksel hedef kurun, geri yüklemeyi düzenli
  doğrulayın;
- eksik ürün görselleri, hammadde ve ağırlık verisini yeni güvenilir kaynak
  bulunduğunda tamamlayın.
