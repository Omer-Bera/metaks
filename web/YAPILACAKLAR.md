# Yapılacaklar

Bu dosya arayüz tarafındaki açık işleri ve kısa karar kaydını tutar. Kalıcı teknik
kurallar [AGENTS.md](AGENTS.md), şema yol haritası
[`veritabani/docs/INFO.md`](../veritabani/docs/INFO.md), yayın ve güvenlik işleri ise
[Güvenlik ve yayına hazırlık](../GUVENLIK_VE_YAYINA_HAZIRLIK.md) içindedir.

Eski madde numaraları kod ve diğer belge referanslarını bozmamak için korunur.
Güncel uygulama sırası:

1. **Eski/belirsiz SKU bakiyesini fiziksel sayımla gerçek SKU'lara sınıflandırma**
2. **Madde 4 — gerçek numune dolap/raf düzeni**

Migration 008–009 2026-08-05'te, **010 ve 011 2026-08-06'da** her iki
`depo_sistemi` kopyasına da uygulandı; arayüz aynı gün `dev`'e alındı (ayrıntı ve
doğrulama kaydı [`veritabani/docs/INFO.md`](../veritabani/docs/INFO.md)). Bunun
arayüz tarafındaki doğrudan sonucu: 2.973 ürünün tamamı şu an tek bir miras
(BELIRSIZ) SKU taşıyor, yani stok işlem ekranında çoğu kodda "eski / belirsiz
varyant" rozeti ve "+ Bu ürüne yeni varyant aç" kısayolu görünüyor. Sıradaki iş
tam olarak bu: gerçek varyantları açıp bakiyeyi oraya taşımak.

⚠️ **Kendi makinesinde yerel `depo_sistemi` kopyası çalıştıran herkes 010 + 011'i
o kopyaya da uygulamalı.** `StokKalemi` modeli 010'un
`lak_mi` / `vernik_mi` / `iscilik_mi` kolonlarını, `stok_kalemi_kaydet()` çağrısı
da dokuz parametreli yeni imzayı kullanıyor; migration görmemiş bir kopyada stok
ekranları "column does not exist" verir.

⚠️ **İlk gerçek varyant açıldığı an 010'un geri dönüş kapısı kapanıyor.**
Rollback, yalnız lak/vernik/işçilik farkıyla ayrılmış `TANIMLI` SKU varsa baştan
durur. Bugün `TANIMLI` SKU sayısı sıfır, yani kapı hâlâ açık.

Madde 5 (dışa aktarma) ve madde 2b (rol ayrımı) tamamlandı; kararları aşağıda.

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

## 8. Gün sonu ekranı — sonraya bırakıldı

Depo sorumlusunun akşam kapanışta ihtiyaç duyduğu tek sayfa: o günün bütün stok
belgeleri ve hareketleri, o an dışarıda (fasonda) duran malın kimde/ne kadar/ne
zamandır/ne zaman beklendiği bilgisi ve çıktı alınabilir bir rapor.

Fikir 2026-08-06'da konuşuldu ve **bilerek şimdilik açık madde olarak** duruyor.
Ayrıntı, veri kaynakları, gün sınırı tuzağı, PDF seçeneklerinin maliyet
karşılaştırması ve henüz karara bağlanmamış noktalar ayrı belgede:
[`GUN_SONU_TASARIMI.md`](GUN_SONU_TASARIMI.md).

Şimdiden bilinen iki kısıt:

- Gün sınırı `models.yerel_tarih()` üzerinden kurulmalı; ham naive UTC kolonu
  00:00–03:00 arasındaki hareketleri bir önceki güne düşürür (madde 5'te bir kez
  ölçülmüş tuzağın aynısı).
- "Ne zamandır dışarıda" bilgisi `v_fason_is_emri_ozet`te yok; ilk `FASON_SEVK`
  belgesinin tarihinden türetilir. İlk sürümde Django tarafında tek gruplu
  sorgu yeterli, şema değişikliği gerektirmiyor.

---

## ✅ 5. Katalog, stok ve hareket dışa aktarma — tamamlandı (2026-08-04)

