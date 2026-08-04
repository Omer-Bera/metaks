# Yapılacaklar

Bu dosya arayüz tarafındaki açık işleri ve kısa karar kaydını tutar. Kalıcı teknik
kurallar [AGENTS.md](AGENTS.md), şema yol haritası
[`veritabani/docs/INFO.md`](../veritabani/docs/INFO.md), yayın ve güvenlik işleri ise
[Güvenlik ve yayına hazırlık](../GUVENLIK_VE_YAYINA_HAZIRLIK.md) içindedir.

Eski madde numaraları kod ve diğer belge referanslarını bozmamak için korunur.
Güncel uygulama sırası:

1. **Madde 4 — numune arayüzü ve gerçek dolap/raf düzeni**
2. **Madde 5 — filtreli CSV/Excel dışa aktarma**
3. **Madde 2b — rol ayrımı**, dış/fason kullanıcı sisteme girene kadar erteli

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
- [ ] Ürün stok detayında satılabilir stok ile numuneyi ayrı özetle; örneğin
  “N adet satılabilir · M numune”. Toplamların kaynağı doğru view olmalı.
- [ ] Ürün detayında “Numunesi nerede?” bilgisini `v_numune_konumlari` üzerinden
  doğrudan görünür yap; dolap + raf kodu/adı birlikte gösterilsin.
- [ ] Transfer ekranında numune raflarını anlaşılır etiketle; kök dolabın seçilebilir
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
indiren “Dışa aktar” eylemi eklenecek.

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

## 2b. Rol/yetki ayrımı — ertelendi

Bugünkü kapılar:

- anonim kullanıcı: katalog, stok ve hareket geçmişinde salt-okunur erişim;
- giriş yapmış kullanıcı: ürün ve stok yazma işlemleri;
- `is_staff`: kullanıcı ve lokasyon yönetimi.

Depo personeli, yönetici, salt-okunur personel ve fason/dış kullanıcı için ince
izin modeli henüz tasarlanmadı. İç ekip dışına hesap verilene kadar yeni rol tablosu
veya izin matrisi eklenmeyecek.

Bu maddeyi yeniden açan olay dış/fason kullanıcıya hesap verilmesi veya anonim
ekranların şirket verisi nedeniyle kapatılmasıdır. O zaman stok işlem tipleri,
lokasyon kapsamı, ürün düzenleme, dışa aktarma ve yönetim eylemleri ayrı ayrı izin
matrisine dökülmeli; güvenlik kararları kök güvenlik belgesiyle birlikte ele alınmalı.

---

## Sırası gelmemiş / arka planda duranlar

- **Otomatik test altyapısı:** `katalog/tests.py` boş. Canlı `depo_sistemi`ne test
  DB'si oluşturmayan güvenli bir fixture/test şeması tasarlanmadan test runner'ı
  paylaşılan veriye karşı çalıştırılmamalı.
- **Çoklu görsel galerisi:** veri ve kullanıcı ihtiyacı belirginleşene kadar tek ana
  görsel korunuyor.
- **Otomatik stok yenileme:** açık sekme kendiliğinden yenilenmiyor. Operasyonel
  ihtiyaç oluşursa katalogdan bağımsız olarak stok ekranında değerlendirilecek.
- **Telefon kamerasıyla kod okuma:** HTTPS ve gerçek donanım ihtiyacı netleşmeden
  yapılmayacak; klavye gibi çalışan USB/Bluetooth okuyucular mevcut hızlı ekranla
  kullanılabilir.
- **Yayın/güvenlik:** DEBUG, SECRET_KEY, HTTPS, servis sunucusu, ACL, yedekleme ve
  Raspberry Pi işletimi burada tekrarlanmaz; kök güvenlik belgesinden izlenir.

---

## Tamamlanan karar kaydı

| Eski madde | Tarih | Sonuç ve kalıcı karar |
| --- | --- | --- |
| ✅ 0 — düşük-kod arayüz | 2026-07-31 | Appsmith projeden çıkarıldı; korunacak ikinci arayüz tüketicisi yok. |
| ✅ 1 — giriş akışı | 2026-07-30 | `/` giriş/misafir yönlendiricisi oldu; salt-okunur ekranlar anonim kalırken yazma giriş istiyor. |
| ✅ 2a — kullanıcı yönetimi | 2026-07-31 | Django auth + `is_staff`; kullanıcı adı/silme yerine hesap pasife alma ve parola yönetimi. |
| ✅ 2c — lokasyon yönetimi | 2026-07-31 | Hiyerarşik ekleme, pasife alma ve yalnız hiç kullanılmamış lokasyonda silme tamamlandı. |
| ✅ 3 — ürün ekleme/düzenleme | 2026-07-31 | İki ekran aynı formu ve tek `urun_kaydet()` yazma kapısını kullanıyor; giriş yeterli, `is_staff` gerekmiyor. |
| ✅ 3b — hızlı stok işlemi | 2026-07-31 | Kod/barkod, öneri, ürün formu ve kayıt döngüsü URL değiştirmeyen tek sayfada birleşti; PASİF ürünler de işleniyor. |
| ✅ stok kovası ve stok ekle | 2026-08-02 | Kaplama/çeşit/montaj ürün özelliği değil stok kovası oldu; `/stok/ekle/` mal kabul ekranı eklendi. |
| ✅ numune şema ön koşulu | 2026-07-30 | Ayrı varlık yerine lokasyon hiyerarşisi seçildi; migration 004 ve Django yaprak-lokasyon geçişi tamamlandı. |

Bir madde tamamlandığında açık bölümden kaldırıp bu tabloya tarih ve tek cümlelik
kalıcı gerekçeyle ekleyin. Canlı satır sayısı, kişisel cihaz durumu ve tek kullanımlık
test kontrol listeleri burada tutulmaz; bunlar gerektiğinde ölçülür veya Git
geçmişinden bulunur.
