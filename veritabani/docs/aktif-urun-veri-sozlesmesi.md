# Aktif Ürün Veri Sözleşmesi

Appsmith Ürünler/Katalog sayfasının kullanacağı veri sözleşmesi. Bu belge inceleme +
migration hazırlığı aşamasının çıktısıdır. **001, 002 ve 003 migration'larının tamamı
ortak veritabanına uygulandı** (bkz. "Migration sırası") — `v_aktif_urunler`,
`v_lokasyon_stok_ozet`, `v_toplam_stok` ve `stok_hareketi_kaydet()` artık canlıda
kullanılabilir.

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

1. **✅ UYGULANDI (2026-07-29)** — `sql/migrations/001_katalog_durumu.sql`. İlk deneme,
   CHECK constraint'in backfill UPDATE'lerinden ÖNCE eklenmesi yüzünden başarısız oldu
   (tüm satırlar anlık olarak tutarsız duruma düşüyordu) — transaction içinde olduğu
   için canlıya hiçbir şey yazılmadan geri alındı. Sıra düzeltildi (constraint artık
   backfill'den SONRA ekleniyor), ikinci denemede sorunsuz uygulandı: `UPDATE 1780`,
   `UPDATE 1193`, sonuç dry-run tahminiyle birebir eşleşti.
2. **✅ UYGULANDI (2026-07-29)** — `sql/migrations/002_lokasyon_stok_view.sql` (sadece
   view, mevcut tabloları değiştirmez). `v_lokasyon_stok_ozet`/`v_toplam_stok` canlıda
   sorgulandı, beklendiği gibi 0 satır döndü (`stok_hareketleri` hâlâ boş).
3. **✅ UYGULANDI (2026-07-29)** — `sql/migrations/003_stok_hareketi_fonksiyonu.sql`
   (mükerrer gönderim koruması + `stok_hareketi_kaydet()` fonksiyonu). Sözdizimi/mantık
   daha önce canlı şemaya karşı test edilmişti (`BEGIN` ... `ROLLBACK`, hiçbir kalıcı iz
   bırakmadan); kalıcı uygulama sonrası `\d stok_hareketleri` ve `\df stok_hareketi_kaydet`
   ile kolonların/fonksiyonun canlıda gerçekten oluştuğu doğrulandı.

Her biri `BEGIN`/`COMMIT` içinde, tek transaction, hata olursa otomatik geri alınır.
Her biri için ayrı bir `_rollback.sql` dosyası var. 002 ve 003, 001'e bağımlı değil
(002 ayrı tablolar üzerinde; 003 `stok_hareketleri`'ne dokunuyor ama `v_aktif_urunler`
kullanmıyor) — ama 003, `v_lokasyon_stok_ozet` view'ını çağırdığı için **002'den sonra
uygulanmalı**.

## Stok hareketi kayıt fonksiyonu ve sayım kuralı (kesinleşti)

**Sayım (SAYIM_DEVRİ) girişi TOPLAM BAKİYEDİR, fark değil.** Personel fiziksel olarak
saydığı toplam miktarı girer; personelin kendisinin fark hesaplaması istenmiyor —
hem sistemin mevcut rakamını önceden bilmesi gerekirdi (önyargı yaratır, sayımın amacını
zedeler) hem de elle çıkarma hata payı ekler. `stok_hareketi_kaydet()` fonksiyonu bu
toplamı `v_lokasyon_stok_ozet`'teki mevcut miktarla karşılaştırıp gerçek ledger farkını
kendisi hesaplar ve `stok_hareketleri`'ne öyle yazar (fark sıfırsa hiçbir satır eklenmez).

Appsmith'in `KaydetButton`'ı **doğrudan `stok_hareketleri`'ne INSERT atmamalı**, sadece
`stok_hareketi_kaydet(...)` fonksiyonunu çağırmalı:

```sql
SELECT * FROM stok_hareketi_kaydet(
    {{ crypto.randomUUID() }},                          -- istemci_islem_kimligi (mükerrer gönderim koruması)
    {{ UrunSonuclariTable.selectedRow.stok_kodu }},
    {{ IslemTipiSelect.selectedOptionValue }},
    {{ MiktarInput.text }}::INTEGER,
    NULL,                                   -- kaynak_lokasyon_id (GIRIS/SAYIM_DEVRI'de NULL, CIKIS'te zorunlu)
    {{ LokasyonSelect.selectedOptionValue }}::INTEGER,
    {{ AciklamaInput.text }},
    {{ appsmith.user.email }}               -- yapan_kullanici, zorunlu
);
```

Dönüş: `hareket_id`, `uygulanan_miktar`, `atlandi` (bool — mükerrer gönderim ya da sıfır
farklı sayım nedeniyle kayıt oluşmadıysa `TRUE`), `mesaj` (kullanıcıya gösterilecek
Türkçe açıklama). Appsmith `KaydetButton`'ın `onClick`'inde bu sorguyu çalıştırıp
`mesaj`'ı bir Toast/Text widget'ında göstermesi yeterli.

**2026-07-29 revizyonu — üç ek kontrol** (ChatGPT'nin "master plan" prompt'unun Prompt 3
gereksinimleri gözden geçirilirken ortaya çıktı, canlı şemaya karşı `BEGIN...ROLLBACK`
ile test edildi, hiçbir kalıcı iz bırakmadan):

- **Yeterli stok kontrolü**: kaynak lokasyondan bir miktar düşülecekse (ÇIKIŞ, TRANSFER'in
  kaynak ucu, DÜZELTME'nin azaltma ucu), oradaki mevcut miktarı aşamaz — aşarsa
  `RAISE EXCEPTION 'Yetersiz stok: bu lokasyonda % adet var, % adet çıkış isteniyor.'`.
  SAYIM_DEVRİ'nin kendi azaltma ucu matematiksel olarak bu kontrolü hep geçer (mevcuttan
  sayılana giden fark, tanım gereği mevcudu aşamaz).
- **`yapan_kullanici` zorunlu** (yeni kolon, `stok_hareketleri.yapan_kullanici VARCHAR(255) NOT NULL`) —
  Appsmith'in Postgres'e bağlantısı tek bir paylaşılan `depo_admin` kullanıcısıyla
  olduğu için Postgres'in kendi `current_user`'ına güvenilemez; değer açıkça
  `{{ appsmith.user.email }}`'den parametre olarak geçirilmeli.
- **İşlem tipine göre lokasyon zorunluluğu**: GİRİŞ→hedef zorunlu, ÇIKIŞ→kaynak zorunlu,
  TRANSFER→ikisi de zorunlu (bu zaten tablonun kendi CHECK'i ile de korunuyordu),
  DÜZELTME→en az biri zorunlu. Daha önce hiçbiri şema seviyesinde garanti değildi.

**Mükerrer gönderim koruması**: `{{ crypto.randomUUID() }}` her buton tıklamasında Appsmith'in
JS ortamında yeni bir UUID üretir. Çift tıklama ya da ağ tekrar denemesi aynı UUID'yi
tekrar gönderirse fonksiyon yeni satır eklemez, `atlandi=TRUE` döner. Ayrıca
`KaydetButton`'ın kendi `isDisabled`/loading durumu da (sorgu çalışırken buton pasif)
ek bir önlem olarak önerilir ama tek başına yeterli değildir (ağ tekrar denemesi
istemci tarafı devre dışı bırakmayı atlayabilir) — asıl güvence veritabanı seviyesindeki
UNIQUE kısıt.

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
