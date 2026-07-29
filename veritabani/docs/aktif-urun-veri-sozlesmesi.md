# Aktif Ürün Veri Sözleşmesi

Appsmith Ürünler/Katalog sayfasının kullanacağı veri sözleşmesi. Bu belge inceleme +
migration hazırlığı aşamasının çıktısıdır — **migration'lar henüz ortak veritabanına
uygulanmadı**, kullanıcı onayı bekliyor (bkz. "Migration sırası").

## Aktif ürün kriterleri

Bir `urunler` satırı **AKTİF** kabul edilir ancak ve ancak:

1. `urun_gorselleri` tablosunda bu `stok_kodu` için `ana_gorsel_mi = TRUE AND aktif_mi = TRUE`
   olan bir kayıt varsa, **ve**
2. O görsel dosyası diskte gerçekten mevcutsa ve yapısal olarak bozuk değilse (Pillow
   `Image.verify()` ile açılabiliyorsa).

Bunun dışındaki her şey **PASİF**. Üçüncü bir durum olan **İNCELEME_BEKLİYOR** şemada
mevcut ama şu anki veri setinde otomatik olarak hiçbir satıra atanmıyor — aşağıdaki
"Bilinen sınırlamalar" bölümüne bakın.

Zaten arşivlenmiş kayıtlar (çözülemeyen karışık kodlar, ölçü-karmaşık satırlar,
stoksuz satırlar — `data/reference/arsivlenen_eski_urunler.xlsx`) bu değerlendirmeye
hiç girmiyor çünkü **`urunler` tablosuna hiç yüklenmediler**; bu sözleşme sadece
tablodaki 2.973 satırı kapsıyor.

### Doğrulama şu anda gerçekte ne ölçüyor (önemli)

"Görsel doğrulama" bugüne kadar sadece şunu test etti: OOXML çizim anchor'larından
çıkarılan dosya adının bir `stok_kodu`'na eşleşmesi (`gorsel_esle_duzeltilmis_v2.py`)
+ bu inceleme sırasında eklenen yapısal bütünlük kontrolü (dosyanın gerçekten açılabilir
bir görsel olması). **Fotoğrafın görsel olarak doğru/net/doğru ürünle eşleşmiş olduğunu
otomatik olarak doğrulamıyor** — bu, insan gözüyle bakmayı gerektirir. 1.799 eşleşen
görselin tamamı bu inceleme sırasında `Image.verify()` ile test edildi, **0 bozuk dosya
bulundu**. Dosya boyutuna göre "bozuk" filtrelemesi denendi ama yanlış pozitif verdiği
için (küçük dosyalar genelde gerçekten küçük/basit ürün fotoğrafları — bkz. 100012
örneği, 2.142 byte, gayet net bir görsel) terk edildi.

## Kullanılacak tablolar, view'lar ve fonksiyonlar

| Nesne | Tür | Amaç |
|---|---|---|
| `urunler.katalog_durumu` | yeni kolon | `'AKTIF' \| 'PASIF' \| 'INCELEME_BEKLIYOR'` |
| `urunler.aktif_mi` | mevcut kolon | değişmedi; `katalog_durumu='AKTIF'` ile her zaman tutarlı (CHECK constraint) |
| `v_aktif_urunler` | yeni view | Appsmith'in **tek** okuma kaynağı — sadece aktif ürünler, kategori/hammadde/kaplama/ana görsel join'li |
| `v_lokasyon_stok_ozet` | yeni view | ürün × lokasyon bazında net miktar |
| `v_toplam_stok` | yeni view | ürün başına tüm lokasyonlar toplamı |

`urunler`/`urun_gorselleri`/`kategoriler`/`hammaddeler`/`kaplamalar` şemasında hiçbir
değişiklik yok, sadece `katalog_durumu` kolonu eklendi. `stok_hareketleri`/`lokasyonlar`
şemasında hiç değişiklik yok — sadece üzerlerine view eklendi.

## Appsmith sorgularında kullanılacak alan adları

`v_aktif_urunler`: `stok_kodu`, `urun_tipi`, `parent_stok_kodu`, `varyant_adi`,
`olcu_mm`, `boy_ligne`, `boya_mine`, `gramaj_gr`, `montaj_durumu`, `aciklama`,
`kritik_stok_esigi`, `kategori_id`, `kategori_adi`, `hammadde_id`, `hammadde_adi`,
`kaplama_id`, `kaplama_adi`, `ana_gorsel_dosya_adi`, `arama_metni`.

