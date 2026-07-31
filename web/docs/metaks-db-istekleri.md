Bu prompt `~/metaks_DB` reposunda yeni bir Claude Code oturumunda kullanılmak üzere yazıldı.

---

`depo-web-arayuz` (Django+HTMX arayüzü) tarafında sıradaki iki modül için şema
tarafında hazırlık gerekiyor. Şema otoritesi bu repo olduğu için tasarımı ve
migration'ları burada yapmak istiyorum. Aşağıdaki ölçümleri ben canlı `depo_sistemi`
üzerinde yaptım, ama hepsini kendin doğrula — yanılmış olabilirim.

Her iki iş için de bu reponun mevcut disiplini geçerli: numaralı migration +
ayrı rollback dosyası, `BEGIN/COMMIT`, önce `BEGIN...ROLLBACK` ile test sonra
kullanıcı onayıyla uygula. Uygulamadan önce bana ne yapacağını anlat.

# İş 1 — Numune lokasyonları (raf düzeyinde)

## İhtiyaç

Ürünlerin numuneleri showroom'da dolaplarda/raflarda duruyor. "Bu ürünün numunesi
nerede?" sorusunun cevabı **kütüphanede kitap bulur gibi** olmalı: "Numune Dolabı 1 –
Raf 3". Kaç dolap/raf olacağı henüz belli değil, zamanla artacak ve yeniden
düzenlenecek.

`docs/INFO.md`'deki "Faz 8: Numune takibi" notu bunun ayrı bir varlık gerektireceğini,
çünkü numunelerin `urunler`'in "sadece değişmeyen fiziksel öznitelikler" ilkesine
uymadığını söylüyor. Gerekçeye katılıyorum ama o gerekçe **numune yerinin `urunler`
üzerinde bir kolon olmasını** eliyor — ki olmamalı. Bense numunenin zaten var olan
`lokasyonlar` + `stok_hareketleri` mekanizmasına oturduğunu düşünüyorum: numune,
fiziksel olarak ürünün bir adedinin bir yerde durmasıdır; "depodan numune dolabına
taşındı" da tam olarak bir TRANSFER'dir. Böylece numune ödünç alınıp geri konduğunda
kaydı da bedavaya gelir. Bu değerlendirmeye katılmıyorsan söyle, gerekçeni duymak
istiyorum.

## Önerdiğim şema değişikliği

1. **`lokasyonlar_tip_check` genişletilsin:** bugün sadece `DAHILI` / `FASON` kabul
   ediyor, `NUMUNE` eklensin.

2. **Hiyerarşi ve kısa adres kolonları:**
   ```sql
   ALTER TABLE lokasyonlar
     ADD COLUMN ust_lokasyon_id INT NULL REFERENCES lokasyonlar(lokasyon_id),
     ADD COLUMN kod VARCHAR(20) NULL;
   CREATE UNIQUE INDEX uq_lokasyonlar_kod ON lokasyonlar(kod) WHERE kod IS NOT NULL;
   ```
   - Dolap: `lokasyon_adi='Numune Dolabı 1'`, `kod='N1'`, `tip='NUMUNE'`, `ust_lokasyon_id=NULL`
   - Raf: `lokasyon_adi='Raf 3'`, `kod='N1-R3'`, `tip='NUMUNE'`, `ust_lokasyon_id=<N1'in id'si>`
   - Mevcut 8 lokasyon (`Metaks`, `Depo 1`, `Fabrika`, `Kaplama`, `Skor` ve 3 pasif)
     `ust_lokasyon_id=NULL, kod=NULL` kalır — hiçbiri etkilenmez.

   **Neden düz isimlendirme değil** ("Numune Dolabı 1 – Raf 3" tek satır olarak):
   dolap sayısı belirsiz ve yeniden düzenleneceği söylendi. Düz isimle bir dolabı
   yeniden adlandırmak N satır güncellemek demek, hiyerarşide tek satır. Ayrıca
   "Dolap 1'de ne var" sorgusu string önekine (`kod LIKE 'N1-%'`) bağlı kalmaz.
   Karşı görüşün varsa değerlendir — `kod` tek başına da çoğu ihtiyacı karşılıyor.

   **Derinlik bilerek 2 seviye** (dolap → raf). Genel amaçlı ağaç kurma; ihtiyaç
   yok ve recursive CTE'yi her sorguya bulaştırır.

3. **Sadece yaprak lokasyona hareket yazılabilsin.** "Numune Dolabı 1"e stok
   yazılması anlamsız, raflara yazılmalı. Bunu yeni bir kolonla değil,
   `stok_hareketi_kaydet()` içinde bir kontrolle çözmeyi öneriyorum (alt lokasyonu
   olan bir lokasyon hedef/kaynak olarak verilirse Türkçe `RAISE EXCEPTION`) —
   yazmanın tek kapısı zaten orası. v1 için opsiyonel, senin kararın.

