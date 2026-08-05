# Yapılacaklar

Bu dosya arayüz tarafındaki açık işleri ve kısa karar kaydını tutar. Kalıcı teknik
kurallar [AGENTS.md](AGENTS.md), şema yol haritası
[`veritabani/docs/INFO.md`](../veritabani/docs/INFO.md), yayın ve güvenlik işleri ise
[Güvenlik ve yayına hazırlık](../GUVENLIK_VE_YAYINA_HAZIRLIK.md) içindedir.

Eski madde numaraları kod ve diğer belge referanslarını bozmamak için korunur.
Güncel uygulama sırası:

1. **Migration 008 + 009'u yedek + açık onayla ortak veritabanına uygulama**
   (009 renk/hammadde tohumlaması; 008'e bağımlı, ondan sonra uygulanır)
2. **Eski/belirsiz SKU bakiyesini fiziksel sayımla gerçek SKU'lara sınıflandırma**
3. **Madde 4 — gerçek numune dolap/raf düzeni**
4. **Madde 5 — filtreli CSV/Excel dışa aktarma**

---

## 4. Numune takibi — sıradaki iş

### Değişmeyecek karar

Numune için ayrı veritabanı veya ayrı tablo kurulmayacak. Numune, ürünün `NUMUNE`
tipli bir lokasyonda duran fiziksel stoğudur. Dolap kök, raf yaprak lokasyondur;
dolaba değil rafa hareket yazılır. Numunenin dolaba gidişi/gelişi normal TRANSFER
hareketidir ve aynı defterde izlenir.

Şema ön koşulları tamamlandı:

- migration 004 dolap→raf hiyerarşisini, `kod` alanını ve `NUMUNE` tipini ekledi;
- `v_lokasyonlar_detay`, `v_fiziksel_stok` ve `v_numune_konumlari` hazır;
- stok yazma fonksiyonu yalnız `yaprak_mi=True` lokasyona izin veriyor;
- Django lokasyon yönetimi ve hareket seçimleri `LokasyonDetay` kullanıyor.

### Yapılacaklar

- [ ] Fiziksel dolapları ve rafları kullanıcıyla yerinde çıkar: dolap adı/kodu,
  raf adı/kodu ve kullanılacak sıralama kesinleşsin.
- [ ] Gerçek kök/raf satırlarını `/yonetim/lokasyonlar/` üzerinden gir. Deneme veya
  hayalî lokasyonları canlı listede bırakma.
- [ ] Raf sayısı büyüdüğünde stok işlem formundaki düz seçimi iki adımlı
  dolap→raf seçimine veya aranabilir kutuya çevir. Küçük listede gereksiz özel UI
  ekleme; gerçek satır sayısına göre karar ver.
- [x] Ürün stok detayında satılabilir stok ile numuneyi ayrı özetle; örneğin
  “N adet satılabilir · M numune”. Toplamların kaynağı doğru view olmalı.
- [ ] Ürün detayında “Numunesi nerede?” bilgisini `v_numune_konumlari` üzerinden
  doğrudan görünür yap; dolap + raf kodu/adı birlikte gösterilsin.
- [x] Transfer ekranında numune raflarını anlaşılır etiketle; kök dolabın seçilebilir
  hâle gelmediğini koru.

### Kabul ölçütleri

- Bir ürün kodundan numunenin dolap/raf konumu tek ekranda bulunabiliyor.
- Depo→numune ve numune→depo transferleri aynı stok defterinde izleniyor.
- Numune miktarı fiziksel stokta var, satılabilir stok toplamında yok.
- Pasif raf geçmişte görünüyor fakat yeni harekette seçilemiyor.
- Birden fazla dolapta aynı raf adı olsa bile tam ad/kod belirsizlik yaratmıyor.
- Masaüstü ve mobil kullanımda seçim alanı gerçek lokasyon listesiyle doğrulanıyor.

---

## 5. Hareket geçmişinde CSV / Excel dışa aktarma

`/stok/hareketler/` üzerindeki aktif filtrelerle aynı kayıt kümesini dosya olarak
indiren “Dışa aktar” eylemi eklenecek. Kapsam ve kararlar için
[`DISA_AKTARIM_TASARIMI.md`](DISA_AKTARIM_TASARIMI.md) belgesine bakın.

### Yapılacaklar

- [ ] HTML liste ve dışa aktarma aynı filtreleme fonksiyonunu/queryset kurucusunu
  kullansın; arama, işlem tipi, kaynak/hedef lokasyon, kullanıcı ve tarih aralığı
  iki yerde kopyalanmasın.
- [ ] Dışa aktarmada sayfalama uygulama; filtrelenmiş kümenin tamamını
  `StreamingHttpResponse` ile satır satır üret.
- [ ] Tarihi `yerel_tarih()` üzerinden Europe/Istanbul saatinde yaz. Ham naive UTC
  kolonunu doğrudan dışa aktarma.
- [ ] Türkçe Excel uyumu için ayraç `;`, kodlama UTF-8 ve dosyanın başı BOM olsun.
- [ ] Stok kodu/açıklama/kullanıcı gibi metin alanlarının Excel formülü olarak
  yorumlanmasını engelle; `=`, `+`, `-` veya `@` ile başlayan hücreleri güvenli yaz.
- [ ] Dosya adı tarih içersin; uygulanan filtreler dosya içeriğinde veya adında
  anlaşılabilir olsun.

### Kabul ölçütleri

- Ekrandaki filtrelerle dosyadaki satırlar birebir aynı kayıt kümesini temsil ediyor.
- Tarih gün sınırlarında üç saat kaymıyor.
- Türkçe karakterler ve sütunlar gerçek Excel'de doğru açılıyor.
- Büyük sonuç kümesi bellekte bütünüyle tutulmuyor.
- Filtre yokken ve sonuç boşken geçerli dosya üretiliyor.

---

## ✅ 6. Stok & fason kullanım kolaylığı turu — tamamlandı (2026-08-05)

Migration 008'in ekranları ilk kez günlük depo işine göre düzenlendi. Kalıcı
kararlar:

- **Lokasyon listeleri iş amacına göre süzülüyor.** Süzme tablosu
  (`stok_merkezi.html`) `stok_islemi_kaydet()`'in kendi kontrollerinin aynası:
  fason sevkinde kaynak `DAHILI` / hedef `FASON`, dönüşte tersi, fire kaynağı
  `FASON`. Kural KOPYALANMADI, yalnız aynı kısıt POST'tan önce gösteriliyor;
  otorite hâlâ veritabanı. Yer değiştirmede `NUMUNE` bilerek listede kaldı —
  depo↔numune transferi madde 4'ün akışı, yalnız `DAHILI`'ya indirmek onu
  sessizce kapatırdı.
- **Stok durumu ve parti "Gelişmiş seçenekler" altında.** İkisi de günlük işte
  neredeyse hep varsayılanda (`SERBEST`, boş) kalıyordu; katlanmışlık yalnız
  görünüm, alanlar DOM'da ve POST'ta. İçlerinde hata varsa bölüm açık başlıyor.
- **Fason dönüşü ve fire tek formda.** Fire girildiğinde iki AYRI belge yazılıyor
  (veritabanı bir başlıkta tek `islem_nedeni` tutuyor) ama tek transaction
  içinde: fire reddedilirse dönüş de geri alınıyor, teslimat defterde yarım
  kalmıyor. Fire belgesinin istemci kimliği ilkinden `uuid5` ile TÜRETİLİYOR —
  rastgele olsaydı çift gönderimde dönüş atlanır, fire ikinci kez yazılırdı.
  Tamamı fire olan teslimatın yeri hâlâ ayrı "Fason fire kaydı" amacı.
- **Yeni SKU ekranında ürün kodu autocomplete.** Ayrı bir uç nokta
  (`urun_kodu_onerileri`), çünkü stok işlemindeki öneri `stok_kalemleri` içinde
  arıyor; "yeni varyant aç" ekranında aranan şey ise henüz varyantı OLMAYAN ürün.
- **Stok modülünün üç eylemi filtre barının üstünde buton oldu**
  (stok işlemi / yeni varyant / fason işleri); önceden ikisine ancak
  `/stok/islem/` üzerinden ulaşılıyordu. Ürün detayında da "+ Yeni varyant"
  ürün koduyla açılıyor.
- **Hareket geçmişinde iş amacı filtresi ve SKU/varyant sütunu.** Amaç belge
  BAŞLIĞINDAN filtreleniyor (`stok_islemleri.islem_nedeni`), teknik tipten değil:
  bir fason dönüşü CIKIS + GIRIS üretiyor ve tip filtresi o belgenin yalnız bir
  satırını bırakırdı. Fason ve fire satırları rozetli.
- **Ölü stok akışları silindi:** `stok_ekle`, `hizli_islem`, `_islem_baglami`,
  `_oneriler`, `_kodu_coz`, `_islem_urunu`, `_lokasyon_stok` ve
  `stok_islem.html`. Hiçbiri URL'den erişilemiyordu ve var olmayan bir forma
  (`StokEkleFormu`) / var olmayan parçalara (`_hizli_alan.html`) bağlıydılar.
  `stok_islem` view'ı yalnız eski derin bağlantıyı taşıyan yönlendirme olarak
  kaldı.

Renk ve hammadde açılır listeleri **migration 009 ortak veritabanına uygulanana
kadar boş kalmaya devam eder**; kod tarafında yapılacak bir şey yok.

---

## ✅ 2b. Rol/yetki ayrımı — tamamlandı

Migration 008 arayüzüyle birlikte Django izinleri ayrıldı:

- anonim kullanıcı: yalnız katalog;
- stok görüntüleyici: stok ve hareket salt-okuma;
- stok operatörü: görüntüleme + normal stok işlemi + sayım;
- fason sorumlusu: görüntüleme + normal işlem + fason iş emri/hareketi;
- stok yöneticisi: düzeltme dahil bütün stok yetkileri;
- `is_staff`: yönetim paneli ve geçiş süresince bütün stok yetkileri.

Roller Django gruplarıdır; asıl kapılar ayrı `stok_goruntule`, `hareket_goruntule`,
`stok_islem_yap`, `sayim_yap`, `duzeltme_yap`, `fason_yonet` izinleridir. HTML,
HTMX ve doğrudan URL aynı decorator/sorgu kontrolünü kullanır.

---

## Sırası gelmemiş / arka planda duranlar

- **Django otomatik test altyapısı:** Yetki/kanonik URL için veritabanısız hızlı
  testler var. Defter kabul testleri `veritabani/sql/tests/008_stok_urun_modeli_test.sql`
  içinde ve yalnız disposable kopyada çalışır; tam web akış testleri için izole
  METAKS DB fixture'ı hâlâ gerekir. Çekirdek SQL kabul turu geçti; sonradan eklenen
  parti, fason fire ve rollback korumaları için son forward + kabul + rollback
  turu ortak DB'ye geçmeden önce yeni restore edilmiş kopyada tekrarlanmalıdır.
- **Çoklu görsel galerisi:** veri ve kullanıcı ihtiyacı belirginleşene kadar tek ana
  görsel korunuyor.
- **Otomatik stok yenileme:** açık sekme kendiliğinden yenilenmiyor. Operasyonel
  ihtiyaç oluşursa katalogdan bağımsız olarak stok ekranında değerlendirilecek.
- **Telefon kamerasıyla kod okuma:** HTTPS ve gerçek donanım ihtiyacı netleşmeden
  yapılmayacak; klavye gibi çalışan USB/Bluetooth okuyucular mevcut stok işlem ekranıyla
  kullanılabilir.
- **Yayın/güvenlik:** DEBUG, SECRET_KEY, HTTPS, servis sunucusu, ACL, yedekleme ve
  Raspberry Pi işletimi burada tekrarlanmaz; kök güvenlik belgesinden izlenir.

---

## Tamamlanan karar kaydı

| Eski madde | Tarih | Sonuç ve kalıcı karar |
| --- | --- | --- |
| ✅ 0 — düşük-kod arayüz | 2026-07-31 | Appsmith projeden çıkarıldı; korunacak ikinci arayüz tüketicisi yok. |
| ✅ 1 — giriş akışı | 2026-08-04 | `/` giriş/misafir yönlendiricisi; katalog anonim, stok ve hareketler izinli kullanıcıya açık. |
| ✅ 2a — kullanıcı yönetimi | 2026-07-31 | Django auth + `is_staff`; kullanıcı adı/silme yerine hesap pasife alma ve parola yönetimi. |
| ✅ 2c — lokasyon yönetimi | 2026-07-31 | Hiyerarşik ekleme, pasife alma ve yalnız hiç kullanılmamış lokasyonda silme tamamlandı. |
| ✅ 3 — ürün ekleme/düzenleme | 2026-07-31 | İki ekran aynı formu ve tek `urun_kaydet()` yazma kapısını kullanıyor; giriş yeterli, `is_staff` gerekmiyor. |
| ✅ 3b — birleşik stok işlemi | 2026-08-04 | `/stok/ekle/` ve `/stok/hizli/` tek amaç-temelli `/stok/islem/` ekranına yönlendi; teknik giriş/çıkış seçimini sistem yapıyor. |
| ✅ ürün/SKU/fason modeli | 2026-08-04 | Ürün kodu model kimliği, SKU ticari varyant oldu; dış stok aynı defterde fason lokasyonu + iş emriyle izleniyor. Migration 008 ortak DB onayını bekliyor. |
| ✅ stok görünürlük ve roller | 2026-08-04 | Katalog açık kaldı; stok/hareket sorguları ayrı Django izinleri ve yönetim ekranındaki stok rolleriyle kapatıldı. |
| ✅ 6 — stok & fason kullanım turu | 2026-08-05 | Lokasyonlar iş amacına göre süzülüyor, fason dönüşü fireyi tek atomik akışta yazıyor, hareket geçmişi iş amacıyla filtreleniyor; kullanılmayan eski stok akışları silindi. |
| ✅ numune şema ön koşulu | 2026-07-30 | Ayrı varlık yerine lokasyon hiyerarşisi seçildi; migration 004 ve Django yaprak-lokasyon geçişi tamamlandı. |

Bir madde tamamlandığında açık bölümden kaldırıp bu tabloya tarih ve tek cümlelik
kalıcı gerekçeyle ekleyin. Canlı satır sayısı, kişisel cihaz durumu ve tek kullanımlık
test kontrol listeleri burada tutulmaz; bunlar gerektiğinde ölçülür veya Git
geçmişinden bulunur.
