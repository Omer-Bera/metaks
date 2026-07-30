# Yapılacaklar

Sırayla önceliklendirilmiş iş listesi. Mimari kararlar ve mevcut durum `CLAUDE.md`'de;
burası "sırada ne var" sorusunun cevabı.

Sıra kullanıcıyla kararlaştırıldı (2026-07-30):
**giriş akışı → yönetim paneli/kullanıcılar → ürün ekleme → numune takibi → CSV.**

4 ve 5 numaralı işler `metaks_DB` tarafında şema hazırlığı bekliyor; o iş paralel
yürüyebilir, 1 ve 2 hiçbir şeye bağlı değil.

---

## 1. Giriş akışı ✅ TAMAMLANDI (2026-07-30)

Giriş kutusu ana ekranın en altında, modül kartlarının da altında kalıyordu.

Yapılanlar: `/` artık yönlendirici (`views.ana_ekran`) — giriş yapılmışsa **veya**
session'da `misafir` bayrağı varsa panel, aksi hâlde `/giris/`. Giriş formu
çoğaltılmadı, yönlendirme tercih edildi. Giriş ekranında ayraç + **"Giriş yapmadan
devam et"** (`/misafir/`, bayrağı işaretleyip panele döner). Ana ekrandaki giriş
kutusu kaldırıldı; üst çubuğa giriş yapmamış kullanıcı için **"Giriş yap"** eklendi
(ana ekran, katalog/stok, hareket geçmişi) — girişin kalıcı görünür yolu bu, asıl
keşfedilebilirlik düzeltmesi. `LoginView` artık `redirect_authenticated_user=True`.

Bilinçli detaylar:

- **Misafir seçimi session'da hatırlanıyor**, yani kapı tarayıcı başına bir kez
  çıkıyor. Katalog ön büroda müşteri karşısında hızla açılan bir ekran; her açılışta
  araya sayfa koymak günde onlarca gereksiz tıklama olurdu.
- **Çıkışta bayrak da temizleniyor** — Django'nun `logout()`'u session'ı flush ettiği
  için bedavaya geliyor, yani "Çıkış" güvenilir biçimde giriş ekranına döner.
- Katalog/stok/hareketler hâlâ **girişsiz açık**; sadece yazma sayfası
  `@login_required` ve `next` ile geri dönüş korunuyor.

Doğrulama: gerçek tarayıcıda 25/25 kontrol (kök yönlendirme, misafir devam, session
hafızası, üst çubuk her iki durumda, giriş yapmışken `/giris/`, çıkış sonrası kapının
geri gelmesi, `next` akışı, mobil, şablon sızıntısı, konsol). Test girişi için
`default` SQLite'ta geçici kullanıcı açılıp sonunda silindi — paylaşımlı Postgres'e
dokunulmadı.

---

## 2. Yönetim paneli (`/yonetim/`)

Tek bir yönetim giriş noktası; içinde şimdilik iki kart: **Kullanıcılar** ve **Ürünler**.
Diğer sayfalarla aynı tasarım dili. Sadece yetkili kullanıcıya görünür.

### 2a. Kullanıcı yönetimi

Kullanıcılar Django'nun **SQLite `default`** bağlantısında (paylaşımlı METAKS
Postgres'ine dokunulmuyor) — yani bu iş `metaks_DB` tarafında hiçbir şey beklemiyor.

- Kullanıcı listesi, ekleme, parola değiştirme, pasife alma.
- Django'nun hazır `/admin/`'i bugün de çalışıyor ve bu işi yapabilir; ama çerçeve
  gürültüsü (log kayıtları, izin matrisi, İngilizce terimler) ekip için uygun değil.
  `/admin/` kaçış yolu olarak açık kalsın, günlük kullanım sade ekrandan olsun.
- **Bunun içinde halledilecek:** bugünkü tek hesabın (`omer`) parolası geliştirme
  sırasında konuldu, değiştirilmeli.

### 2b. Rol/yetki ayrımı (bu adımda değil, ama buradan doğacak)

Şu an giriş yapan herkes her ürüne her işlem tipini uygulayabiliyor. İç ağda tek ekip
için bugün yeterli; **fason/dış kullanıcı girdiği anda** gözden geçirilmeli. Kullanıcı
ekranı yapılırken en azından "yönetici mi" ayrımının yeri hazırlansın.