4. **Görüntüleme için yol/etiket.** Arayüzün "Numune Dolabı 1 · Raf 3" basabilmesi
   için `v_lokasyon_stok_ozet`'e (ya da ayrı küçük bir view'a) `kod` ve birleşik
   ad gelmeli. Derinlik 2 olduğu için basit bir self-join yeterli.

## ⚠️ Dikkat — bu değişikliğin canlı Appsmith'i kırdığı yer

`depo-appsmith-arayuz` hâlâ aktif kullanımda ve devam eden depo sayımı onun üzerinden
yürüyor. İki gerçek çarpışma var:

**(a) `StokIslemi` lokasyon açılır listesi dolar.** Şu iki sorgunun ikisinde de
**tip filtresi yok**:

- `pages/StokIslemi/queries/LokasyonlariGetir` → `SELECT lokasyon_id, lokasyon_adi, tip FROM lokasyonlar WHERE aktif_mi = true ORDER BY lokasyon_adi`
- `pages/LokasyonYonetimi/queries/LokasyonlarListele` → aynı sorgu

Numune rafları eklendiği anda bunlar bugün 5 satır dönerken onlarca satır dönmeye
başlar ve **sayımın yapıldığı ekranın lokasyon kutusu kullanılamaz hâle gelir.**

Bu yüzden **sıra önemli**: önce Appsmith sorgularına tip filtresi eklenmeli
(`AND tip IN ('DAHILI','FASON')` ya da hiyerarşi için "yaprak olanlar"), **sonra**
numune lokasyonları oluşturulmalı. Migration'ı uygulamadan önce bunu kullanıcıya
hatırlat.

Ayrıca `pages/LokasyonYonetimi/widgets/YeniLokasyonTipiSelect.json` tip listesini
sabit gömüyor (`Dahili`/`Fason`) — yeni tip orada görünmeyecek. Kırılma değil,
eksiklik; Appsmith'ten numune lokasyonu eklenemeyeceği anlamına gelir.

**(b) `v_toplam_stok` numuneleri satılabilir stok sayar.** Bugünkü tanım lokasyon
tipine **hiç bakmadan** hepsini topluyor:

```sql
SELECT stok_kodu, sum(mevcut_miktar) FROM v_lokasyon_stok_ozet GROUP BY stok_kodu;
```

Bu view'ın Appsmith'teki dört tüketicisinin **hepsi "satılabilir stok" anlamında**
kullanıyor:

| Yer | Kullanım |
| --- | --- |
| `YonetimAnaSayfasi/OzetIstatistikler` | `SUM(toplam_miktar)` = toplam stok miktarı |
| `YonetimAnaSayfasi/OzetIstatistikler` | `toplam_miktar < kritik_stok_esigi` → kritik ürün sayısı |
| `StokOzet/StokOzetGetir` | aynı kritik stok karşılaştırması |
| `UrunlerKatalog/KatalogUrunleriGetir` | "Sadece stokta olanlar" filtresi |

Vitrindeki 2 numune yüzünden bir ürünün "kritik değil" görünmesi yanlış olur.

**Önerim:** `v_toplam_stok` **`NUMUNE` tipini hariç tutacak şekilde güncellensin**,
fiziksel toplamı isteyen için yanına ayrı bir view eklensin (`v_fiziksel_stok` vb.).
Böylece yukarıdaki dört tüketici **tek satır değişiklik olmadan doğru kalır**.

Bunun "var olan bir view'ın anlamını sessizce değiştirmek" olduğunun farkındayım —
normalde karşı çıkardım. Burada savunulabilir buluyorum çünkü henüz hiç `NUMUNE`
lokasyonu yok, yani değişiklik **bugün sonucu hiç değiştirmiyor** (iki tanım da birebir
aynı satırları döndürür, bunu doğrula), ve aynı migration'da yapılırsa iki tanım hiç
ayrı yaşamıyor. Alternatif (v_toplam_stok fiziksel kalsın, yeni view satılabilir olsun)
dört Appsmith sorgusunun da düzeltilmesini gerektirir ve düzeltilmeyen biri sessizce
yanlış cevap verir. Yine de karar senin; `docs/aktif-urun-veri-sozlesmesi.md`
güncellenmeli, çünkü iki arayüz de o sözleşmeyi okuyor.

## Zamanlama notu

Devam eden sayım bu işi aciliyetli kılıyor: numune dolabını açıp 3 adet bulan kişinin
bunu yazacağı dürüst bir yer bugün yok — ya hiç yazılmıyor ya da bir depo lokasyonuna
karışıyor. Yani bu, sayım bittikten sonra eklenecek bir süs değil, sayımın doğruluğunu
etkileyen bir eksik.

# İş 2 — `urun_kaydet()` fonksiyonu

## Sorun

Django arayüzüne ürün ekleme/düzenleme ekranı yapacağım. Ama `urunler`'e satır
eklemek **yetmiyor, ürün görünmez kalıyor**:

