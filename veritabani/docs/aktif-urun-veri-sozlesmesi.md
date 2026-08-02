# Aktif Ürün Veri Sözleşmesi

Arayüz (`web/`, Django + HTMX) veriyi **yalnızca** buradaki view'lardan okur ve
**yalnızca** buradaki fonksiyonlardan yazar. Aşağıdaki imzalar bağlayıcıdır.

**001, 002 ve 003 migration'larının tamamı ortak veritabanına uygulandı** (bkz.
"Migration sırası") — `v_aktif_urunler`, `v_lokasyon_stok_ozet`, `v_toplam_stok` ve
`stok_hareketi_kaydet()` canlıda kullanılabilir.

**004 (numune lokasyonları) ve 005 (`urun_kaydet()`) yazıldı ve canlı şemaya karşı
`BEGIN...ROLLBACK` içinde test edildi, HENÜZ UYGULANMADI.** İkisi de aşağıda ayrı
bölümlerde belgelenmiştir. 004 uygulandığında `v_toplam_stok`'un **anlamı değişir**
(satılabilir stok = numune hariç) — ayrıntı için o bölüme bakın.

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
| `v_aktif_urunler` | yeni view | Katalog/arama ekranlarının **tek** okuma kaynağı — sadece aktif ürünler, kategori/hammadde/kaplama/ana görsel join'li |
| `v_lokasyon_stok_ozet` | view (002, 004 ve **007'de genişledi**) | ürün × lokasyon × **kaplama kovası** bazında net miktar |
| `stok_hareketleri.kaplama_id` / `kaplama_cesidi` / `montaj` / `boya` / `mine` | yeni kolon (007) | stok partisinin kaplama bilgisi; ilk üçü stok kovasını tanımlar |
| `v_toplam_stok` | view (002, **004'te anlamı değişti**) | ürün başına **satılabilir** toplam (004 sonrası NUMUNE hariç) |
| `v_lokasyonlar_detay` | yeni view (004) | lokasyon açılır listelerinin **tek** kaynağı — hiyerarşi, `tam_ad`, `yaprak_mi` |
| `v_fiziksel_stok` | yeni view (004) | ürün başına fiziksel toplam (numuneler **dahil**) |
| `v_numune_konumlari` | yeni view (004) | "bu ürünün numunesi nerede?" |
| `urun_kaydet()` | yeni fonksiyon (005) | ürün ekleme/güncellemenin **tek** kapısı |
| `urun_sonraki_gorsel_sirasi()` | yeni fonksiyon (005) | bir sonraki `sira_no` (dosya adı kurmak için) |
| `urunler.olusturan_kullanici` / `guncelleyen_kullanici` | yeni kolon (005) | denetim izi; eski 2.973 satırda NULL |

`urunler`/`urun_gorselleri`/`kategoriler`/`hammaddeler`/`kaplamalar` şemasında hiçbir
değişiklik yok, sadece `katalog_durumu` kolonu eklendi. `stok_hareketleri`/`lokasyonlar`
şemasında hiç değişiklik yok — sadece üzerlerine view eklendi.

## View alan adları

`v_aktif_urunler`: `stok_kodu`, `urun_tipi`, `parent_stok_kodu`, `varyant_adi`,
`olcu_mm`, `boy_ligne`, `boya_mine`, `gramaj_gr`, `montaj_durumu`, `aciklama`,
`kritik_stok_esigi`, `kategori_id`, `kategori_adi`, `hammadde_id`, `hammadde_adi`,
`kaplama_id`, `kaplama_adi`, `ana_gorsel_dosya_adi`, `arama_metni`.

`arama_metni`: stok_kodu + kategori_adi + hammadde_adi + kaplama_adi + aciklama'nın
küçük harfe çevrilip birleştirilmiş hali — tek bir `ILIKE '%...%'` ile hepsini aramak
için (bkz. `csv_guncelle.py`'deki `arama_metni_olustur()` ile aynı yaklaşım).

`v_lokasyon_stok_ozet`: `stok_kodu`, `lokasyon_id`, `lokasyon_adi`, `lokasyon_tipi`,
`mevcut_miktar` **+ 004 sonrası:** `lokasyon_kodu`, `lokasyon_tam_adi`
**+ 007 sonrası:** `kaplama_id`, `kaplama_adi`, `kaplama_cesidi`, `montaj`.
Yeni kolonlar her seferinde sona eklendi, mevcut kolonların adı/sırası/tipi korundu —
isimle seçen sorgular etkilenmez.

**007 bu view'ın SATIR ANLAMINI değiştirdi:** artık (stok_kodu, lokasyon) başına
birden fazla satır dönebiliyor — `kaplama_id` + `kaplama_cesidi` + `montaj` üçlüsü
bir stok **kovası** tanımlıyor ve her kova ayrı satır. Yani aynı ürünün aynı
lokasyondaki "light gold / askıda / montajlı" stoğu ile "ham / dolap / montajsız"
stoğu ayrı ayrı görünüyor ve **ayrı sayılıyor**. Bu view'dan tekil bir bakiye
okuyan her sorgu kovayı da eşleştirmek zorunda; üçü de NULL olabildiği için
karşılaştırma `=` ile değil **`IS NOT DISTINCT FROM`** ile yapılmalı (`= NULL`
hiçbir zaman eşleşmez, "belirtilmemiş" kovası hep 0 okunurdu).

`v_toplam_stok`: `stok_kodu`, `toplam_miktar`. `v_fiziksel_stok`: aynı kolonlar.
**İkisi de 007'de DEĞİŞMEDİ ve bu bilinçli** — ürün başına tek satır sözleşmesi
korunuyor. Altlarındaki satır sayısı arttı ama `SUM(...) GROUP BY stok_kodu`
sonucu aynı. Kırılımı buraya taşımak katalogdaki "sadece stokta olanlar"
filtresini, ana ekranın sayım ilerlemesini ve stok kartlarındaki tek rakamı
sessizce bozardı.

## Boş değer davranışları

- `hammadde_id`/`kaplama_id` → `NULL` (bu tablolar şu an **tamamen boş**, 0 satır;
  hiçbir üründe hammadde/kaplama ataması yapılmamış). `v_aktif_urunler.hammadde_adi`/
  `kaplama_adi` bu yüzden şu an **her satırda NULL** dönecek. Arayüzde bu
  filtreler şimdilik boş görünecek — kod hatası değil, veri henüz girilmemiş.
- `ana_gorsel_dosya_adi` → tanım gereği `v_aktif_urunler`'da hiçbir zaman NULL olamaz
  (view zaten aktif görseli olan satırları filtreliyor).
- `aciklama`, `varyant_adi`, `boya_mine`, `montaj_durumu`, `gramaj_gr`, `boy_ligne` →
  kaynak veride zaten kısmen boş, NULL olabilir; `arama_metni` bunları `coalesce(...,'')`
  ile boş string'e çeviriyor, arama sorgusu NULL'dan etkilenmiyor.
- `v_lokasyon_stok_ozet` / `v_toplam_stok` → **şu an 0 satır** (aşağıya bakın).

## Stok hesaplama yöntemi

*(2026-07-30 güncellemesi: aşağıdaki "tablolar boş" ifadesi artık geçerli değil —
`lokasyonlar`'da 8 satır (5 aktif gerçek iş lokasyonu), `stok_hareketleri`'nde 30 satır
var ve depo sayımı üzerinden aktif olarak veri akıyor. `v_toplam_stok` bugün 8 satır /
478 adet dönüyor. İşaret kuralı aşağıdaki haliyle geçerli ve `stok_hareketi_kaydet()`
tarafından uygulanıyor.)*

Kabul edilen işaret kuralı (varsayım — Faz 4 yükleyicisi bu kuralla tutarlı veri
üretmeli):

- `hedef_lokasyon_id` dolu → `+miktar` (GİRİŞ, TRANSFER'in varış ucu, SAYIM_DEVRİ açılış bakiyesi)
- `kaynak_lokasyon_id` dolu → `-miktar` (ÇIKIŞ, TRANSFER'in çıkış ucu)
- DÜZELTME: azaltma → kaynak_lokasyon_id dolu + pozitif miktar (ÇIKIŞ gibi); artırma → hedef_lokasyon_id dolu + pozitif miktar (GİRİŞ gibi)

Bir lokasyondaki net miktar = o lokasyonun hedef olduğu hareketlerin toplamı eksi
kaynak olduğu hareketlerin toplamı. Bu varsayım Faz 4 yükleyicisi yazılırken kullanıcıyla
teyit edilmeli.

## Örnek parametreli sorgular

Stok kodu/kategori/açıklama arayan canlı arama (arama kutusuna bağlı):

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

4. **⏳ YAZILDI, TEST EDİLDİ, UYGULANMADI (2026-07-30)** —
   `sql/migrations/004_numune_lokasyonlari.sql` (numune lokasyon hiyerarşisi, yeni
   view'lar, `stok_hareketi_kaydet()`'e yaprak kontrolü). Canlı şemaya karşı
   `BEGIN...ROLLBACK` içinde 13 senaryo ile test edildi: `v_toplam_stok` eski/yeni
   tanım farkı **0 satır**, mevcut 8 lokasyon etkilenmedi, derinlik-3 / mükerrer kod /
   mükerrer raf adı / üst lokasyona hareket reddedildi, yetersiz stok kontrolü
   regresyonu geçti. Rollback dosyası da test edildi — kolon/view/fonksiyon/kısıt
   dört ölçütte de **0 fark** ile geri getiriyor.
5. **⏳ YAZILDI, TEST EDİLDİ, UYGULANMADI (2026-07-30)** —
   `sql/migrations/005_urun_kaydet_fonksiyonu.sql` (`urun_kaydet()`,
   `urun_sonraki_gorsel_sirasi()`, denetim izi kolonları, `aktif_mi` varsayılan
   düzeltmesi). 19 senaryo ile test edildi; regresyon olarak mevcut 1780 AKTİF /
   1193 PASİF dağılımı ve `v_aktif_urunler`'ın 1780 satırı **değişmedi**.
   004 ve 005 birlikte de test edildi (yeni ürün → numune rafına giriş → `satilabilir=0`,
   `fiziksel=2` uçtan uca senaryosu).

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

Kaydet akışı **doğrudan `stok_hareketleri`'ne INSERT atmamalı**, sadece
`stok_hareketi_kaydet(...)` fonksiyonunu çağırmalı:

```sql
SELECT * FROM stok_hareketi_kaydet(
    %s,   -- istemci_islem_kimligi (UUID, mükerrer gönderim koruması)
    %s,   -- stok_kodu
    %s,   -- islem_tipi
    %s,   -- miktar (INTEGER)
    %s,   -- kaynak_lokasyon_id (GIRIS/SAYIM_DEVRI'de NULL, CIKIS'te zorunlu)
    %s,   -- hedef_lokasyon_id
    %s,   -- aciklama
    %s,   -- yapan_kullanici, zorunlu
    -- 007 sonrası, hepsi opsiyonel (verilmezse "belirtilmemiş" kovası):
    %s,   -- kaplama_id (kaplamalar tablosuna FK)
    %s,   -- kaplama_cesidi ('ASKIDA' | 'DOLAP')
    %s,   -- montaj (BOOLEAN)
    %s,   -- boya (serbest metin)
    %s    -- mine (serbest metin)
);
```

**007 imzayı genişletti ama geriye uyumlu**: beş yeni parametrenin hepsi
`DEFAULT NULL`, yani eski 8 argümanlı çağrılar değişmeden çalışıyor. Fonksiyon
`CREATE OR REPLACE` ile değil **önce `DROP` edilerek** yeniden yaratıldı; PostgreSQL
fonksiyonları (ad + argüman tipleri) ile tanımladığı için parametre eklemek eskisini
değiştirmez, yanına ikinci bir aşırı yükleme koyar ve 8 argümanlı çağrı
"function is not unique" ile belirsizleşirdi.

**Kova kimliği `kaplama_id` + `kaplama_cesidi` + `montaj`** üçlüsüdür; `boya`/`mine`
bilerek DIŞINDA. İkisi de serbest metin ve kimlik anahtarına girselerdi
`"kırmızı"`/`"Kırmızı"`/`"kırmızı "` üç ayrı stok kovası açar, stok sessizce
kaybolurdu. Onlar partinin açıklayıcı bilgisi, deftere not olarak düşüyor.

Dönüş: `hareket_id`, `uygulanan_miktar`, `atlandi` (bool — mükerrer gönderim ya da sıfır
farklı sayım nedeniyle kayıt oluşmadıysa `TRUE`), `mesaj` (kullanıcıya gösterilecek
Türkçe açıklama). Arayüzün yapması gereken tek şey bu sorguyu çalıştırıp `mesaj`'ı
kullanıcıya göstermek — kuralları ikinci kez doğrulamak değil.

**2026-07-29 revizyonu — üç ek kontrol** (ChatGPT'nin "master plan" prompt'unun Prompt 3
gereksinimleri gözden geçirilirken ortaya çıktı, canlı şemaya karşı `BEGIN...ROLLBACK`
ile test edildi, hiçbir kalıcı iz bırakmadan):

- **Yeterli stok kontrolü** (**007'de KOVA bazına indi**: artık "bu lokasyonda bu
  kaplamada kaç adet var" sorusuna bakıyor, lokasyonun toplamına değil — 100 adet
  "light gold" stoğu, "ham" kovasından yapılacak bir çıkışı karşılamıyor):
  kaynak lokasyondan bir miktar düşülecekse (ÇIKIŞ, TRANSFER'in
  kaynak ucu, DÜZELTME'nin azaltma ucu), oradaki mevcut miktarı aşamaz — aşarsa
  `RAISE EXCEPTION 'Yetersiz stok: bu lokasyonda % adet var, % adet çıkış isteniyor.'`.
  SAYIM_DEVRİ'nin kendi azaltma ucu matematiksel olarak bu kontrolü hep geçer (mevcuttan
  sayılana giden fark, tanım gereği mevcudu aşamaz).
- **`yapan_kullanici` zorunlu** (yeni kolon, `stok_hareketleri.yapan_kullanici VARCHAR(255) NOT NULL`) —
  Postgres'e tek bir paylaşılan `depo_admin` kullanıcısıyla bağlanıldığı için
  Postgres'in kendi `current_user`'ına güvenilemez; değer uygulamadan açıkça
  parametre olarak geçirilmeli (Django: `request.user.email or username`).
- **İşlem tipine göre lokasyon zorunluluğu**: GİRİŞ→hedef zorunlu, ÇIKIŞ→kaynak zorunlu,
  TRANSFER→ikisi de zorunlu (bu zaten tablonun kendi CHECK'i ile de korunuyordu),
  DÜZELTME→en az biri zorunlu. Daha önce hiçbiri şema seviyesinde garanti değildi.

**Mükerrer gönderim koruması**: arayüz her form basımında yeni bir UUID gömer. Çift
tıklama ya da ağ tekrar denemesi aynı UUID'yi tekrar gönderirse fonksiyon yeni satır
eklemez, `atlandi=TRUE` döner. Butonun kendi pasifleştirme/loading durumu ek bir önlem
olarak önerilir ama tek başına yeterli değildir (ağ tekrar denemesi
istemci tarafı devre dışı bırakmayı atlayabilir) — asıl güvence veritabanı seviyesindeki
UNIQUE kısıt.

## Numune lokasyonları (migration 004 — yazıldı, test edildi, UYGULANMADI)

Numune ayrı bir varlık değil: var olan `lokasyonlar` + `stok_hareketleri`
mekanizmasının üzerine oturuyor. Numune, ürünün bir adedinin bir yerde durmasıdır;
"depodan numune dolabına taşındı" tam olarak bir TRANSFER'dir, dolayısıyla numune
ödünç alınıp geri konduğunda hareket kaydı bedavaya gelir.

### Şema değişikliği

- `lokasyonlar.tip` artık `'DAHILI' | 'FASON' | 'NUMUNE'`.
- `lokasyonlar.ust_lokasyon_id` (self-FK, NULL = kök) ve `lokasyonlar.kod` (VARCHAR(20),
  tekil, NULL olabilir) eklendi. Dolap: `kod='N1'`, `ust_lokasyon_id=NULL`.
  Raf: `kod='N1-R3'`, `ust_lokasyon_id=<N1>`.
- **Derinlik 2 ile sınırlı** (dolap → raf) ve bu şemada zorlanıyor: `kok_mu`/`ust_kok_mu`
  üretilmiş kolonları + bileşik FK. Bu iki kolon iç tesisattır, **arayüzler okumamalı**.
- `uq_lokasyonlar_ad_tip` kaldırıldı, yerine `(COALESCE(ust_lokasyon_id,-1), lokasyon_adi, tip)`
  tekil indeksi geldi — eskisi Dolap 1'in "Raf 3"ü ile Dolap 2'nin "Raf 3"ünü çakıştırıp
  hiyerarşiyi bloke ediyordu. Kök lokasyonlar için davranış birebir korundu.
- **Mevcut 8 lokasyon hiç etkilenmiyor**: hepsi `ust_lokasyon_id=NULL, kod=NULL, yaprak_mi=true`.

### `v_lokasyonlar_detay` — açılır listelerin tek kaynağı

Kolonlar: `lokasyon_id`, `lokasyon_adi`, `kod`, `tip`, `aktif_mi`, `ust_lokasyon_id`,
`ust_lokasyon_adi`, `ust_kod`, `tam_ad`, `yaprak_mi`.

`tam_ad` = kök ise `lokasyon_adi`, alt ise `"<üst> · <alt>"` (örn. `Numune Dolabı 1 · Raf 3`).
`yaprak_mi` = hiç alt lokasyonu yok. Bu tanım `stok_hareketi_kaydet()`'in içindeki
kontrolle **birebir aynıdır** — aksi halde UI'da seçilebilen ama fonksiyonun reddettiği
bir lokasyon oluşurdu.

```sql
-- Stok işlemi ekranının lokasyon açılır listesi
SELECT lokasyon_id, tam_ad, tip
FROM v_lokasyonlar_detay
WHERE aktif_mi = true AND yaprak_mi = true
ORDER BY (tip = 'NUMUNE'), tam_ad;   -- depo lokasyonları önce
```

> **Numune rafları tipe göre DIŞLANMAMALIDIR.** Numune dolabını açıp 3 adet bulan kişi
> bunu ancak numune rafını seçebilirse yazabilir; dışlamak çözülmek istenen problemi
> ortadan kaldırır. Doğru filtre `yaprak_mi` (dolaplar çıkar, raflar kalır). Liste
> şişmesi sıralama + arama ile çözülür.

### Sadece yaprak lokasyona hareket yazılabilir

`stok_hareketi_kaydet()` artık kaynak ya da hedef olarak alt lokasyonu olan bir lokasyon
verilirse Türkçe `RAISE EXCEPTION` atıyor:

> `"Numune Dolabı 1" bir üst lokasyondur (alt lokasyonları var); stok hareketi doğrudan buraya yazılamaz, alt lokasyonlardan birini seçin.`

Fonksiyonun imzası ve geri kalan davranışı **değişmedi**.

### `v_toplam_stok`'un anlamı değişti — satılabilir stok

004 sonrası `v_toplam_stok` **NUMUNE tipindeki lokasyonları hariç tutar**. Fiziksel
toplam (numuneler dahil) için `v_fiziksel_stok` kullanılır. İkisinin de kolonları aynı:
`stok_kodu`, `toplam_miktar`.

Bu, var olan bir view'ın anlamını değiştirmektir. Gerekçe:

1. Henüz hiç NUMUNE lokasyonu yok, yani değişiklik **bugün sonucu hiç değiştirmiyor** —
   uygulama öncesi doğrulandı: iki tanım arasında **0 fark satırı** (8 satır / 478 adet).
2. View'ın dört tüketicisinin **dördü de zaten "satılabilir stok"** anlamında kullanıyor
   (`YonetimAnaSayfasi/OzetIstatistikler` ×2, `StokOzet/StokOzetGetir`,
   `UrunlerKatalog/KatalogUrunleriGetir`). Alternatif — `v_toplam_stok` fiziksel kalsın,
   satılabilir yeni view olsun — bu dördünün de düzeltilmesini gerektirir ve düzeltilmeyen
   biri **sessizce yanlış cevap verir**. Vitrindeki 2 numune yüzünden bir ürünün "kritik
   değil" görünmesi yanlış olurdu.

### `v_numune_konumlari` — "numunem nerede?"

Kolonlar: `stok_kodu`, `lokasyon_id`, `lokasyon_kodu`, `lokasyon_tam_adi`, `mevcut_miktar`.
Sadece `mevcut_miktar > 0` olan NUMUNE satırlarını döner.

### ⚠️ Uygulama sırası (bu sıra önemlidir)

Migration'ın kendisi **bilerek etkisizdir** — hiçbir NUMUNE lokasyonu oluşturmaz, sadece
oluşturulabilmesinin önünü açar. Tehlikeli adım veri girişidir, DDL değil:

1. ✅ **Migration 004** — etkisiz, güvenli. Açılır listeler değişmedi.
2. ✅ **Arayüzün lokasyon sorguları düzeltildi** (2026-07-31): stok işlem formu, hareket
   geçmişi filtresi ve ana ekran KPI'ı artık `v_lokasyonlar_detay` + `yaprak_mi`
   okuyor; `/yonetim/lokasyonlar/yeni/` formu `NUMUNE` tipini ve üst lokasyon
   seçimini sunuyor, yani numune dolabı/rafı artık arayüzden açılabiliyor.
3. **Sıradaki adım:** gerçek numune dolap/raf satırlarının girilmesi. Henüz girilmedi.

Adım 3 önce yapılsaydı devam eden sayımın yapıldığı ekranın lokasyon kutusu onlarca
satırla dolar ve kullanılamaz hâle gelirdi — sıranın sebebi buydu.

## `urun_kaydet()` (migration 005 — yazıldı, test edildi, UYGULANMADI)

### Neden zorunlu

`urunler`'e sade bir INSERT ürünü "görünmez" bırakmıyor, **doğrudan patlıyor** (canlıda
ölçüldü):

```text
INSERT INTO urunler (stok_kodu) VALUES ('X');
ERROR:  new row for relation "urunler" violates check constraint
        "chk_urunler_katalog_durumu_aktif_mi_tutarli"
```

Çünkü `aktif_mi` DEFAULT `TRUE` ile `katalog_durumu` DEFAULT `'PASIF'` birbiriyle
çelişiyor ve CHECK ikisinin birlikte hareket etmesini şart koşuyor. ORM'den gelen her
kısmi INSERT hata verir. **005 bu varsayılanı da düzeltiyor** (`aktif_mi` DEFAULT `FALSE`),
böylece sade INSERT geçerli bir PASİF taslak üretir. `scripts/database/yukle.py`
`aktif_mi`'yi açıkça yazdığı için etkilenmez (doğrulandı).

Ayrıca `katalog_durumu`'nu yöneten **hiçbir trigger yok** (doğrulandı: `urunler`,
`urun_gorselleri`, `stok_hareketleri` üzerindeki 26 trigger'ın hepsi `tgisinternal=t`,
yani FK kısıt trigger'ları). AKTİF ataması 001'deki tek seferlik backfill'di.

### İmza

```sql
urun_kaydet(
    p_mod                   VARCHAR,            -- 'EKLE' | 'GUNCELLE'  (zorunlu)
    p_stok_kodu             VARCHAR,            -- zorunlu
    p_yapan_kullanici       VARCHAR,            -- zorunlu (denetim izi)
    p_kategori_id           INTEGER DEFAULT NULL,
    p_hammadde_id           INTEGER DEFAULT NULL,
    p_kaplama_id            INTEGER DEFAULT NULL,
    p_urun_tipi             VARCHAR DEFAULT 'ANA_URUN',
    p_parent_stok_kodu      VARCHAR DEFAULT NULL,
    p_varyant_adi           VARCHAR DEFAULT NULL,
    p_kalip_versiyonu       VARCHAR DEFAULT NULL,
    p_olcu_mm               NUMERIC DEFAULT NULL,
    p_boy_ligne             NUMERIC DEFAULT NULL,
    p_boya_mine             VARCHAR DEFAULT NULL,
    p_gramaj_gr             NUMERIC DEFAULT NULL,
    p_montaj_durumu         VARCHAR DEFAULT NULL,
    p_aciklama              TEXT    DEFAULT NULL,
    p_kritik_stok_esigi     INTEGER DEFAULT 0,
    p_stok_takip_edilsin_mi BOOLEAN DEFAULT TRUE,
    p_ana_gorsel_dosya_adi  VARCHAR DEFAULT NULL
) RETURNS TABLE (
    stok_kodu      VARCHAR,
    katalog_durumu VARCHAR,   -- 'AKTIF' | 'PASIF'
    gorsel_id      BIGINT,    -- görsel verilmediyse NULL
    mesaj          TEXT       -- kullanıcıya gösterilecek Türkçe açıklama
)
```

İlk üç parametre konumsaldır; kalanlar için **adlandırılmış parametre** (`p_olcu_mm := 12.5`)
kullanın — 19 parametrenin sırasını takip etmek kırılgandır.

### Tasarım kararları

- **Tek fonksiyon + zorunlu `p_mod`**: sessiz upsert bilerek reddedildi. Ekleme
  ekranında yanlış yazılan bir stok kodu, sessiz upsert'te mevcut bir ürünü fark
  edilmeden ezerdi. `p_mod` niyeti açık kılıyor, doğrulama bloğu tek yerde kalıyor.
- **`GUNCELLE` = TAM KAYIT (full replace)**: form bütün alanları göndermeli, gönderilmeyen
  alan NULL'a çekilir. `COALESCE`'lı "kısmi güncelleme" bilerek seçilmedi — o tasarımda
  dolu bir alanı bir daha asla boşaltamazsınız.
- **AKTİF olma kuralı: tek şart ana görsel** (kullanıcı kararı, 2026-07-30). Kategori/ölçü
  zorunlu değil — mevcut 1780 AKTİF ürünün 31'i kategorisiz, 65'i ölçüsüz olduğu için daha
  sıkı bir kural eski veriyle çelişirdi. Ana görselsiz ürün PASİF kalır; bu bir hata değil,
  **taslak üründür**.
- **Ayrı idempotency UUID'sine gerek yok**: `stok_kodu` birincil anahtar olduğundan doğal
  idempotency anahtarıdır (EKLE modunda ikinci gönderim anlaşılır bir hata verir).
- **Kapsam dışı**: `stok_kodu` değiştirme. GUNCELLE modunda `stok_kodu` kimliktir.

### Doğrulamalar (hepsi Türkçe `RAISE EXCEPTION`)

Geçersiz `p_mod` · boş `p_stok_kodu` · boş `p_yapan_kullanici` · negatif
`p_kritik_stok_esigi` · EKLE'de zaten var olan stok kodu · GUNCELLE'de bulunamayan ürün ·
var olmayan `kategori_id`/`hammadde_id`/`kaplama_id` · izinli olmayan `urun_tipi` ·
`ALT_PARCA`/`VARYANT` için eksik `parent_stok_kodu` · kendine parent · var olmayan parent ·
görsel adı yerine yol verilmesi (`/` veya `\` içeren değer reddedilir).

### Ana görsel davranışı

- `p_ana_gorsel_dosya_adi` verilirse: önce o ürünün diğer ana görselleri indirilir, sonra
  yenisi `ana_gorsel_mi=true, aktif_mi=true` olarak yazılır (`uq_urun_tek_ana_gorsel`
  kısmi tekil indeksi gereği bu sıra zorunlu). Ürün `AKTIF` olur.
- Aynı dosya adı tekrar verilirse **yeni satır açılmaz**, mevcut satır yeniden ana görsel
  yapılır (`uq_urun_gorselleri_dosya` gereği).
- Verilmezse: EKLE'de ürün PASİF taslak doğar; GUNCELLE'de mevcut durum ve görseller
  **korunur** (görseli olan ürün pasife düşmez).
- **`ana_gorsel_mi` yetkili alandır, `sira_no` değil.** Eski pipeline `sira_no=1`'i birincil
  kabul ediyordu; bundan sonra `sira_no` yalnızca sıralama/dosya adı ekidir. Bir ürünün
  ikinci görseli ana görsel yapılırsa `sira_no=2` olup `ana_gorsel_mi=true` olabilir.

### Görsel dosyası — DB dışında kalan kısım

- Dosyalar `images/final/products/` altında, adlandırma `<stok_kodu>_<sira_no>.<uzantı>`.
  Django **doğrudan bu dizine yazar** (tek dizin, tek URL tabanı, mevcut
  `scripts/images/gorsel_eslesme_raporu.py` çalışmaya devam eder).
  **Koşul: asla üzerine yazma, sadece yeni dosya.** Bu dizin `CLAUDE.md`'de "load-bearing"
  olarak işaretli.
- `sira_no` için `urun_sonraki_gorsel_sirasi(p_stok_kodu) RETURNS INTEGER` çağrılır
  (`MAX(sira_no)+1`, ürün yoksa 1).
- Uzantı **yeni yüklemelerde** küçük harfe çevrilir ve `jpeg` → `jpg` normalize edilir.
  Mevcut 435 `jpeg` kaydına dokunulmaz.
- **Sıra: önce dosya, sonra DB.** Fonksiyon hata verirse yazılan dosya silinir. Ters
  sırada bir çökme, DB'de var olmayan dosyayı gösteren kırık bir ürün bırakır; bu sırada
  ise en kötü ihtimalle sahipsiz bir dosya kalır — ve onu bulan araç zaten mevcut.
- ⚠️ **VPS/Raspberry Pi'ye taşınırsa bu bağlantı yeniden düşünülmeli**: bugün Django ile
  nginx aynı hostta ve dizin `docker-compose.yml`'de nginx'e `:ro` bağlı; yazan taraf
  host. Ayrı makinelere dağılırsa paylaşımlı bir birim (NFS/S3 vb.) ya da bir yükleme
  servisi gerekir.

### Django çağrı örneği

```python
with connections['metaks'].cursor() as cur:
    cur.execute(
        "SELECT stok_kodu, katalog_durumu, gorsel_id, mesaj "
        "FROM urun_kaydet(%s, %s, %s, p_kategori_id := %s, p_olcu_mm := %s, "
        "                 p_ana_gorsel_dosya_adi := %s)",
        ['EKLE', stok_kodu, request.user.email, kategori_id, olcu_mm, dosya_adi],
    )
    stok_kodu, katalog_durumu, gorsel_id, mesaj = cur.fetchone()
```

`stok_servisi.py`'deki desenin aynısı: iş kuralları Python'da **tekrarlanmaz**, Türkçe
mesaj doğrudan fonksiyondan gelir.

### Denetim izi

`urunler.olusturan_kullanici` EKLE'de, `guncelleyen_kullanici` GUNCELLE'de yazılır;
GUNCELLE ayrıca `updated_at`'i ilerletir (bu kolonun bakımını bugüne kadar hiçbir şey
yapmıyordu — 2973/2973 satırda `created_at`'e eşitti). Mevcut 2.973 satırda ikisi de
NULL kalır: o ürünleri kimin oluşturduğunu gerçekten bilmiyoruz, NULL "bilinmiyor"
demektir.

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