`/katalog/`, `/stok/` ve `/stok/hareketler/` ekranlarının her biri, o an açık
filtreleriyle aynı kayıt kümesini CSV veya XLSX olarak indiriyor. Kapsam ve
kararlar için [`DISA_AKTARIM_TASARIMI.md`](DISA_AKTARIM_TASARIMI.md). Kalıcı
kararlar:

- **Filtre sözleşmesi tek yerde.** `ListeFiltresi` ve `HareketFiltresi` hem HTML
  hem dosya yolunu besliyor; arama, işlem tipi, iş amacı, lokasyon, kullanıcı ve
  tarih aralığı kopyalanmıyor. Dışa aktarım madde 6'dan ÖNCE yazıldığı için
  birleştirmede iki yer ayrıca hizalandı: hareket amacı (`islem_nedeni`) filtresi
  `HareketFiltresi`'ne alındı ve stok dosyası `_stok_liste_sorgusu()` üzerinden
  ekranın kendi `StokBakiye`/`StokUrunOzet` sorgusuna bağlandı. Eski
  `v_toplam_stok` yolu bırakılsaydı dosya, kaplama/parti/fason filtrelerini hiç
  uygulamadan ekrandan BAŞKA bir küme indirirdi.
- **Sayfalama yok, akış var.** Filtrelenmiş kümenin tamamı `StreamingHttpResponse`
  ile satır satır üretiliyor (`iterator(chunk_size=2000)`), bellekte tutulmuyor.
- **Tarih `yerel_tarih()` üzerinden Europe/Istanbul.** Ham naive UTC kolonu dışa
  aktarılmıyor; gün sınırında üç saatlik kayma yok.
- **Türkçe Excel uyumu:** CSV ayracı `;`, kodlama UTF-8 ve dosyanın başında BOM.
- **Formül enjeksiyonu kapalı:** `=`, `+`, `-` veya `@` ile başlayan metin
  hücreleri `_metni_formulden_koru()` ile güvenli yazılıyor.
- **Dosya adı tarihli**, uygulanan filtreler dosyanın ilk satırındaki "Kapsam"
  bilgisinde okunabiliyor (`kapsam_ozeti()`).

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

Renk ve hammadde açılır listeleri migration 009 ile doldu (13 renk, 7 hammadde);
2026-08-05'te hem yerel hem ortak veritabanında doğrulandı.

---

## ✅ 7. Stok, SKU ve fason ekranları — migration 010 + 011 hizalaması (2026-08-06)

Ekranlar 010'un nitelik modeline ve 011'in iş kurallarına hizalandı. Kalıcı
kararlar:

- **Müşteri ve tedarikçi lokasyon DEĞİLDİR.** `lokasyonlar.tip` yalnız `DAHILI`,
  `FASON`, `NUMUNE` olmaya devam ediyor; karşı taraf `is_ortaklari` satırı.
  Dahili/Harici ayrımı SADECE görünüm: lokasyon listeleri Dahili / Numune /
  Dış atölye (fason) `<optgroup>`'larıyla basılıyor, `tip='FASON'` kodu
  değişmedi. Boş grup hiç basılmıyor — canlıda NUMUNE lokasyonu olmadığı için o
  grup bugün gerçekten boş (bkz. madde 4).
- **Amaç seçimi iki kademeli, aynı sayfada.** Üst kademe malın yönü (Mal giriyor
  / Mal çıkıyor / Diğer), alt kademe amaç. Yeni URL/view açılmadı, POST'a giden
  alan hâlâ tek `amac`; `?amac=` ve `?kod=` derin bağlantıları korunuyor. Bütün
  alt seçenekleri izne takılan bir üst kademe hiç gösterilmiyor.
- **Arayüzdeki her süzme veritabanındaki bir kuralın AYNASI.** Lokasyon tipi
  tablosu 011'in, karşı taraf rol tablosu 008 + 011'in kontrollerinin birebir
  kopyası; iş kuralı Python veya JS'te ikinci kez TANIMLANMADI. `DUZELTME`
  bilerek kısıtsız: fason lokasyonundaki bir hatanın da düzeltilebilmesi gerekiyor
  ve düzeltme oradan çıkışın tek yolu — oraya tesis-içi filtresi koymak o yolu
  sessizce kapatırdı.
