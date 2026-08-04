# METAKS ERP veri sözleşmesi

Bu dosya, Django arayüzünün `depo_sistemi` veritabanıyla bağlayıcı okuma/yazma
sözleşmesidir. Tarihsel test günlüğü değildir. Şemanın çalıştırılabilir otoritesi
`../sql/01_schema.sql` ile `../sql/migrations/` altındaki sıralı migration'lardır;
alan veya imza uyuşmazlığında SQL ve canlı şema birlikte doğrulanmalıdır.

Migration 001–007, 2026-08-04 itibarıyla ortak veritabanına uygulanmıştır.
Django'nun bu şemaya bağlı modelleri `managed = False` durumundadır ve
`depo_sistemi` üzerinde Django migration'ı çalıştırılmaz.

## Temel sınırlar

- Katalog ve arama `v_aktif_urunler` üzerinden okunur.
- Stok toplamı ve lokasyon kırılımı ilgili view'lardan okunur.
- `stok_hareketleri` yalnız `stok_hareketi_kaydet()` ile yazılır.
- `urunler` yalnız `urun_kaydet()` ile eklenir/güncellenir.
- Django iş kurallarını yeniden uygulamaz; parametreleri geçirir ve fonksiyonun
  döndürdüğü Türkçe mesajı kullanıcıya taşır.
- PostgreSQL mesajı ve kısıtları son savunma hattıdır; istemci doğrulaması yalnız
  kullanım kolaylığı sağlar.

Lokasyon yönetimi bu iki yazma kapısının dışındaki sınırlı istisnadır. Django
`lokasyonlar` tablosuna yazar; derinlik, üst ilişki ve tekillik kuralları PostgreSQL
kısıtlarıyla korunur. Okuma ve seçim yine `v_lokasyonlar_detay` üzerinden yapılır.

## Katalog durumu

`urunler.katalog_durumu` değerleri:

- `AKTIF`: katalogda gösterilebilir;
- `PASIF`: taslak veya doğrulanmış ana görseli olmayan ürün;
- `INCELEME_BEKLIYOR`: şemanın desteklediği, bugün otomatik kullanılmayan kalite
  inceleme durumu.

`chk_urunler_katalog_durumu_aktif_mi_tutarli`, `AKTIF` durumunu
`aktif_mi = TRUE`, diğer durumları `aktif_mi = FALSE` ile eşler.

İlk backfill'de ürün, aktif bir `ana_gorsel_mi` kaydı varsa AKTİF yapılmıştır.
Yeni ürün akışında `urun_kaydet()` ana görsel dosya adı verilince ürünü AKTİF,
verilmeyince PASİF taslak oluşturur. Dosyanın diskte gerçekten bulunması ve geçerli
bir görsel olması veritabanının değil, dosyayı önce yazıp doğrulayan uygulama
katmanının sorumluluğudur.

## Okuma view'ları

### `v_aktif_urunler`

Katalog/arama ekranlarının tek ürün kaynağıdır ve yalnız `AKTIF` satırları döndürür.

Alanlar, sırasıyla:

```text
stok_kodu, urun_tipi, parent_stok_kodu, varyant_adi,
olcu_mm, boy_ligne, boya_mine, gramaj_gr, montaj_durumu, aciklama,
kritik_stok_esigi,
kategori_id, kategori_adi,
hammadde_id, hammadde_adi,
kaplama_id, kaplama_adi,
ana_gorsel_dosya_adi, arama_metni
```

`arama_metni`, stok kodu + kategori + hammadde + ürün seviyesindeki eski kaplama
alanı + açıklamanın küçük harfli birleşimidir. Arama tüketicileri ayrı kolonları
elle birleştirmek yerine bu alanı kullanır.

Migration 007 sonrasında kaplama/montajın operasyonel otoritesi stok partisidir.
Üründeki eski alanlar geriye uyumluluk için kalır; yeni stok kırılımında kullanılmaz.