Orta boy iş. Bağımsız.

---

## 3. Ürün ekleme / düzenleme

Kendi sayfası (`/urun/ekle/`), yönetim panelinden ve liste sayfalarından erişilir.

> **Ön koşul karşılandı (2026-07-30):** `urun_kaydet()` canlıda. Django tarafı artık
> `katalog/stok_servisi.py` deseninde ince bir çağrı katmanı yazacak — iş kuralı
> tekrarlanmayacak, dönen Türkçe mesaj olduğu gibi taşınacak.

### Giriş noktaları

- **Ürün sayısının yanına "+ Ürün ekle" butonu** (katalog ve stok sayfalarında),
  yalnızca **giriş yapmış** kullanıcıya görünür — müşteriye ürün gösterirken açılan
  katalog sayfasında yazma butonu görünmesin.
- **Boş arama sonucundan ekleme:** kullanıcı bir stok kodu arayıp bulamadığında
  "Bu koda ait ürün yok — `1005120` ile ürün ekle" bağlantısı çıksın. İhtiyacın gerçekten
  doğduğu an burası; kod da forma önceden doldurulmuş gelir.

### Form alanları

Zorunlu olan tek kolon `urunler.stok_kodu`; kalanların hepsi NULL kabul ediyor ya da
varsayılanı var. Ama pratikte kataloğun işe yaraması için gereken çekirdek: **stok kodu,
kategori, ürün tipi, ölçü ve ana görsel.**

Form ikiye ayrılsın: kısa bir **temel** bölüm + katlanır **detay** bölümü. Sebebi ölçüm:
`boya_mine`, `montaj_durumu`, `hammadde_adi`, `kaplama_adi` bugün **1.780 ürünün
hiçbirinde** dolu değil — hepsini öne koymak formu kimsenin doldurmadığı alanlarla
şişirirdi (detay panelinin "sadece dolu alanları göster" mantığının aynısı).

### Bu iş neden stok işleminden zor — ölçülmüş sebepler

1. **Satır eklemek yetmiyor, ürün görünmez kalır.** `urunler`'e INSERT edilen kayıt
   `katalog_durumu` varsayılanı olan `PASIF` ile doğar ve **öyle kalır**: bu değeri
   yöneten hiçbir trigger yok (kontrol edildi — `urunler` üzerinde trigger sıfır),
   AKTİF ataması migration 001'deki **tek seferlik backfill UPDATE**'ti. Ayrıca
   `chk_urunler_katalog_durumu_aktif_mi_tutarli` kısıtı `katalog_durumu` ile `aktif_mi`'nin
   birlikte hareket etmesini zorunlu kılıyor.
   Yani ekleme akışı bir bütün: görsel yükle → `urun_gorselleri`'ne
   `ana_gorsel_mi=true, aktif_mi=true` satırı → `urunler`'i `AKTIF` + `aktif_mi=true` yap.
   Üçü **tek transaction'da**, yoksa yarım ürün kalır.
2. **Görsel dosyası nereye yazılacak?** Görselleri nginx `gorsel-sunucu` servisi
   `<stok_kodu>_<sira_no>.<uzantı>` adlandırmasıyla sunuyor ve dizinin
   (`metaks_DB/images/final/products`) sahibi `metaks_DB`; nginx'e `:ro` bağlı, yazan
   taraf host. Bu repo bugün hiç dosya yazmıyor — Django'ya o dizine yazma yetkisi
   vermek gerçek bir bağlantı kararı.

**Sıralama kararı:** önce dosya, sonra DB. Fonksiyon hata verirse yazılan dosya silinir.
Ters sırada çökme olursa var olmayan dosyayı gösteren kırık ürün kalır; bu sırada en
kötü ihtimalle sahipsiz bir dosya kalır, o da zararsız.

Büyük iş, ön koşullu.

---

## 4. Numune takibi (dolap / raf)

**Karar:** ayrı veritabanı **yok**, ayrı tablo **yok**. Numune, fiziksel olarak ürünün
bir adedinin bir yerde durması demek — sistemde bunun adı zaten **lokasyon**. Mevcut
altyapı (`lokasyonlar` + `stok_hareketleri` + TRANSFER + detay panelindeki lokasyon
dökümü) işi büyük ölçüde karşılıyor: numune dolabı bir lokasyon olarak tanımlandığı
anda "bu ürünün numunesi Vitrin'de, 2 adet" bilgisi neredeyse yeni ekran yazmadan
çıkıyor, numune ödünç alınıp geri konduğunda kaydı da bedavaya geliyor.

