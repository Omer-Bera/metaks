# Gün sonu ekranı

Bu belge `/stok/gun-sonu/` ekranının tasarım kaydıdır. Fikir 2026-08-06'da
konuşuldu ve **bilerek sonraya bırakıldı**; burada duran şey karar değil, karar
verilirken kaybolmaması gereken ayrıntı. Açık iş maddesi
[YAPILACAKLAR.md](YAPILACAKLAR.md) madde 8'dir.

Kalıcı teknik kurallar [AGENTS.md](AGENTS.md), dosya üretme altyapısı
[DISA_AKTARIM_TASARIMI.md](DISA_AKTARIM_TASARIMI.md), şema otoritesi
[`veritabani/sql/`](../veritabani/sql/) içindedir.

## Neden gerekli?

Bugün "bugün ne oldu" sorusunun cevabı üç ayrı yerden toplanıyor: hareket
geçmişini tarih aralığıyla filtrele, fason işlerini ayrı sekmeden aç, dışarıda ne
kadar mal kaldığını iş emri iş emri topla. Depo sorumlusunun akşam kapanışta
sorduğu sorular ise tek küme:

- Bugün hangi belgeler yazıldı, hangi mal girdi, hangi mal çıktı?
- Şu anda dışarıda (fasonda) ne var, kimde, ne zamandır orada, ne zaman dönmesi
  bekleniyor, geciken var mı?
- Bunu kâğıda dökebiliyor muyum? (Vardiya devri, patrona rapor, arşiv.)

Ekranın varlık sebebi bu üç sorunun **tek sayfada ve yazdırılabilir** olması.
Yeni veri üretmiyor: mevcut defterin gün kesitini okuyor.

## Kullanıcı deneyimi

- Salt-okunur sayfa. Hiçbir yazma kapısına dokunmuyor, hiçbir form yok.
- Varsayılan gün **bugün**; `?tarih=YYYY-MM-DD` ile başka bir güne bakılabilir.
  Bu detay şart: personel çoğu zaman ertesi sabah "dünü" yazdırmak istiyor ve
  yalnız-bugün bir ekran o iş için kullanılamaz.
- Bir önceki / bir sonraki gün bağlantıları.
- Üstte "Rapor oluştur (PDF)" butonu.
- Giriş noktası: ana ekran ve stok listesindeki eylem satırı.

## Sayfanın bölümleri

### 1. Günün özeti (sayaç şeridi)

Tek satırda: yazılan belge sayısı, giren toplam adet, çıkan toplam adet, transfer
adedi, sayım/düzeltme belgesi sayısı, o gün açılan fason iş emri sayısı.

Sayaçların hepsi aşağıdaki iki bölümün verisinden türetilir; ayrı bir sorgu
kaynağı yok ki şerit ile tablo birbirini yalanlamasın.

### 2. Günün stok hareketleri

Satır değil **belge** listesi: `stok_islemleri` başlığı üstte (iş amacı, karşı
taraf, belge no, yapan kullanıcı, saat), altında o belgenin `stok_hareketleri`
satırları (SKU, miktar, kaynak → hedef, stok durumu, parti).

Belge bazlı olması bilinçli: bir fason dönüşü defterde ÇIKIŞ + GİRİŞ iki satır
üretiyor ve düz satır listesinde iki ayrı olay gibi okunuyor — hareket
geçmişinde bu ayrımın neden belge başlığından yapıldığı YAPILACAKLAR madde 6'da
kayıtlı, aynı gerekçe burada da geçerli.

### 3. Dışarıdaki ürünler

O anki durum (günün değil): açık fason iş emirlerinden `fason_bakiye > 0`
olanlar. Her satırda:

| Alan | Kaynak |
| --- | --- |
| İş emri no, fasoncu, fason lokasyonu | `v_fason_is_emri_ozet` |
| Gönderilen SKU → dönecek SKU, işlem türü | `v_fason_is_emri_ozet` |
| Planlanan / gönderilen / dönen / fire / dışarıda kalan | `v_fason_is_emri_ozet` |
| **Ne zamandır dışarıda** | view'da YOK — aşağıya bakın |
| Beklenen dönüş tarihi, gecikme rozeti | `v_fason_is_emri_ozet.beklenen_donus_tarihi` |

"Ne zamandır dışarıda" `v_fason_is_emri_ozet`te yok. Karşılığı, o iş emrine ait
**ilk `FASON_SEVK` belgesinin tarihi**: `stok_islemleri` içinde
`fason_is_emri_id = X AND islem_nedeni = 'FASON_SEVK'` satırlarının
`MIN(islem_tarihi)`'si. İki yol var:

1. Django tarafında tek gruplu sorgu (şema değişikliği yok, ilk sürüm için
   doğru olan).
