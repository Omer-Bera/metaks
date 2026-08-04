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
uygulanmış durumda.

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

- `urunler` yalnız ürünün kimlik/fiziksel ana verisini taşır; üretim ve stok
  partisi özellikleri ayrı tutulur.
- Kalıp göz sayısı `urunler` dışında, `kalip_bilgileri_yedek.xlsx` içinde Faz 3'ü
  bekler.
- Kaplama rengi, kaplama yöntemi ve montaj durumu stok partisinin özelliğidir.
  Kova anahtarı `kaplama_id + kaplama_cesidi + montaj` üçlüsüdür.
- `boya` ve `mine` serbest metindir; yazım farkları sahte stok kovaları açmasın
  diye kova anahtarına dahil edilmez.
- Numune ayrı ürün değildir: ürünün `NUMUNE` tipindeki bir lokasyonda duran fiziksel
  adedidir; hareket geçmişi normal stok defterinden gelir.
- `v_toplam_stok` satılabilir stoğu, `v_fiziksel_stok` numuneler dahil fiziksel
  stoğu gösterir.
- Stok ve ürün iş kuralları Django'da kopyalanmaz; iki veritabanı fonksiyonu tek
  yazma kapısıdır.
- Görsel dosyasının fiziksel otoritesi `images/final/products/` dizinidir. Django
  yazar, nginx aynı dizini salt-okunur sunar, DB yalnız dosya adını tutar.
- Ham kaynak, nihai yükleme dosyası, kalıp yedeği ve aktif görsel dizini yedeksiz
  toplu değiştirilmez.

## Sıradaki işler

### Yakın dönem

1. Gerçek numune dolabı ve raflarını `NUMUNE` hiyerarşisi olarak girin.
2. Arayüzde ürün detayına numune konumu/miktarı görünümünü ekleyin.
3. Hareket geçmişi için Türkçe Excel ile uyumlu CSV/Excel dışa aktarmayı ekleyin.
4. Dış/fason kullanıcı ihtiyacı doğduğunda rol ve işlem yetkilerini ayırın.

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