Ayrı veritabanı elendi: `urunler` ile join edilemez, iki bağlantı, iki yedekleme,
bütünlük sadece gelenekle korunur. Aynı iş, aynı ürünler — aynı veritabanı.

### Adresleme: kütüphane düzeni (karar verildi)

Kullanıcının istediği "kütüphanede kitap bulur gibi" düzen → **iki seviyeli hiyerarşi +
kısa kod**: dolap (`N1`) → raf (`N1-R3`). `lokasyonlar`'a `ust_lokasyon_id` (self-FK) ve
`kod` kolonları eklenir; mevcut 8 lokasyon ikisi de NULL kalarak etkilenmez.

Düz isimlendirme ("Numune Dolabı 1 – Raf 3" tek satır) elendi: dolap sayısı belirsiz ve
yeniden düzenleneceği söylendi — düz isimde bir dolabı yeniden adlandırmak N satır,
hiyerarşide tek satır; ayrıca "Dolap 1'de ne var" sorgusu string önekine bağlı kalmaz.
Derinlik bilerek 2 seviyede sabit, genel amaçlı ağaç kurulmuyor.

### Django tarafında yapılacak

- Numune lokasyonları için stok işlemi formunda **iki adımlı seçim** (dolap → raf) ya da
  aranabilir kutu; onlarca rafı düz bir `<select>`'e dökmek kullanılamaz olur.
- Detay panelinde numune satırları ayrı gösterilsin: **"478 adet · 2 numunede"**.
- Ürün detayında "Numunesi nerede?" doğrudan görünür olsun — asıl sorulan soru bu.

### Zamanlama

Sıralamada 3'ten sonra ama **iş yükü olarak çok daha küçük** (iki migration + birkaç
lokasyon satırı + rozet), gerekirse araya girebilir. Ek gerekçe: **sayım hâlâ sürüyor**
ve numune dolabını açıp 3 adet bulan kişinin bunu yazacağı dürüst bir yer bugün yok —
ya hiç yazılmıyor ya bir depo lokasyonuna karışıyor. Sayımın doğruluğunu etkileyen bir
eksik, sonradan eklenen bir süs değil.

---

## 5. Hareket geçmişinde CSV / Excel dışa aktarma

Sayım denetimi için: `/stok/hareketler/` üzerindeki **aktif filtrelerle** aynı sonucu
dosya olarak indirme. Filtre çubuğuna bir "Dışa aktar" butonu.

Dikkat edilecekler:

- Tarihler **yerel saatle** yazılmalı — `yerel_tarih()` kullanılmazsa dosyada 3 saat
  geri değerler olur (bkz. CLAUDE.md, zaman dilimi tuzağı).
- Excel'in Türkçe yerel ayarı CSV'de **`;` ayracı** ve **UTF-8 BOM** bekler; virgül +
  BOM'suz dosya açıldığında hem Türkçe karakterler bozulur hem her satır tek hücreye düşer.
  Gerçek Excel'de açıp doğrulanmalı.
- Sayfalama yok, filtrelenmiş kümenin tamamı; `StreamingHttpResponse` ile satır satır
  akıtılmalı (bugün 30 satır ama defter append-only, sürekli büyüyecek).
- Salt-okunur iş, `stok_hareketi_kaydet()` disiplinine dokunmuyor.

Bağımsız iş. Küçük.

---

## metaks_DB tarafı — ✅ TAMAMLANDI (2026-07-30)

Devir metni `docs/metaks-db-istekleri.md`'de. Migration 004 (numune lokasyonları) ve
005 (`urun_kaydet()`) canlı `depo_sistemi`'ne uygulandı ve doğrulandı; öncesi/sonrası
birebir aynı (8 lokasyon, 30 hareket, 1780 AKTİF, `v_toplam_stok` 8 satır / 478 adet).

Sonuçta kullanılabilir hâle gelenler:

- `v_lokasyonlar_detay` — açılır listelerin **tek kaynağı**; `kod`, `tam_ad`
  ("Numune Dolabı 1 · Raf 3"), `yaprak_mi`.
