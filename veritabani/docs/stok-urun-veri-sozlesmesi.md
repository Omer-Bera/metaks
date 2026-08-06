# Stok ve ürün veri sözleşmesi (migration 008 + 010 + 011)

Bu sözleşme migration 008 uygulandıktan sonraki ürün/SKU, belge ve fason yüzeylerini
tanımlar. Migration ortak veritabanına uygulanana kadar canlı şema 007 sözleşmesindedir.

**SKU kimliği migration 010 ile, yazma kapısının kuralları 011 ile değişti.** İkisi de
yazıldı ama ortak veritabanına uygulanmadı; aşağıdaki tanımlar uygulandıktan sonrası
içindir. Django tarafı 010 ve 011'e hizalandı — yani bu kod 010 uygulanmamış bir
veritabanına bağlanırsa stok ekranları hata verir, ikisi birlikte dağıtılmalıdır.

## Kimlikler

- `urunler.stok_kodu`: tasarım/model düzeyindeki tarihsel ürün kodudur.
- `stok_kalemleri.sku_kodu`: kaplama, boya rengi, mine rengi, montaj hali, lak, vernik
  ve işçilik nitelikleri aynı olan, birbirinin yerine sevk edilebilir stok kalemidir.
  Bu yedi nitelik `uq_stok_kalemleri_nitelik` kısmi tekillik indeksinin anahtarıdır.
- Lak, vernik ve işçilik **ikilidir** (`lak_mi`, `vernik_mi`, `iscilik_mi` BOOLEAN).
  Boya ve mine rengi ikiliye indirilmez; `renkler` tablosuna bakan kontrollü
  referans olarak kalır.
- Montaj hali `BELIRSIZ`, `DEMONTE`, `YARI_MONTE` veya `MONTE` olur. 008'in `HAM`
  değeri 010'da `DEMONTE` oldu: bu projede **"ham" kaplanmamış demektir**
  (`kaplamalar` tablosundaki satır), montaj hali değil. Aynı kelimeyi iki anlamda
  kullanmak hem ekranda hem SQL'de karışıyordu.
- Her ürüne migration sırasında aynı kodlu `BELIRSIZ` miras SKU açılır. Bu SKU
  kaplanmamış kabul edilmez; fiziksel sayımda gerçek `-V01`, `-V02` SKU'larına
  sınıflandırılır.
- `stok_partileri`: gerektiğinde SKU içindeki üretim/kabul lotunu ayırır; ürün veya
  SKU kodunun yerine geçmez.

### `BELIRSIZ` satırlarda nitelik değerleri bilgi değildir

Tekillik indeksi yalnız `nitelik_durumu = 'TANIMLI'` satırlarda çalışır, yani miras
SKU'ların nitelikleri kimliğe girmez. Bunun okuma tarafındaki sonucu:

- `kaplama_id`, `boya_renk_id`, `mine_renk_id` bu satırlarda `NULL`'dır — "kaplamasız"
  değil, **bilinmiyor**;
- `lak_mi`, `vernik_mi`, `iscilik_mi` bu satırlarda `FALSE`'tır ama bu yalnızca kolon
  varsayılanıdır — "laksız/verniksiz/işçiliksiz" değil, **bilinmiyor**.

Bu `FALSE`'ı "laksız" diye okuyan bir filtre miras SKU'lar hakkında yalan söyler.
Uyarı kolon yorumlarında da (`COMMENT ON COLUMN`) durur.

### `stok_kalemi_kaydet()` imzası

010 imzaya üç BOOLEAN parametre ekledi ve **varsayılan vermedi**:

```text
stok_kalemi_kaydet(
    p_urun_kodu, p_kaplama_id, p_boya_renk, p_mine_renk, p_montaj_durumu,
    p_lak_mi, p_vernik_mi, p_iscilik_mi, p_yapan_kullanici
)
```