- Yeni satır `katalog_durumu` varsayılanı olan `'PASIF'` ile doğuyor ve öyle kalıyor.
  Bu kolonu yöneten **hiçbir trigger yok** (`urunler`, `urun_gorselleri`,
  `stok_hareketleri` üzerinde trigger sayısı sıfır — doğrula), AKTİF ataması
  `sql/migrations/001_katalog_durumu.sql`'deki **tek seferlik backfill UPDATE**'ti.
- `chk_urunler_katalog_durumu_aktif_mi_tutarli` kısıtı `katalog_durumu` ile
  `aktif_mi`'nin birlikte hareket etmesini zorunlu kılıyor.
- `v_aktif_urunler` sadece `katalog_durumu='AKTIF'` satırları veriyor, yani yeni ürün
  hiçbir arayüzde görünmez.

Yani ekleme bölünemez bir bütün: ana görsel satırı + `urunler` satırı + AKTİF'e
geçiş, **tek transaction'da**. Yarısı olursa ya görünmez ürün ya kırık görsel kalır.

## İstediğim

`stok_hareketi_kaydet()` ile **aynı desende** bir `urun_kaydet()` fonksiyonu: iş
kuralı veritabanında tek yerde dursun, Appsmith ve Django aynı kuralı paylaşsın,
Türkçe `RAISE EXCEPTION` mesajları doğrudan kullanıcıya gösterilebilsin. Django
tarafındaki katman (`katalog/stok_servisi.py` gibi) sadece parametre geçirip dönen
mesajı taşıyacak, hiçbir kuralı tekrar etmeyecek.

Karşılaması gerekenler (eksik/fazla gördüğünü söyle):

- Yeni ürün ekleme **ve** mevcut ürünü güncelleme (ya tek fonksiyon ya ikisi ayrı).
- Ana görsel verildiğinde `urun_gorselleri`'ne `ana_gorsel_mi=true, aktif_mi=true`
  satırı + `urunler`'i `katalog_durumu='AKTIF', aktif_mi=true` yapma; verilmediğinde
  ürünün `PASIF` kalması (bu bir hata değil, taslak ürün).
- Doğrulamalar: `stok_kodu` zaten var mı (PK, ama mesaj anlaşılır olsun),
  `kategori_id`/`hammadde_id`/`kaplama_id` gerçekten var mı, `urun_tipi` izinli
  değerlerden mi, `parent_stok_kodu` verilmişse mevcut mu.
- Zorunlu alan sadece `stok_kodu`; kalanların hepsi NULL kabul ediyor ya da
  varsayılanı var. Kataloğun işe yaraması için pratikte gereken çekirdek ise
  stok kodu + kategori + ölçü + ana görsel — bunlardan hangilerini şema düzeyinde
  zorunlu saymak istediğini konuşalım.

## Görsel dosyası — DB dışında kalan kısım

Fonksiyon dosya yazamaz. Mevcut düzen:

- Dosyalar `~/metaks_DB/images/final/products` altında, adlandırma
  `<stok_kodu>_<sira_no>.<uzantı>` (`1001013_1.png`, `100012_1.jpg`).
- `docker-compose.yml`'de nginx'e **`:ro`** olarak bağlı, yani yazan taraf host.

Sorularım:

1. Django'nun bu dizine yazmasını uygun buluyor musun, yoksa yükleme ayrı bir
   dizine mi düşmeli? Dizinin sahibi bu repo, o yüzden karar senin.
2. Uzantı/isim kuralı ne olmalı — aynı ürüne ikinci görsel gelirse `sira_no` nasıl
   belirlenecek?
3. Yerelde izin sorunu yok (`drwxr-xr-x omerzerenuz:staff`), ama ileride VPS'e
   taşınırsa bu bağlantı yeniden düşünülmeli — not düşülsün.

Django tarafında sıralamayı **önce dosya, sonra DB** yapmayı planlıyorum: fonksiyon
hata verirse yazdığım dosyayı silerim. Tersi sırada çökme olursa DB'de var olmayan
dosyayı gösteren kırık ürün kalır; bu sırada ise en kötü ihtimalle sahipsiz bir dosya
kalır ki zararsız. Daha iyi bir fikrin varsa söyle.

## Denetim izi

`stok_hareketleri`'nde `yapan_kullanici` var ama `urunler`'de kim ekledi/değiştirdi
bilgisi yok. Bunu bu işin kapsamına almak ister misin, yoksa ayrı mı tutalım?

# Bitirirken

- `docs/aktif-urun-veri-sozlesmesi.md` her iki iş için de güncellenmeli — iki arayüz
  de o sözleşmeyi okuyor, ben Django tarafını ona göre yazacağım.
- Değişen/eklenen view ve fonksiyon imzalarını bana net biçimde bildir (kolon adları,
  parametre sırası, dönüş tipleri), `depo-web-arayuz` tarafını ona göre yazacağım.