- `v_toplam_stok` artık **satılabilir** stok (NUMUNE hariç), `v_fiziksel_stok` hepsi.
- `v_numune_konumlari` — "bu ürünün numunesi nerede?" doğrudan buradan.
- `v_lokasyon_stok_ozet`'e `lokasyon_kodu` + `lokasyon_tam_adi` eklendi (sona; mevcut
  kolonların adı/sırası korundu, `LokasyonStok` modeli etkilenmedi).
- `urun_kaydet(p_mod, p_stok_kodu, p_yapan_kullanici, …, p_ana_gorsel_dosya_adi)` →
  `(stok_kodu, katalog_durumu, gorsel_id, mesaj)`; `urun_sonraki_gorsel_sirasi()`.
- `urunler`'e `olusturan_kullanici` / `guncelleyen_kullanici`; `aktif_mi` varsayılanı
  FALSE'a düzeltildi.
- `stok_hareketi_kaydet()` artık sadece **yaprak** lokasyona yazıyor.

### ⚠️ Kalan tuzak: lokasyon sorguları (numune satırları GİRİLMEDEN önce)

Bugün hiçbir NUMUNE satırı yok, o yüzden hiçbir şey bozuk değil. Ama gerçek dolap/raf
satırları girilmeden **önce** her iki arayüz de `v_lokasyonlar_detay`'a taşınıp
`yaprak_mi` filtresi almalı. **Tipe göre dışlamak yanlış olur** — numune dolabını açıp
3 adet bulan kişi o rafı seçemezse çözülmek istenen problem yerinde kalır.

Django'da üç yer (dördüncüsü `views.py:577`, dokunulmasa da doğru — dolaplara hareket
yazılamadığı için `v_lokasyon_stok_ozet`'te hiç görünmezler):

| Yer | Bugünkü hâli | Numune girilince |
| --- | --- | --- |
| `views.py:651` (stok işlem formu) | `filter(aktif_mi=True)` | dolaplar seçilebilir görünür, fonksiyon reddeder |
| `views.py:431` (hareket geçmişi filtresi) | `.all()` — hiç filtre yok | aynı, üstelik pasifler de dahil |
| `views.py:81` (ana ekran KPI) | `filter(aktif_mi=True).count()` | **"Aktif lokasyon" rafları depo sayar** (5 → 23) |

Appsmith'te iki yer: `StokIslemi/LokasyonlariGetir`,
`LokasyonYonetimi/LokasyonlarListele`. Ayrıca
`LokasyonYonetimi/YeniLokasyonTipiSelect.json` tip listesini sabit gömüyor
(`Dahili`/`Fason`) — yeni tip orada görünmez, yani numune lokasyonu Appsmith'ten
eklenemez (sorun değil, kasıtlı olarak metaks_DB tarafından girilecek).

---

## Sırası gelmemiş / arka planda duranlar

- **Otomatik test yok** (`katalog/tests.py` boş). Django test runner'ı `metaks` bağlantısı
  için test veritabanı oluşturmaya çalışır — paylaşımlı `depo_sistemi`'ne karşı istenmeyen
  davranış. Muhtemel yol: `SimpleTestCase` / `databases = {'default'}` + fixture katmanı.
- **Test hareketleri ledger'da duruyor** (`1001013`, `1001020`) — ürün tamamlandığında
  `metaks_DB` tarafında numaralı migration ile temizlenecek (kararlaştırıldı).
- **Çoklu görsel galerisi yok** — 1.780 ürünün sadece 19'unda ikinci aktif görsel var,
  kazanç küçük.
- **Otomatik tazeleme yok** — açık duran sekme yenilenene kadar eski veriyi gösterir.
  Canlı stok ekranında `hx-trigger="every 30s"` mantıklı olur, katalogda gereksiz.
- **Üretim ayarları** (DEBUG, SECRET_KEY, ALLOWED_HOSTS, HTTPS) ve hosting kararı.
  Giriş eklendiği için artık kritik: parolalar bugün HTTP üzerinden gidiyor, **dışarı
  açılmadan önce** HTTPS ve gerçek bir `SECRET_KEY` şart.
- **Branch modeli** — kardeş repolardaki `master`/`dev`/`review` düzeni buraya
  uygulanmadı, karar bekliyor.