Varsayılan olmaması bilinçlidir: varsayılan verilseydi güncellenmemiş bir çağrı
sessizce "laksız" kaydederdi. Üçünden biri `NULL` gelirse fonksiyon hata verir —
`TANIMLI` bir SKU belirsiz nitelik taşımaz. Fonksiyonun idempotent davranışı
(mevcut kombinasyon için `atlandi = TRUE` ile aynı SKU'yu döndürmek) korunur;
fason iş emri akışı hedef SKU'yu buna dayanarak türetir.

`kaplamalar` tablosundaki `ham` satırı 010'da `aktif_mi = FALSE` oldu (silinmedi;
FK'lar `ON DELETE RESTRICT` ve proje soft-delete kullanıyor). Yeni SKU'larda
kullanılamaz; kaplanmamış hâl `kaplama_id IS NULL` ile ifade edilir.

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

### 011'in eklediği iki kural ailesi

Karşı taraf zorunluluğu (rol `is_ortagi_rolleri`'nden, iş ortağı aktif olmalı):

| İşlem nedeni | Gereken rol |
| --- | --- |
| `SATIN_ALMA_KABUL` | `TEDARIKCI` |
| `SATIS_SEVKI` | `MUSTERI` |
| `MUSTERI_IADE` | `MUSTERI` |
| `TEDARIKCI_IADE` | `TEDARIKCI` |

İşlem nedeni ↔ lokasyon tipi:

| İşlem nedeni | İzinli kaynak | İzinli hedef |
| --- | --- | --- |
| `SATIN_ALMA_KABUL`, `URETIM_GIRIS`, `MUSTERI_IADE` | — | `DAHILI` |
| `SATIS_SEVKI`, `TEDARIKCI_IADE` | `DAHILI` | — |
| `SAYIM` | — | `DAHILI`, `NUMUNE` |
| `IC_TRANSFER` | `DAHILI`, `NUMUNE` | `DAHILI`, `NUMUNE` |
| `DUZELTME`, `STOK_SINIFLANDIRMA`, `MIRAS_HAREKET` | kısıt yok | kısıt yok |
| `FASON_SEVK`, `FASON_DONUS`, `FIRE` | 008'in iş emri kuralları | 008'in iş emri kuralları |

`DUZELTME`'nin kısıtsız kalması bilinçlidir: fason lokasyonundaki bir hatanın da
düzeltilebilmesi gerekiyor ve düzeltme oradan çıkışın tek yoludur. Arayüz bu
tabloları POST'tan önce gösterir ama otorite bu fonksiyondur; kural Python veya
JavaScript'te ikinci kez tanımlanmaz.

Eski `stok_hareketi_kaydet()` imzası uyumluluk sarmalayıcısıdır; o da yeni kapıya
yönlenir. Yeni Django kodu bu sarmalayıcıyı kullanmaz. 010, sarmalayıcının içindeki
montaj eşleştirmesini de `HAM` yerine `DEMONTE` yaptı; imza değişmedi.

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

sql/migrations/010_sku_nitelikleri.sql
sql/tests/010_sku_nitelikleri_test.sql
sql/migrations/010_sku_nitelikleri_rollback.sql

sql/migrations/011_stok_islemi_kurallari.sql
sql/tests/011_stok_islemi_kurallari_test.sql
sql/migrations/011_stok_islemi_kurallari_rollback.sql
```

011'in kabul testi hedef SKU'yu 010'un dokuz parametreli imzasıyla açar; yani 011
tek başına 008 seviyesindeki bir kopyada test edilemez, tur her zaman
`010 ileri → 011 ileri → test → 011 rollback → 010 rollback` sırasındadır.

Kabul testi yalnız disposable/restored kopyada çalıştırılır ve kendi örnek
hareketlerini transaction sonunda geri alır. Ortak veritabanına uygulama için güncel
yedek ve açık kullanıcı onayı zorunludur.

008 kabul testi hem eski 6 parametreli `stok_kalemi_kaydet()` imzasını hem `HAM`
değerini kullanır; 010 uygulanmış bir kopyada beklendiği gibi hata verir. 010 sonrası
kabul testi `sql/tests/010_sku_nitelikleri_test.sql` dosyasıdır.

010'un rollback'i, yalnız lak/vernik/işçilik farkıyla ayrılmış `TANIMLI` SKU varsa en
başta durur: o kolonlar düşerse iki ayrı SKU aynı kimliğe inerdi. Böyle bir durumda
önce varyantlar elle birleştirilir veya pasife alınır.