`arama_metni`: stok_kodu + kategori_adi + hammadde_adi + kaplama_adi + aciklama'nın
küçük harfe çevrilip birleştirilmiş hali — tek bir `ILIKE '%...%'` ile hepsini aramak
için (bkz. `csv_guncelle.py`'deki `arama_metni_olustur()` ile aynı yaklaşım).

`v_lokasyon_stok_ozet`: `stok_kodu`, `lokasyon_id`, `lokasyon_adi`, `lokasyon_tipi`,
`mevcut_miktar`. `v_toplam_stok`: `stok_kodu`, `toplam_miktar`.

## Boş değer davranışları

- `hammadde_id`/`kaplama_id` → `NULL` (bu tablolar şu an **tamamen boş**, 0 satır;
  hiçbir üründe hammadde/kaplama ataması yapılmamış). `v_aktif_urunler.hammadde_adi`/
  `kaplama_adi` bu yüzden şu an **her satırda NULL** dönecek. Appsmith arayüzünde bu
  filtreler şimdilik boş görünecek — kod hatası değil, veri henüz girilmemiş.
- `ana_gorsel_dosya_adi` → tanım gereği `v_aktif_urunler`'da hiçbir zaman NULL olamaz
  (view zaten aktif görseli olan satırları filtreliyor).
- `aciklama`, `varyant_adi`, `boya_mine`, `montaj_durumu`, `gramaj_gr`, `boy_ligne` →
  kaynak veride zaten kısmen boş, NULL olabilir; `arama_metni` bunları `coalesce(...,'')`
  ile boş string'e çeviriyor, arama sorgusu NULL'dan etkilenmiyor.
- `v_lokasyon_stok_ozet` / `v_toplam_stok` → **şu an 0 satır** (aşağıya bakın).

## Stok hesaplama yöntemi

`stok_hareketleri` ve `lokasyonlar` şu an **boş** (Faz 4 yükleyici script'i henüz
yazılmadı — `CLAUDE.md`'de belgelenmiş bilinen durum). View'lar bugün 0 satır dönüyor;
bu beklenen bir durumdur, hata değildir.

Kabul edilen işaret kuralı (varsayım — Faz 4 yükleyicisi bu kuralla tutarlı veri
üretmeli):

- `hedef_lokasyon_id` dolu → `+miktar` (GİRİŞ, TRANSFER'in varış ucu, SAYIM_DEVRİ açılış bakiyesi)
- `kaynak_lokasyon_id` dolu → `-miktar` (ÇIKIŞ, TRANSFER'in çıkış ucu)
- DÜZELTME: azaltma → kaynak_lokasyon_id dolu + pozitif miktar (ÇIKIŞ gibi); artırma → hedef_lokasyon_id dolu + pozitif miktar (GİRİŞ gibi)

Bir lokasyondaki net miktar = o lokasyonun hedef olduğu hareketlerin toplamı eksi
kaynak olduğu hareketlerin toplamı. Bu varsayım Faz 4 yükleyicisi yazılırken kullanıcıyla
teyit edilmeli.

## Örnek parametreli sorgular

Stok kodu/kategori/açıklama arayan canlı arama (Appsmith Input1'e bağlı, "Run query
automatically" açık):

```sql
SELECT stok_kodu, kategori_adi, hammadde_adi, kaplama_adi, olcu_mm,
       aciklama, ana_gorsel_dosya_adi
FROM v_aktif_urunler
WHERE arama_metni ILIKE '%' || lower({{ Input1.text }}) || '%'
ORDER BY stok_kodu
LIMIT 50;
```

Sadece stok kodu öneki (hızlı, PK indeksini kullanır):

```sql
SELECT * FROM v_aktif_urunler
WHERE stok_kodu ILIKE {{ Input1.text }} || '%'
ORDER BY stok_kodu
LIMIT 50;
```

Bir ürünün lokasyon bazlı stok dökümü:

```sql
SELECT lokasyon_adi, lokasyon_tipi, mevcut_miktar
FROM v_lokasyon_stok_ozet
WHERE stok_kodu = {{ Table1.selectedRow.stok_kodu }}
ORDER BY lokasyon_adi;
```

## İndeksler

| İndeks | Tablo | Neden |
|---|---|---|
| `idx_urunler_katalog_durumu` | `urunler(katalog_durumu)` | admin/inceleme ekranı filtreleri |
| `idx_urunler_aciklama_trgm` | `urunler USING GIN (aciklama gin_trgm_ops)` | `aciklama` içinde "içerir" araması (`pg_trgm`) |

`idx_urunler_aktif` (mevcut) zaten `v_aktif_urunler`'ın ana filtresini karşılıyor —
tekrar oluşturulmadı. `stok_kodu` önek araması birincil anahtar indeksini kullanıyor —
ayrı indekse gerek yok. `kategori_adi`/`hammadde_adi`/`kaplama_adi` küçük lookup
tablolarında (35/0/0 satır) — bu ölçekte indekssiz join zaten anlık, gereksiz indeks
eklenmedi.

## Migration sırası

1. **Onay bekleniyor** — `sql/migrations/001_katalog_durumu.sql` (kolon + backfill + indeks + `pg_trgm` + `v_aktif_urunler`)
2. **Onay bekleniyor** — `sql/migrations/002_lokasyon_stok_view.sql` (sadece view, mevcut tabloları değiştirmez)

İkisi de `BEGIN`/`COMMIT` içinde, tek transaction, hata olursa otomatik geri alınır.
Her biri için ayrı bir `_rollback.sql` dosyası var. Uygulanmadan önce hangi sırayla
çalıştırılacağı konusunda bağımlılık yok — 002, 001'e bağımlı değil (ayrı tablolar).

## Test sonuçları

Canlı veritabanına karşı **salt-okunur** olarak doğrulandı (hiçbir satır değiştirilmedi):

| Ölçüt | Migration öncesi | Migration sonrası (beklenen) |
|---|---|---|
| Toplam ürün | 2.973 | 2.973 (değişmez) |
| Aktif olacak | — (`aktif_mi` hepsinde `TRUE`, hiç kullanılmıyordu) | 1.780 |
| Pasif olacak | — | 1.193 |
| Mükerrer `stok_kodu` | 0 (birincil anahtar zaten garanti ediyor) | 0 |
| `v_aktif_urunler` sorgu testi | — | 1.780 satır döndü (beklenenle birebir eşleşti) |
| `v_lokasyon_stok_ozet` sözdizimi testi | — | 0 satır (beklenen — `stok_hareketleri` boş) |
| Görsel bütünlük taraması (Pillow, 1.799 dosya) | — | 0 bozuk dosya |

Ürün tipi kırılımı (aktif ürünlerin urun_tipi dağılımı):

| urun_tipi | toplam | görselli (aktif olacak) |
|---|---|---|
| ANA_URUN | 2.968 | 1.776 |
| ALT_PARCA | 3 | 2 |
| VARYANT | 2 | 2 |

## Bilinen sınırlamalar

- **İçerik doğrulaması yok**: bir görselin *doğru ürünü* gösterdiği otomatik olarak
  doğrulanamıyor, sadece dosya adı eşleşmesi + yapısal bütünlük kontrol ediliyor.
  Yanlış ürünle eşleşmiş ama yapısal olarak sağlam bir görsel varsa, bu sözleşme onu
  yakalayamaz — insan gözüyle örnekleme/denetim gerekir.
- **INCELEME_BEKLIYOR şu an boş**: mevcut veri setinde otomatik olarak "belirsiz" diye
  işaretlenebilecek bir grup yok (arşivlenmesi gerekenler zaten `urunler` tablosuna hiç
  girmedi). Şema üçüncü durumu destekliyor ama ilk yüklemede hiçbir satır bu durumda değil.
- **Çoklu görselli 19 ürün**: birden fazla görseli olan ürünlerde birincil (ana) görsel
  dosya adındaki sıra numarasına göre otomatik seçildi, insan tarafından "en iyi" olduğu
  teyit edilmedi. Bunlar yine de AKTİF kabul edildi (görselleri çalışıyor, sadece seçim
  ileride gözden geçirilebilir) — listesi `reports/excel/gorsel_eslesme_raporu.xlsx`
  içindeki `Coklu_Gorseller` sayfasında.
- **`hammadde_id`/`kaplama_id` tamamen boş**: arama/filtreleme alanları hazır ama şu an
  hiçbir üründe veri yok.
- **Stok miktarı verisi yok**: `stok_hareketleri`/`lokasyonlar` boş, Faz 4 yükleyicisi
  henüz yazılmadı; işaret kuralı (yukarıda) bir varsayım, gerçek yükleyici yazılırken
  kullanıcıyla teyit edilmeli.
