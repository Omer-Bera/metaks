# METAKS veritabanı — durum ve yol haritası

Bu belge veri/pipeline/şema tarafında “nerede kaldık, sırada ne var?” sorusunun
cevabıdır. Çalıştırma kuralları `../AGENTS.md`, arayüzün bağlayıcı veri sözleşmesi
`aktif-urun-veri-sozlesmesi.md`, ekran işleri ise `../../web/YAPILACAKLAR.md`
içindedir.

Canlı satır sayıları kalıcı gerçekler değildir. Aşağıdaki sayılar
**2026-08-04 tarihli salt-okunur denetim snapshot'ıdır**; karar vermeden önce
yeniden sorgulanmalıdır.

## Güncel çalışma noktası — 2026-08-04

Veri temizleme, normalizasyon, karışık stok kodu çözümü, PostgreSQL yüklemesi ve
görsel eşleme tamamlandı. Migration 001–007 ortak `depo_sistemi` veritabanına
uygulanmış durumda. Migration 008 kodu ve kabul testi hazırdır; **ortak veritabanına
uygulanmamıştır**, güncel yedek ve kullanıcı onayı bekler.

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
| Hammadde | 0 |
| Kaplama rengi | 11 |
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
| 008 | Çekirdek kabul testi geçti; son disposable turu ve onay bekliyor | Ürün/SKU ayrımı, belge başlığı, stok durumu, parti, iş ortağı ve fason iş emri |

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
[`stok-urun-veri-sozlesmesi.md`](stok-urun-veri-sozlesmesi.md) içindedir. 008;
2026-08-04'te `depo_sistemi` dump'ından oluşturulan `metaks_m008_test` disposable
veritabanında ileri migration ve `sql/tests/008_stok_urun_modeli_test.sql` ile
çekirdek satın alma, satış, transfer, fason sevk/dönüş, sayım, idempotency ve
toplam mutabakatı senaryolarında doğrulandı. Bu turun ardından eklenen parti,
fason fire ve 007 fonksiyon gövdesini geri yükleyen rollback korumaları için yeni
restore edilmiş disposable kopyada forward + kabul + rollback turu henüz
tekrarlanmadı. Ortak veritabanında hiçbir şema/veri değişikliği yapılmadı.

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

1. Ortak veritabanının güncel yedeğini alın; migration 008 forward + rollback'i
   yeni restore edilmiş kopyada son kez çalıştırın ve açık kullanıcı onayıyla uygulayın.
2. Eski/belirsiz SKU bakiyesini ham varsaymadan fiziksel sayımla gerçek SKU'lara
   sınıflandırın.
3. Gerçek numune dolabı ve raflarını `NUMUNE` hiyerarşisi olarak girin.
4. Hareket geçmişi için Türkçe Excel ile uyumlu CSV/Excel dışa aktarmayı ekleyin.

İkinci, üçüncü ve dördüncü maddelerin uygulama durumu
`../../web/YAPILACAKLAR.md` tarafından izlenir.

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
