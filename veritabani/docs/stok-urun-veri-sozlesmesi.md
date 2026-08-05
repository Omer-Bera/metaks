# Stok ve ürün veri sözleşmesi (migration 008)

Bu sözleşme migration 008 uygulandıktan sonraki ürün/SKU, belge ve fason yüzeylerini
tanımlar. Migration ortak veritabanına uygulanana kadar canlı şema 007 sözleşmesindedir.

## Kimlikler

- `urunler.stok_kodu`: tasarım/model düzeyindeki tarihsel ürün kodudur.
- `stok_kalemleri.sku_kodu`: kaplama, boya, mine ve montaj hali aynı olan, birbirinin
  yerine sevk edilebilir stok kalemidir.
- Her ürüne migration sırasında aynı kodlu `BELIRSIZ` miras SKU açılır. Bu SKU ham
  kabul edilmez; fiziksel sayımda gerçek `-V01`, `-V02` SKU'larına sınıflandırılır.
- `stok_partileri`: gerektiğinde SKU içindeki üretim/kabul lotunu ayırır; ürün veya
  SKU kodunun yerine geçmez.

## Yazma kapısı

Yeni kayıtların tek kapısı `stok_islemi_kaydet(...)` fonksiyonudur. Başlık; işlem
nedeni, karşı taraf, belge numarası, fason iş emri, düzeltme bağlantısı, açıklama ve
kullanıcıyı taşır. `p_satirlar` bir JSON dizisidir:

```json
{
  "stok_kalemi_id": 123,
  "islem_tipi": "TRANSFER",
  "miktar": 10,
  "kaynak_lokasyon_id": 8,
  "hedef_lokasyon_id": 10,
  "stok_durumu_kodu": "SERBEST",
  "parti_no": "2026-08-A"
}
```

Fonksiyon amaç/teknik etki uyumunu, yaprak lokasyonu, yeterli ayrıntılı bakiyeyi,
partiyi, iş emri sınırını, belge tekilliğini ve istemci UUID idempotency'sini aynı
transaction içinde denetler. Kaydedilmiş `stok_hareketleri` satırı UPDATE/DELETE
edilemez. Düzeltme yeni belge olarak ve düzelttiği belgeye bağlantıyla yazılır.

Eski `stok_hareketi_kaydet()` imzası uyumluluk sarmalayıcısıdır; o da yeni kapıya
yönlenir. Yeni Django kodu bu sarmalayıcıyı kullanmaz.

## Okuma yüzeyleri

- `v_stok_bakiye`: SKU × lokasyon × stok durumu × parti net bakiyesi.
- `v_stok_urun_ozet`: ürün başına sahip olunan, tesis içi, satışa hazır, fasonda,
  numunede, kalite bekleyen ve bloke toplamları.
- `v_fason_is_emri_ozet`: planlanan, gönderilen, dönen, fire, fasondaki ve açık
  miktarlar. Gerçekleşen miktarlar ayrı sayaçlardan değil defterden türetilir.

`satisa_hazir_toplam`, yalnız `DAHILI + SERBEST + satilabilir_mi` bakiyedir. Fason ve
numune şirket mülkiyetinde olduğu için `sahip_olunan_toplam` içindedir; satışa hazır
toplama girmez.

## Geçiş doğrulaması

Migration ve kabul testi sırasıyla:

```text
sql/migrations/008_stok_urun_modeli.sql
sql/tests/008_stok_urun_modeli_test.sql
sql/migrations/008_stok_urun_modeli_rollback.sql
```

Kabul testi yalnız disposable/restored kopyada çalıştırılır ve kendi örnek
hareketlerini transaction sonunda geri alır. Ortak veritabanına uygulama için güncel
yedek ve açık kullanıcı onayı zorunludur.