### `v_lokasyonlar_detay`

Lokasyon listeleri ve açılır kutuların tek okuma kaynağıdır.

```text
lokasyon_id, lokasyon_adi, kod, tip, aktif_mi,
ust_lokasyon_id, ust_lokasyon_adi, ust_kod, tam_ad, yaprak_mi
```

`tam_ad`, alt satırda `Üst · Alt` biçimindedir. `yaprak_mi`, altında herhangi bir
lokasyon bulunmaması demektir; alt satırın aktif olup olmaması sonucu değiştirmez.
Stok hareketi seçiminde doğru filtre `aktif_mi = TRUE AND yaprak_mi = TRUE` olur.
`NUMUNE` tipi dışlanmaz; numune rafında sayılan ürün yine o rafa yazılmalıdır.

Hiyerarşi bilerek iki seviyelidir: kök → alt/raf. Üretilmiş `kok_mu` ve
`ust_kok_mu` kolonları iç tesisattır, arayüz sözleşmesinin parçası değildir.

### `v_lokasyon_stok_ozet`

Alanlar:

```text
stok_kodu, lokasyon_id, lokasyon_adi, lokasyon_tipi, mevcut_miktar,
lokasyon_kodu, lokasyon_tam_adi,
kaplama_id, kaplama_adi, kaplama_cesidi, montaj
```

Satır anlamı ürün × lokasyon × stok kovasıdır. Aynı ürün ve lokasyon için birden
fazla satır gelebilir.

Kova kimliği:

```text
kaplama_id + kaplama_cesidi + montaj
```

Üç alan da NULL olabilir. Kova eşleştirmesinde `=` değil
`IS NOT DISTINCT FROM` kullanılmalıdır; aksi halde “belirtilmemiş” NULL kovası
hiçbir zaman eşleşmez. `kaplama_cesidi` yalnız `ASKIDA`, `DOLAP` veya NULL olabilir.

`boya` ve `mine`, hareket satırındaki açıklayıcı serbest metin alanlarıdır ve kova
anahtarına girmez. Büyük/küçük harf veya boşluk farkının yapay stok kovası açması
bu şekilde engellenir.

### Toplam ve numune view'ları

`v_toplam_stok(stok_kodu, toplam_miktar)`, ürün başına **satılabilir** toplamdır;
`NUMUNE` tipindeki lokasyonları hariç tutar.

`v_fiziksel_stok(stok_kodu, toplam_miktar)`, numuneler dahil ürün başına fiziksel
toplamdır.

İki view da ürün başına en fazla bir satır döndürür ve migration 007'de kova
kırılımına ayrılmamıştır. Satırın hiç olmaması “bu ürün henüz hareket görmedi”;
satır bulunup miktarın 0 olması “hareket gördü, net bakiye sıfır” anlamına gelir.
Arayüz bu iki durumu birleştirmemelidir.

`v_numune_konumlari` alanları:

```text
stok_kodu, lokasyon_id, lokasyon_kodu, lokasyon_tam_adi, mevcut_miktar
```

Yalnız pozitif bakiyesi olan `NUMUNE` lokasyonlarını döndürür.

## `stok_hareketi_kaydet()`

Bağlayıcı imza:

```sql
stok_hareketi_kaydet(
    p_istemci_islem_kimligi UUID,
    p_stok_kodu VARCHAR,
    p_islem_tipi VARCHAR,
    p_miktar INTEGER,
    p_kaynak_lokasyon_id INTEGER DEFAULT NULL,
    p_hedef_lokasyon_id INTEGER DEFAULT NULL,
    p_aciklama TEXT DEFAULT NULL,
    p_yapan_kullanici VARCHAR DEFAULT NULL,
    p_kaplama_id INTEGER DEFAULT NULL,
    p_kaplama_cesidi VARCHAR DEFAULT NULL,
    p_montaj BOOLEAN DEFAULT NULL,
    p_boya VARCHAR DEFAULT NULL,
    p_mine VARCHAR DEFAULT NULL
) RETURNS TABLE (
    hareket_id BIGINT, uygulanan_miktar INTEGER, atlandi BOOLEAN, mesaj TEXT
)
```