- **Madde 6'daki "stok durumu katlandı" kararı BİLİNÇLİ olarak geri alındı.**
  Alan gelişmiş bölümden çıkıp üç düğmeli segment oldu (varsayılan `SERBEST`
  seçili). Katlandığı dönemde gerçekten hep varsayılanda kalıyordu, ama sebebinin
  bir kısmı görünmemesiydi: kalite bekleyen veya bloke mal girişi yapan personel
  alanı fark etmiyordu. Fason dönüşündeki İKİNCİ durum alanı gelişmişte kaldı —
  yalnız tek amaçta anlamlı.
- **Belge no taşınıyor, kopyalanmıyor.** Satın alma kabulü ve satış sevkiyatında
  görünür (mükerrer belge kilidinin anahtarı), diğer amaçlarda gelişmişe iniyor.
  İki kopya basmak aynı adı iki kez POST ederdi.
- **Dönecek SKU artık elle yazılmıyor, türetiliyor.** Depocu yapılacak işlemleri
  giriyor; sistem kaynak SKU'nun niteliklerine delta uygulayıp
  `stok_kalemi_kaydet()` ile bul-veya-oluştur yapıyor. SKU açma ve iş emri yazma
  TEK transaction'da: emir reddedilirse sahipsiz SKU kalmıyor. Kaynak SKU
  `BELIRSIZ` ise türetme yapılmıyor — nitelikleri bilinmeyen bir şeye delta
  uygulanamaz; kullanıcı "önce gerçek varyant aç" kısayoluna yönlendiriliyor.
- **Fason lokasyonu gizli.** Fasoncunun tek atölyesi otomatik seçiliyor; birden
  fazlaysa alan geri görünüyor. Şemanın izin verdiği çoklu durum sessizce
  varsayılmıyor.
- **`islem_turu` tek değerli kaldı, alt tablo açılmadı.** Tek işlem seçildiyse
  onun türü, birden fazlaysa `DIGER`; ayrıntı `aciklama`'ya yazılıyor.
- **Yeni "SKU niteliği" filtresi: Ham / İşlem görmüş / Eski-belirsiz.** Kod
  değeri `ISLENMEMIS` — `HAM` DEĞİL, çünkü 010 tam olarak bu kelimenin iki
  anlama gelmesini düzeltti; kullanıcıya gösterilen etiket "Ham" olarak kalıyor.
  `kaplama_id IS NULL = ham` YAZILMADI: miras SKU'ların hepsinde kaplama NULL,
  öyle yazılsaydı filtre bütün katalogu ham gösterirdi. Aynı sebeple `BELIRSIZ`
  satırlarda `lak_mi = FALSE` "laksız" diye okunmuyor — 010 o kolonlara varsayılan
  koydu, bilgi koymadı. Süzme `v_stok_bakiye` üzerinden YAPILAMIYOR (view 008'de
  tanımlandı, yeni kolonları taşımıyor); ham `stok_kalemleri` üzerinden alt
  sorguyla yapılıyor.
- **Dışa aktarım hizası korundu.** Yeni filtre `kapsam_ozeti()`'ne girdi ve dosya
  ekranla aynı kümeyi indiriyor (üç değerde de ölçüldü). Dışa aktarım SÜTUNLARI
  değişmedi: stok dosyası ürün kırılımında, SKU nitelikleri o kırılıma sığmıyor —
  bu yüzden `DISA_AKTARIM_TASARIMI.md` güncellenmedi.
- **Ölü kod:** `stok_servisi.hareket_kaydet()` silindi (Django tarafında çağıranı
  yoktu). SQL'deki `stok_hareketi_kaydet()` sarmalayıcısına dokunulmadı — o
  veritabanının dış yüzeyi.

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