2. İhtiyaç kalıcılaşırsa `v_fason_is_emri_ozet`e `ilk_sevk_tarihi` kolonu ekleyen
   bir migration. `CREATE OR REPLACE VIEW` kolon **sonuna** ekleme yapabiliyor,
   mevcut tüketicileri bozmaz.

Sayının doğrulaması da bu bölüme ait: iş emirlerindeki "dışarıda kalan"
toplamı, `v_stok_bakiye`'de `lokasyon_tipi = 'FASON'` satırlarının toplamına
**eşit olmalı**. Eşit değilse bu bir veri sorunudur ve ekranda görünmesi gerekir
— sessizce iki farklı sayı göstermektense uyarı basmak doğru davranış.

## Gün sınırı — kaymaya açık tek nokta

`stok_hareketleri.islem_tarihi` ve `stok_islemleri.islem_tarihi` **naive UTC**
tutuyor. Ham kolon üstünden `date(islem_tarihi) = today` yazmak Europe/Istanbul
gününü üç saat kaydırır: 00:00–03:00 arasındaki hareketler bir önceki güne
düşer. Filtre ve gruplama `models.yerel_tarih()` üzerinden yapılmalı — dışa
aktarımda aynı tuzak zaten bir kez ölçülüp kayda geçti (YAPILACAKLAR madde 5).

## PDF üretimi

İki yol var ve maliyetleri çok farklı:

**A. Yazdırma odaklı HTML (`@media print`) + tarayıcının "PDF olarak kaydet"i.**
Yeni bağımlılık yok, Raspberry Pi'de ek kurulum yok, projenin "Node/derleme adımı
yok" duruşuyla uyumlu. Dosyayı kullanıcı üretir; sunucu üretmez.

**B. Sunucu tarafında gerçek PDF.** `reportlab` (saf Python, arm64 tekerleği var,
ama düzeni elle kurarsınız) veya `WeasyPrint` (HTML/CSS'ten üretir, karşılığında
cairo/pango sistem kütüphaneleri ister — Pi'de ağır). Gerçek gerekçesi ancak
raporun otomatik arşivlenmesi/e-postalanması istenirse doğar.

**Öneri: önce A.** B'ye geçilecekse `reportlab`, ve o zaman
`disa_aktarim.py`'deki akış deseni (filtre → tek kaynak sorgu → akışlı yanıt)
aynen izlenmeli; ikinci bir "rapor kapsamı" tanımı açılmamalı.

Ayrıca hareket tablosunun XLSX/CSV karşılığı zaten var: gün aralığıyla
`/stok/hareketler/disa-aktar/` aynı kümeyi veriyor. Gün sonu ekranı bu bağlantıyı
göstermeli, kendi ikinci bir dosya üreticisini yazmamalı.

## Yetki

Salt-okunur ama stok verisi: `stok_goruntule` + `hareket_goruntule` ister.
Fason bölümü ayrıca `fason_yonet` İSTEMEZ — orada iş emri yönetilmiyor, yalnız
stoğun nerede olduğu okunuyor; `fason_yonet` iş emri açma/kapatma yetkisidir.

## Kararı verilmemiş noktalar

- Gün sonu "kapanış" kavramı var mı? Yani gün kilitlenip bir daha o güne hareket
  yazılamaz mı olacak, yoksa ekran sadece bir görünüm mü? **Şu anki varsayım:
  sadece görünüm.** Kilit, `stok_hareketleri`'nin append-only tasarımına yeni bir
  durum makinesi ekler ve düzeltme akışını da etkiler — ayrı bir karar.
- Rapor arşivlenecek mi (üretilen PDF sunucuda saklansın mı), yoksa her seferinde
  yeniden mi üretilecek? Arşivleme dosya sistemi + yedekleme sorusu açar; bu
  ekranın kapsamına kendiliğinden girmiyor.
- Numune rafları "dışarıda" değil ama gün sonunda ayrı bir satır hak ediyor mu?
  Madde 4 (numune takibi) bittiğinde yeniden bakılmalı.

## Kabul ölçütleri

- Seçilen günün bütün belgeleri ve hareket satırları tek sayfada, saat sırasıyla.
- Gün sınırı Europe/Istanbul; 00:00–03:00 arasındaki bir hareket doğru güne düşer
  (bu ayrıca test edilmeli, göz kararı doğrulanamaz).
- Dışarıdaki her iş emri için: kim, nerede, kaç adet, kaç gündür, ne zaman
  bekleniyor, gecikti mi.
- İş emri bazlı "dışarıda kalan" toplamı fason lokasyonlarının fiziksel
  bakiyesiyle eşit; değilse ekran uyarıyor.
- Sayfa yazdırıldığında (veya PDF'e basıldığında) filtre kutuları, menüler ve
  bağlantılar çıktıda yok; tarih ve kapsam çıktının başında yazılı.
- Ekran hiçbir yazma kapısını çağırmıyor.