`p_yapan_kullanici` SQL imzasında geriye uyumluluk nedeniyle default taşır ama iş
kuralı olarak zorunludur; NULL/boş değer fonksiyon tarafından reddedilir.

| İşlem | Kaynak | Hedef | Anlam |
| --- | --- | --- | --- |
| `GIRIS` | Boş | Zorunlu | Hedefe miktar ekler |
| `CIKIS` | Zorunlu | Boş | Kaynaktan miktar düşer |
| `TRANSFER` | Zorunlu | Zorunlu | Aynı kovayı iki lokasyon arasında taşır |
| `SAYIM_DEVRI` | Boş | Zorunlu | Girilen toplam sayımı bakiyeye çevirir |
| `DUZELTME` | İsteğe bağlı | İsteğe bağlı | İkisinden en az biri zorunlu; kaynak azaltır, hedef artırır |

`SAYIM_DEVRI` değeri fark değil, personelin fiziksel olarak saydığı toplamdır.
Fonksiyon aynı lokasyon ve kovadaki mevcut miktarı bulur, ledger'a yalnız gereken
farkı yazar; fark 0 ise satır eklemeden `atlandi = TRUE` döner.

Kaynak azaltan işlemler aynı kovada yeterli stok bulunmasını gerektirir. Fonksiyon
yalnız yaprak lokasyona yazılmasına izin verir; aktiflik filtresi arayüz seçiminde
ayrıca uygulanır. UUID istemci kimliği UNIQUE'tir; aynı form/ağ isteği tekrar
gelirse ikinci hareket oluşmaz ve `atlandi = TRUE` döner. Arayüz her yeni form için
yeni UUID üretmeli, retry sırasında aynı UUID'yi korumalıdır.

Fonksiyonun `mesaj` alanı kullanıcıya gösterilir. Doğrudan INSERT, bu kontrolleri
ve idempotency güvencesini atladığı için yasaktır.

## `urun_kaydet()` ve görsel sırası

Bağlayıcı imzanın özeti:

```sql
urun_kaydet(
    p_mod VARCHAR, p_stok_kodu VARCHAR, p_yapan_kullanici VARCHAR,
    p_kategori_id INTEGER DEFAULT NULL, p_hammadde_id INTEGER DEFAULT NULL,
    p_kaplama_id INTEGER DEFAULT NULL, p_urun_tipi VARCHAR DEFAULT 'ANA_URUN',
    p_parent_stok_kodu VARCHAR DEFAULT NULL, p_varyant_adi VARCHAR DEFAULT NULL,
    p_kalip_versiyonu VARCHAR DEFAULT NULL, p_olcu_mm NUMERIC DEFAULT NULL,
    p_boy_ligne NUMERIC DEFAULT NULL, p_boya_mine VARCHAR DEFAULT NULL,
    p_gramaj_gr NUMERIC DEFAULT NULL, p_montaj_durumu VARCHAR DEFAULT NULL,
    p_aciklama TEXT DEFAULT NULL, p_kritik_stok_esigi INTEGER DEFAULT 0,
    p_stok_takip_edilsin_mi BOOLEAN DEFAULT TRUE,
    p_ana_gorsel_dosya_adi VARCHAR DEFAULT NULL
) RETURNS TABLE (
    stok_kodu VARCHAR, katalog_durumu VARCHAR, gorsel_id BIGINT, mesaj TEXT
)
```

İlk üç parametre zorunludur; geri kalanı adlandırılmış parametrelerle göndermek
tercih edilir. `p_mod` yalnız `EKLE` veya `GUNCELLE` olabilir. Sessiz upsert yoktur.

