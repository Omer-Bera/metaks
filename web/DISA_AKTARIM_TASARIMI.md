# Katalog, stok ve hareket dışa aktarımı

Bu belge, ürün kataloğu, stok durumu ve stok hareketleri ekranlarına eklenecek
CSV ve Excel dışa aktarım özelliğinin kullanım amacını ve teknik yönünü tanımlar.

## Neden gerekli?

Personel günlük işlerinde Excel'e alışkın olduğu için ekrandaki veriyi dosya olarak
alabilmek pratik bir ihtiyaçtır. Dışa aktarım özellikle şu işlerde kullanılabilir:

- filtrelenmiş stok listesini yöneticisiyle paylaşmak,
- sayım veya sipariş hazırlığı yapmak,
- hareket geçmişini tarih aralığıyla arşivlemek,
- katalog verisini başka bir Excel çalışmasına aktarmak,
- Excel üzerinde not, sınıflandırma veya ek hesaplama yapmak.

Bu nedenle özellik yalnızca teknik bir kolaylık değil, ekran ile günlük operasyon
arasında bir köprü olarak değerlendirilmelidir.

## Kullanıcı deneyimi

Üç sayfada da filtre özetinin yanında aynı adla bir **Dışa aktar** eylemi bulunur.
Eylem iki seçenek sunar:

- **Excel dosyası (.xlsx)**
- **CSV dosyası (.csv)**

Dosya, o anda seçili olan filtrelerin tamamını kullanır. Katalog ve stok
ekranlarındaki sayfalama veya hareketler ekranındaki sonsuz kaydırma dışa aktarımı
sınırlamaz; kullanıcı ekranda görünen ilk sayfayı değil, filtreye uyan kayıtların
tamamını indirir.

Dosya adları tarih içermelidir. Örnekler:

```text
stok-durumu-2026-08-04.xlsx
stok-hareketleri-2026-08-01_2026-08-04.csv
```

Uygulanan filtrelerin dosya adında taşınması zorunlu değildir; ancak dosyanın ilk
satırında veya çalışma sayfası üst bilgisinde kapsamın anlaşılır olması faydalıdır.

## Dışa aktarılacak alanlar

### Ürün kataloğu

- Stok kodu
- Kategori
- Açıklama
- Ürünü tanımlayan diğer mevcut özellikler
- Gerekiyorsa görsel URL'si

### Stok durumu

- Stok kodu
- Kategori
- Toplam stok
- Stok durumu: `Sayılmadı`, `Stok yok` veya `Stok var`
- İhtiyaç netleştiğinde stok kovası kırılımı

`v_toplam_stok` sözleşmesindeki “satır yok” ile “miktar sıfır” ayrımı korunmalıdır;
ikisi dosyada aynı boş değer olarak gösterilmemelidir.

### Stok hareketleri

- Tarih ve saat
- Stok kodu
- Kategori
- İşlem tipi
- Miktar
- Nereden
- Nereye
- Yapan kullanıcı
- Açıklama

Hareket tarihi `yerel_tarih()` üzerinden Europe/Istanbul saatinde yazılmalıdır.
Ham naive UTC kolonu doğrudan dışa aktarılırsa özellikle gün başlangıcı ve bitişinde
üç saatlik kayma oluşabilir.

## Dosya biçimi kuralları

### CSV

CSV, `;` ayraçlı ve UTF-8 BOM'lu üretilmelidir. Bu kombinasyon Türkçe Windows/Excel
kurulumlarında hem `Ç, Ğ, İ, Ö, Ş, Ü` karakterlerinin hem de sütun ayrımının doğru
çalışması için en uyumlu başlangıç noktasıdır.

Metin alanları Excel tarafından formül olarak yorumlanmamalıdır. `=`, `+`, `-` veya
`@` ile başlayan stok kodu, açıklama ya da kullanıcı adı gibi değerler güvenli bir
şekilde yazılmalıdır; bu, dışa aktarılan dosyanın formül enjeksiyonu riskini azaltır.

### Excel

XLSX dosyasında mümkün olduğunca gerçek veri tipleri korunmalıdır:

- tarih ve saatler Excel tarih hücresi,
- miktarlar sayısal hücre,
- başında sıfır bulunan stok kodları metin hücresi olmalıdır.

Başlık satırının sabitlenmesi, Excel filtresinin etkinleştirilmesi ve sütun
genişliklerinin okunabilir ayarlanması personel kullanımını kolaylaştırır. İlk
sürümde görselleri dosyanın içine gömmek gerekli değildir; görsel URL'si yeterlidir.

## Uygulama yaklaşımı

HTML liste ile dışa aktarım aynı filtreleme altyapısını kullanmalıdır. Özellikle
arama, kategori, “sadece stokta olanlar”, işlem tipi, lokasyon, kullanıcı ve tarih
aralığı iki ayrı yerde kopyalanmamalıdır. Böylece ekranda görünen kayıt kümesi ile
indirilen kayıt kümesinin farklılaşması önlenir.

Önerilen geliştirme sırası:

1. Üç sayfada ortak dışa aktarım eylemi ve URL parametrelerinin korunması.
2. CSV çıktısı: standart kütüphane, `StreamingHttpResponse`, UTF-8 BOM ve `;`.
3. XLSX çıktısı: `openpyxl` ile biçimlendirilmiş çalışma sayfası.
4. Filtre ve tarih sınırları için güvenli test verisiyle doğrulama.

Katalog ve stok için normal sorgu yanıtı yeterli olabilir; hareket geçmişi
büyüdüğünde tüm veri kümesini bellekte biriktirmemek için hem CSV hem de mümkünse
XLSX üretiminde akış/bellek sınırı ayrıca değerlendirilmelidir.

## Yetki ve güvenlik

Katalog, stok ve hareket geçmişi bugün anonim salt-okunur erişime açıktır. Dışa
aktarımda ise hareket geçmişi personel adı ve işlem bilgisi içerdiği için en azından
giriş yapmış kullanıcı şartı ayrıca değerlendirilmelidir. İnce rol ayrımı gelene
kadar kapsam şu şekilde netleştirilmelidir:

- katalog dışa aktarımı: katalog görüntüleme yetkisi,
- stok dışa aktarımı: stok görüntüleme yetkisi,
- hareket dışa aktarımı: hareket geçmişi ve personel bilgisi erişimi.

Bu yetki kararı uygulanmadan önce anonim ekran davranışını sessizce değiştirmemek,
ayrı bir karar olarak ele almak gerekir.

## Kabul ölçütleri

- Ekrandaki filtrelerle dosyadaki kayıt kümesi birebir aynıdır.
- Dışa aktarım sayfalama ile sınırlanmaz.
- Türkçe karakterler gerçek Excel'de doğru görünür.
- CSV sütunları Türkçe Excel'de doğru ayrılır.
- Tarihler Europe/Istanbul saatinde ve gün sınırları doğru yazılır.
- Başında sıfır bulunan stok kodları korunur.
- Filtre yokken ve sonuç boşken de geçerli başlık satırına sahip dosya üretilir.
- Büyük sonuç kümeleri gereksiz şekilde tamamen belleğe alınmaz.