- **Django otomatik test altyapısı:** Yetki/kanonik URL ve dışa aktarım testleri
  saf `SimpleTestCase` — veritabanı kurmadan çalışıyor. ORM entegrasyonları için
  güvenli fixture/test şeması tasarlanmadan test runner'ını paylaşılan
  `depo_sistemi`ne karşı çalıştırmayın. Defter kabul testleri
  `veritabani/sql/tests/008_stok_urun_modeli_test.sql` içinde ve yalnız disposable
  kopyada çalışır; tam web akış testleri için izole METAKS DB fixture'ı hâlâ
  gerekir. Parti, fason fire ve rollback korumalarını da kapsayan son forward +
  kabul + rollback turu 2026-08-05'te YAPILDI: ortak veritabanının yedeğinden
  kurulan tek kullanımlık kopyada 008 ileri, 17 assertion'lık kabul testi, 009
  ileri + rollback ve 008 rollback çalıştırıldı; testin sessizce geçmediği 008
  uygulanmamış bir kopyada hata verdirilerek doğrulandı (bkz. 11eeffe).
- **Konsinye / emanet mal bilerek modelin dışında (2026-08-06):** müşteride ve
  tedarikçide METAKS'a ait duran mal GERÇEKTEN var, ama şimdilik "yokmuş gibi"
  ilerleniyor — kapsamı şişirmemek için alınmış bilinçli karar. Madde 7'deki
  "müşteri ve tedarikçi lokasyon değildir" kararının gerekçesi budur. Ayrım
  mülkiyette: fasondaki malın mülkiyeti devrolmuyor (o yüzden lokasyon), satılan
  malınki devroluyor. Müşteri lokasyon yapılsaydı satılan mal `v_stok_bakiye`'de
  sonsuza kadar bakiye olarak dururdu ve `v_stok_urun_ozet.sahip_olunan_toplam`
  artık bize ait olmayanı da sayardı; kimsenin saymayacağı, hiç kapanmayacak bir
  bakiye birikirdi. "Mal kime gitti / kimden geldi" sorusunun cevabı bugün
  lokasyon değil **belge başlığı** (`stok_islemleri.is_ortagi_id`); hareket
  geçmişi bunu zaten gösteriyor. Karar geri alınırsa doğru yol "Müşteri" tipi
  lokasyon açmak DEĞİL, bir iş ortağına bağlı ayrı bir `KONSINYE` lokasyon tipi
  eklemektir — mülkiyet ayrımı orada da korunur. Aynı sınırın ikinci yarısı:
  bugün bir fasoncunun tek atölyesi var, yani fason iş emrindeki lokasyon seçimi
  pratikte tek seçenekli. Şema çoklu lokasyonu destekliyor
  (`lokasyonlar.is_ortagi_id`), değiştirmeye gerek yok; madde 7'de alanın
  gizlenmesi buna dayanıyor ve ikinci bir atölye açıldığı gün alan kendiliğinden
  geri geliyor.

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
| ✅ 5 — filtreli CSV/Excel dışa aktarım | 2026-08-04 | Katalog, stok ve hareket ekranları aynı filtre sorgularından sayfalamasız dosya üretiyor; CSV akışlı, XLSX write-only/geçici dosyalı ve anonim okuma davranışı korundu. |
| ✅ 7 — stok/SKU/fason ekranlarının 010+011 hizalaması | 2026-08-06 | Amaç seçimi iki kademeli oldu, iadeler menüye girdi, lokasyon ve karşı taraf süzmeleri 011'in birebir aynası yapıldı, dönecek SKU elle yazılmak yerine türetiliyor ve `HAM` her yerde `DEMONTE` oldu; arayüz artık migration 010'u zorunlu kılıyor. |
| ✅ 010 + 011'in uygulanması | 2026-08-06 | İki `depo_sistemi` kopyasına da (önce yerel Docker, doğrulama sonrası Pi) yedek + prova + açık onayla uygulandı ve arayüz aynı gün `dev`'e alındı; şema değişikliği ile ona bağımlı kod arasındaki pencere kapatıldı. |

Bir madde tamamlandığında açık bölümden kaldırıp bu tabloya tarih ve tek cümlelik
kalıcı gerekçeyle ekleyin. Canlı satır sayısı, kişisel cihaz durumu ve tek kullanımlık
test kontrol listeleri burada tutulmaz; bunlar gerektiğinde ölçülür veya Git
geçmişinden bulunur.