`GUNCELLE` tam kayıt değiştirmedir: form bütün alanları gönderir, NULL “eski değeri
koru” değil “alanı temizle” anlamındadır. Stok kodu kimliktir ve bu fonksiyonla
değiştirilmez. `ALT_PARCA` ve `VARYANT` geçerli bir üst ürün gerektirir.

Ana görsel adı verilirse ilgili görsel kaydı ana/aktif yapılır ve ürün AKTİF olur.
Verilmezse yeni ürün PASİF taslak olur; güncellemede mevcut görsel/katalog durumu
korunur. `ana_gorsel_mi` yetkili birincil-görsel alanıdır; `sira_no` yalnız sıralama
ve dosya adı içindir.

`urun_sonraki_gorsel_sirasi(p_stok_kodu) RETURNS INTEGER`, yeni dosya için
`MAX(sira_no) + 1` üretir. Dosya adı `<stok_kodu>_<sira>.<uzanti>` biçimindedir ve
DB'ye yol değil yalnız dosya adı verilir. Uygulama dosyayı önce yazmalı, sonra
`urun_kaydet()` çağırmalı; DB çağrısı başarısızsa yalnız yeni yazılan dosyayı
silmelidir. Var olan dosyanın üzerine yazılmaz.

`olusturan_kullanici` EKLE'de, `guncelleyen_kullanici` GUNCELLE'de yazılır;
güncelleme `updated_at` değerini ilerletir.

## Migration durumu

| Migration | Bağlayıcı sonuç | Durum |
| --- | --- | --- |
| 001 | Katalog durumu ve `v_aktif_urunler` | Uygulandı |
| 002 | Lokasyon ve toplam stok view'ları | Uygulandı |
| 003 | Stok hareketi fonksiyonu ve idempotency | Uygulandı |
| 004 | Lokasyon hiyerarşisi, NUMUNE ve fiziksel/numune view'ları | Uygulandı |
| 005 | Ürün yazma fonksiyonu, görsel sırası ve denetim izi | Uygulandı |
| 006 | 30 tarihsel test hareketinin koşullu temizliği | Uygulandı |
| 007 | Kaplama/montaj stok kovaları ve geniş fonksiyon imzası | Uygulandı |

006 yalnız geçmiş veri temizliğidir; fresh/boş kurulumun genel şema adımı değildir.
Tam önkoşulu sağlamayan veritabanında uygulanmamalıdır.

## Zaman dilimi sözleşmesi

`stok_hareketleri.islem_tarihi` ve bazı eski zaman alanları
`TIMESTAMP WITHOUT TIME ZONE` tipindedir. PostgreSQL oturumu UTC iken
`CURRENT_TIMESTAMP` bu alanlara UTC duvar saatini timezone bilgisiz yazar.

Django bu değeri doğrudan Europe/Istanbul saati gibi yorumlamamalıdır. Hareket
sorguları `web/katalog/models.py` içindeki `yerel_tarih()` desenini kullanır:
değer önce UTC kabul edilip timezone-aware yapılır, ardından Django gösterimde
`Europe/Istanbul` dilimine çevirir. Yeni sorgular aynı dönüşümü kullanmalıdır.

## Bilinen sınırlamalar

- Görsel doğrulaması dosyanın açılabildiğini ve stok koduyla ad eşleşmesini sınar;
  fotoğrafın doğru ürünü gösterdiğini otomatik kanıtlamaz.
- `INCELEME_BEKLIYOR` desteklenir fakat otomatik kalite akışı henüz yoktur.
- Ürün seviyesindeki eski kaplama/montaj alanları boş olabilir; stok için ledger alanları kullanılır.
- `boya` ve `mine` serbest metindir; raporlamada yazım varyasyonları dikkate alınır.
- 2026-08-04 itibarıyla gerçek `NUMUNE` lokasyonu yoktur; boş sonuç kod hatası değildir.
- Canlı sayılar sözleşme değildir; tarihli snapshot `INFO.md` içindedir.
