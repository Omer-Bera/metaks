# 🗄️ METAKS DB

METAKS metal tekstil aksesuarları kataloğunun temizlenmesi, standartlaştırılması, PostgreSQL veritabanına aktarılması ve ürün görsellerinin stok kodlarıyla eşleştirilmesi için hazırlanan veri altyapısı projesidir.

Bu depo; ürün ana verisini, veri temizleme scriptlerini, PostgreSQL şemasını, migration sürecini, ürün görsellerini ve geçmiş çalışma çıktılarının arşivini içerir.

---

## ✅ Mevcut Durum

Tamamlanan çalışmalar:

- Kategori adlarının standartlaştırılması
- Stoklu, stoksuz ve karmaşık ürünlerin ayrıştırılması
- Ölçü alanlarının sayısal formata dönüştürülmesi
- Parent-child ürün ilişkilerinin kurulması
- Kalıp göz sayısı bilgilerinin ürün ana verisinden ayrılması
- PostgreSQL şemasının hazırlanması
- Nihai ürünlerin PostgreSQL'e aktarılması
- Excel içindeki ürün görsellerinin stok kodlarıyla eşleştirilmesi
- Üst üste duran ve hatalı konumlandırılmış görsellerin manuel kontrolü
- Nihai görsel arşivinin oluşturulması

Nihai görsel arşivinde **2.733 ürün görseli** bulunmaktadır.

> **2026-07-28 güncellemesi:** 857 karışık satırın stok kodu ayrıştırma/normalizasyon işi tamamlandı (bkz. `docs/karisik_stok_kodu_kurali.md`), 1.142 yeni varyant veritabanına yüklendi (toplam **2.973 ürün**). Kalan 216 çözülemeyen karışık kod, 66 hiç işlenmemiş "ölçü karmaşık" satır, 6 stoksuz satır ve dosya adı eski birleşik kod listesini kullandığı için eşleşmeyen 934 görsel — bilinçli bir kapsam kararıyla **arşivlendi** (silinmedi): ürün tarafı `data/reference/arsivlenen_eski_urunler.xlsx`'e, görseller `images/arsiv/products/`'a taşındı. Gerekçe: bu kayıtlar büyük olasılıkla çok eski/düşük cirolu ürünler; aktif sistemi bunlarla şişirmek yerine temiz, çalışan bir sisteme odaklanmayı tercih ettik. Aktif görsel klasörü artık DB ile **%100 eşleşiyor** (1.799/1.799).

---

## ⭐ Nihai Veri Seti

Aşağıdaki dosya ve klasörler projenin güncel ve güvenilir ana veri setidir:

```text
data/raw/urun_listesi.xlsx
data/processed/temiz_urunler_final_v2.xlsx
data/reference/kalip_bilgileri_yedek.xlsx
images/final/products/
```

`data/processed/temiz_urunler_final_v2.xlsx` içindeki **2.973 satır**, `scripts/database/yukle.py` ile PostgreSQL'e yüklenmiş olan güncel nihai veridir (2.969 ANA_URUN, 3 ALT_PARCA, 2 VARYANT). Bu dosya, standart temiz veri + `karisik_urunleri_coz.py`/`karisik_urunleri_birlestir.py` ile çözülen 1.142 karışık-kod varyantının birleşimidir. `data/interim/temiz_urunler_standart.xlsx` artık ara bir aşamadır (bkz. Normalizasyon Hattı bölümü); doğrudan referans alınmamalıdır. Eski `temiz_urunler_final_v1.xlsx` (1.831 satır, karışık kodlar hariç) tarihsel referans olarak korunuyor.

### `data/raw/urun_listesi.xlsx`

Ürün kataloğunun görselleri düzeltilmiş nihai Excel kaynağıdır.

Bu dosyada:

- ürün satırları,
- stok kodları,
- ürün açıklamaları,
- Excel içine gömülü ürün görselleri

bulunur.

Görsel eşleme işlemi bu dosya esas alınarak yapılmıştır. Dosya, görsel konumlarının ve ilişkilerinin korunması için ana klasörde saklanmalıdır.

### `data/interim/temiz_urunler_standart.xlsx`

Temizlik hattının (Aşama 1) çıktısıdır; ölçüleri sayısal, kategorileri standart hale getirilmiş ama henüz normalize edilmemiş ürün verisidir.

Bu dosyada:

- standart kategori adları,
- sayısal ölçü alanları,
- açıklama alanları

bulunur. Stok kodları bu aşamada henüz tekil değildir — birleşik/tekrar eden kodlar Normalizasyon Hattı'nda (`scripts/normalization/`, `scripts/maintenance/`) çözülür.

### `data/processed/temiz_urunler_final_v2.xlsx`

PostgreSQL'e aktarılmış olan gerçek nihai veridir (**2.973 satır**). Normalizasyon Hattı'nın son adımı olan `final_excel_hazirla.py` tarafından üretilir; tekil stok kodları, parent-child/varyant ilişkileri ve `scripts/database/yukle.py`'nin beklediği tüm kolonları içerir. Girişi artık `temiz_urunler_tekrarsiz_v2.xlsx` değil, `karisik_urunleri_birlestir.py`'nin ürettiği `data/interim/temiz_urunler_karisik_dahil.xlsx`'tir.

### `data/reference/kalip_bilgileri_yedek.xlsx`

Ürünlerden ayrılan kalıp göz sayısı bilgilerinin stok kodlarıyla birlikte tutulduğu güvenli yedektir.

Bu veri ileride geliştirilecek Kalıp Modülü için korunmaktadır.

### `images/final/products/`

Stok kodlarıyla adlandırılmış nihai ürün görsellerini içerir (2.733 dosya). Çalışma/kontrol aşaması için kullanılan kopya `images/working/products/` klasöründedir; ham eşleme raporu (`gorsel_esleme_raporu.csv`) o klasörde tutulur, derlenmiş/özetlenmiş hâli ise `reports/excel/gorsel_eslesme_raporu.xlsx`'tir.

Bu rapor; Excel satırı, stok kodu, kaynak medya dosyası, oluşturulan dosya adı ve işlem durumunu kayıt altına alır.

> Bu klasör elle yeniden adlandırılmamalı veya eski görsel klasörleriyle birleştirilmemelidir.

---

## 📂 Ana Klasör Yapısı

```text
metaks_DB/
├── archive/                    # kullanılmayan eski dosyalar (bkz. Arşiv Yapısı)
├── data/
│   ├── raw/                    # urun_listesi.xlsx (görsel gömülü, ~195 MB)
│   ├── interim/                 # temizlik/normalizasyon ara dosyaları
│   ├── processed/                # temiz_urunler_final_v2.xlsx (DB'ye yüklenen)
│   └── reference/                 # kalip_bilgileri_yedek.xlsx vb.
├── docs/INFO.md                    # bu dosya
├── docker-compose.yml
├── images/
│   ├── working/products/            # işlem gören görseller + gorsel_esleme_raporu.csv
│   └── final/products/               # nihai 2.733 ürün görseli
├── init_db.sql                        # eski şema (docker-compose tarafından kullanılmıyor)
├── reports/excel/                      # kontrol ve dönüşüm raporları
├── scripts/
│   ├── cleaning/                        # temizle.py, olcu_temizle.py, duzelt.py, ayir.py
│   ├── normalization/                    # birlesik_stok_kodlarini_duzelt.py, final_excel_hazirla.py
│   ├── maintenance/                       # kalip_yedekle.py, *_tekrarlarini_sil.py
│   ├── database/                           # yukle.py
│   └── images/                              # gorsel_esle_duzeltilmis_v2.py ve türevleri
├── sql/01_schema.sql                    # GÜNCEL şema (docker-compose tarafından kullanılıyor)
└── venv/
```

---

## 🐍 Python Scriptleri

### Veri temizleme hattı

Scriptlerin temel çalışma sırası (gerçek script yolları `scripts/` altındadır, bkz. Ana Klasör Yapısı):

```text
temizle.py
→ olcu_temizle.py
→ duzelt.py
→ kalip_yedekle.py
→ ayir.py
→ birlesik_stok_kodlarini_duzelt.py
→ ayni_urun_tekrarlarini_sil.py
→ secili_stok_tekrarlarini_sil.py
→ final_excel_hazirla.py
→ yukle.py
```

`ayir.py`'den sonraki dört script (Normalizasyon Hattı) pipeline'a sonradan eklendi; birleşik/tekrar eden stok kodlarını çözüp veritabanına yüklenecek son dosyayı (`temiz_urunler_final.xlsx`) hazırlar.

### `temizle.py`

Ham ürün verisini işleyen ilk temizlik scriptidir.

Başlıca görevleri:

- kategori adlarını ana gruplara standartlaştırmak,
- stoksuz ürünleri ayırmak,
- karmaşık stok kodlarını tespit etmek,
- parent-child ilişkilerini kurmak,
- sonraki temizlik adımları için ara dosyaları üretmek.

### `olcu_temizle.py`

Ölçü alanlarını standartlaştırır.

Örnek:

```text
20mm → 20
2cm  → 20
```

Tek bir sayısal değere dönüştürülemeyen ölçüler açıklama veya manuel düzenleme alanına aktarılır.

### `duzelt.py`

Açıklama alanlarında oluşan tekrarlı veya gereksiz metinleri temizler.

### `kalip_yedekle.py`

Kalıp göz sayısı gibi üretim bilgilerini ürün ana verisinden ayırır ve:

```text
kalip_bilgileri_yedek.xlsx
```

dosyasına aktarır.

### `ayir.py`

Temizlik sonunda:

- standart ve doğrudan aktarılabilir ürünleri,
- birden fazla ölçü veya stok kodu içeren manuel işlem gerektiren ürünleri

ayrı dosyalara böler.

### `birlesik_stok_kodlarini_duzelt.py`

`temiz_urunler_standart.xlsx`'teki birleşik/hatalı stok kodlarını düzeltir ve düzeltme kararlarını `birlesik_stok_kodu_duzeltme_raporu.xlsx` raporuna yazar.

### `ayni_urun_tekrarlarini_sil.py`

Stok kodu, kategori ve ölçüleri birebir aynı olan tekrar satırları siler (`silinen_ayni_urun_tekrarlari.xlsx` raporu).

### `secili_stok_tekrarlarini_sil.py`

Otomatik kurallarla ayıklanamayan, elle karar verilmiş belirli stok kodları (örn. 2111735, 2117058, 2126746, 2134040) için tekilleştirme yapar (`manuel_silinen_stok_tekrarlari.xlsx` raporu).

### `final_excel_hazirla.py`

Normalizasyon hattının son adımıdır. Özel çoklu-parça/varyant ürünleri (örn. "2108" toka+pul takımı, "1805012" eski/yeni kalıp varyantları) `ANA_URUN` / `ALT_PARCA` / `VARYANT` satırlarına böler, `temiz_urunler_final.xlsx` dosyasını ve `final_excel_duzenleme_raporu.xlsx` kontrol raporunu üretir.

### `yukle.py`

Nihai temiz ürün verisini (`temiz_urunler_final.xlsx`) doğrulayıp (zorunlu kolonlar, tekil stok kodu, parent ilişkileri) PostgreSQL'e aktaran migration scriptidir. Yükleme öncesi `urunler` ve `kategoriler` tablolarını `TRUNCATE ... CASCADE` ile temizler.

### `gorsel_esle_duzeltilmis_v2.py`

`urun_listesi.xlsx` içindeki Excel drawing ilişkilerini doğrudan OOXML yapısından okuyarak ürün görsellerini stok kodlarıyla eşleştirir.

Script:

- görünür ürün sayfasını bulur,
- sayfaya bağlı doğru drawing XML dosyasını seçer,
- görsel anchor konumunu Excel satırıyla eşleştirir,
- stok kodunu ilgili satırın B sütunundan okur,
- orijinal görsel uzantısını korur,
- aynı stok koduna ait çoklu görselleri `_1`, `_2`, `_3` şeklinde adlandırır,
- eşleme sonucunu CSV raporuna kaydeder.

Çalıştırma:

```bash
python3 scripts/images/gorsel_esle_duzeltilmis_v2.py data/raw/urun_listesi.xlsx
```

Çıktı klasörü, verilen Excel dosyasının **bulunduğu klasöre göreli** oluşturulur (`<excel_dosyasının_klasörü>/urun_gorselleri_stoklu_duzeltilmis/`) — script `data/`/`images/` klasör yapısını bilmez. Bu komut mevcut çıktı klasörüyle çalıştırılmadan önce eski klasörün arşivlenmesi veya çıktı klasörünün boş olduğunun doğrulanması gerekir.

Bu scriptten sonra sırasıyla şunlar çalıştırılır:

- `gorsel_stok_kodlarini_guncelle.py` — normalizasyon sırasında stok kodu değişen görselleri yeniden adlandırır (`birlesik_stok_kodu_duzeltme_raporu.xlsx` eşlemesini kullanır),
- `gorsel_eslesme_raporu.py` — nihai görsel klasörünü veritabanındaki `urunler` tablosuyla karşılaştırıp eşleşmeyen/görselsiz/çoklu-görselli ürünleri raporlar (`gorsel_eslesme_raporu.xlsx`).

---

## 🐘 PostgreSQL Yapısı

### `docker-compose.yml`

PostgreSQL konteynerini çalıştırır.

```bash
docker compose up -d
```

### `sql/01_schema.sql`

Güncel ve `docker-compose.yml` tarafından fiilen kullanılan şemadır (`docker-entrypoint-initdb.d` altına mount edilir). Kök dizindeki `init_db.sql` daha eski/basit bir sürümdür ve artık konteyner tarafından kullanılmaz — referans olarak saklanmaktadır.

Temel tablolar:

```text
kategoriler
urunler
hammaddeler
kaplamalar
lokasyonlar
stok_hareketleri
urun_gorselleri
```

`urun_gorselleri` tablosu — aşağıdaki "Ürün Görselleri İçin Veritabanı Yapısı" bölümünde detaylandırıldığı gibi — **zaten oluşturulmuş durumdadır**; henüz veri yüklenmemiştir (bkz. Faz 2).

### Mimari ilkeler

#### Master data yaklaşımı

`urunler` tablosu yalnızca ürünün değişmeyen fiziksel ve tanımlayıcı özelliklerini tutar.

Örnek:

- stok kodu,
- kategori,
- ölçü,
- gramaj,
- açıklama,
- parent ürün ilişkisi.

#### Üretim verisinin ayrılması

Kalıp göz sayısı gibi imalat bilgileri doğrudan ürünün özelliği kabul edilmemiştir.

Bu bilgiler ileride:

```text
kaliplar
```

tablosunda yönetilecektir.

#### Parent-child ilişkisi

Ayrı stok kodu bulunmayan tamamlayıcı parçalar türetilmiş stok kodlarıyla ana ürüne bağlanır.

Örnek:

```text
ANA-STOK
ANA-STOK-PUL
```

#### Sayısal alanlar

Ölçü ve boy bilgileri mümkün olduğu ölçüde metin yerine sayısal veri tiplerinde tutulur. Böylece:

- filtreleme,
- sıralama,
- aralık sorguları,
- raporlama

daha güvenilir ve hızlı yapılabilir.

---

## 🖼️ Ürün Görselleri İçin Veritabanı Yapısı

Bir ürüne birden fazla görsel bağlanabilmesi için görsel bilgileri ayrı bir tabloda tutulur. Bu tablo **zaten `sql/01_schema.sql`'de oluşturulmuştur** (aşağıdaki yapı planlanan değil, gerçek/mevcut yapıdır); henüz veri yüklenmemiştir:

```sql
CREATE TABLE urun_gorselleri (
    gorsel_id         BIGSERIAL PRIMARY KEY,
    stok_kodu          VARCHAR(100) NOT NULL REFERENCES urunler(stok_kodu) ON DELETE CASCADE,
    dosya_adi           TEXT NOT NULL,
    ana_gorsel_mi        BOOLEAN NOT NULL DEFAULT FALSE,
    sira_no               INTEGER NOT NULL DEFAULT 1 CHECK (sira_no > 0),
    medya_tipi             VARCHAR(30) NOT NULL DEFAULT 'URUN_GORSELI',
    aciklama                 TEXT,
    aktif_mi                  BOOLEAN NOT NULL DEFAULT TRUE,
    olusturma_tarihi            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (stok_kodu, dosya_adi)
);
```

Bir ürünün yalnızca bir aktif "ana görseli" olabileceğini garanti eden kısmi bir unique index de tanımlıdır (`uq_urun_tek_ana_gorsel`).

Dosyalar fiziksel olarak:

```text
images/final/products/
```

klasöründe saklanır; veritabanında ise dosya adı ve `stok_kodu` ilişkisi tutulur. **934 görsel** henüz hiçbir stok koduna bağlı değil (bkz. yukarıdaki uyarı) — stok kodu tarafı çözüldü ama görsel dosya adları yeni kodlarla eşleşmiyor; bu tabloya veri yüklemeden önce görsellerin yeniden bağlanması gerekiyor.

---

## 🗃️ Arşiv Yapısı

`archive/` klasörü aktif sistemde kullanılmayan ancak veri geçmişini ve yeniden üretilebilirliği koruyan dosyaları içerir.

```text
archive/
├── extracted_excel/
├── intermediate_data/
├── notebooks/
├── old_images/
├── project_snapshots/
├── reports/
└── scripts/
```

### `archive/extracted_excel/`

Excel dosyasının ZIP/OOXML olarak açılmış içeriğini ve analiz amacıyla oluşturulan ZIP dosyasını içerir.

### `archive/intermediate_data/`

Temizleme hattı sırasında üretilen ara Excel ve CSV dosyalarını içerir.

### `archive/notebooks/`

Eski analiz ve migration notebooklarını içerir.

### `archive/old_images/`

Nihai görsel klasöründen önce oluşturulan eski görsel çıktılarını içerir.

### `archive/project_snapshots/`

Belirli tarihlerde alınan, deponun tüm dosya listesinin anlık görüntülerini (`dosya_listesi_*.txt`) içerir.

### `archive/reports/`

Görsel analizi, çoklu görsel kontrolü ve eski-yeni karşılaştırma raporlarını içerir.

### `archive/scripts/`

Ana işlem hattında artık kullanılmayan ancak denetim veya yeniden analiz için saklanan yardımcı scriptleri içerir.

---

## 🔒 Dosya Koruma Kuralları

Aşağıdaki dosya ve klasörler yedek alınmadan silinmemeli veya toplu olarak değiştirilmemelidir:

```text
data/raw/urun_listesi.xlsx
data/processed/temiz_urunler_final_v2.xlsx
data/reference/kalip_bilgileri_yedek.xlsx
images/final/products/
sql/01_schema.sql
scripts/database/yukle.py
```

Özellikle `data/raw/urun_listesi.xlsx`, gömülü görseller nedeniyle yaklaşık 195 MB boyutundadır. Dosyanın normal Excel kaydı sırasında görsel anchor yapısı değişebileceğinden, toplu düzenlemelerden önce yedek alınmalıdır.

Excel tarafından oluşturulan şu tip geçici dosyalar (`~$...xlsx`) gerçek veri değildir ve yalnızca ilgili Excel dosyası kapalıyken silinebilir. Kök dizinde şu an böyle iki dosya var; silmeden önce Excel'in gerçekten kapalı olduğu doğrulanmalı.

---

## 🧪 Temel Kontrol Komutları

Nihai görsel sayısı:

```bash
find images/final/products -maxdepth 1 -type f \
\( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) \
| wc -l
```

Beklenen sonuç:

```text
2733
```

Eşleme raporunun varlığını kontrol etme:

```bash
ls -lh images/working/products/gorsel_esleme_raporu.csv
```

PostgreSQL konteyner durumu:

```bash
docker compose ps
```

Ana klasör görünümü:

```bash
ls -lah
```

Arşiv görünümü:

```bash
find archive -maxdepth 2 -print
```

---

## 🚀 Sonraki Fazlar

### Faz 2: Ürün görsellerinin veritabanına bağlanması ✅ TAMAMLANDI (2026-07-28)

- ~~`urun_gorselleri` tablosunun oluşturulması~~ ✅ (`sql/01_schema.sql`)
- ~~857 karışık ürün satırının stok kodu ailelerine göre normalize edilip veritabanına yüklenmesi~~ ✅ — 2.973 ürün DB'de
- ~~934 eşleşmeyen görselin çözülmesi~~ ✅ arşivlendi (`images/arsiv/products/`), aktif klasör %100 eşleşiyor
- ~~CSV eşleme raporunun veritabanına aktarılması~~ ✅ `scripts/database/gorselleri_yukle.py` — 1.799 görsel yüklendi
- ~~ana görsel ve sıralama mantığının belirlenmesi~~ ✅ dosya adındaki sıra numarası (`<stok_kodu>_<sira>.<uzanti>`) kullanıldı; sira=1 → `ana_gorsel_mi`
- eksik ürün-görsel ilişkilerinin raporlanması: 1.194 üründe henüz görsel yok (`Gorselsiz_Urunler` raporu) — bu normal/beklenen bir eksiklik, arşiv kapsamı dışında, ayrıca ele alınmalı

Sonuç: 1.780 üründe tam olarak bir ana görsel var, 19 üründe birden fazla görsel var, hiçbir kısıt ihlali yok.

### Faz 3: Kalıp modülü

- `kaliplar` tablosunun oluşturulması
- göz sayısı bilgisinin kalıplara bağlanması
- ürün-kalıp ilişkilerinin kurulması
- kalıp bakım ve durum kayıtlarının eklenmesi

### Faz 4: Depo yönetimi ✅ BÜYÜK ÖLÇÜDE TAMAMLANDI (2026-07-29)

Bu fazın ayrıntılı planı, kullanıcının ChatGPT'den alıp değerlendirmemizi istediği bir
"master plan" prompt setinden geldi (Prompt 3: "Depocu stok giriş-çıkış ekranı") —
prompt'un kendisinde bazı hatalar vardı (örn. `urunler`'de olmayan bir `urun_id` varsayımı,
yanlış ürün/görsel sayıları) ama gereksinimleri gerçek eksikleri ortaya çıkardı.

- ~~depo ve raf lokasyonları~~ 🔶 kısmi — `lokasyonlar` tablosuna 3 test/placeholder satırı
  girildi (Ana Depo, Sevkiyat Alanı — DAHILI; Fason Atölye 1 — FASON). **Gerçek işletme
  lokasyonlarıyla değiştirilmeli**, sadece Appsmith'i test edebilmek için.
- ~~mevcut stok hesaplama~~ ✅ **canlıya uygulandı** — `v_lokasyon_stok_ozet`/
  `v_toplam_stok` view'ları (`sql/migrations/002_lokasyon_stok_view.sql`), kullanıcı
  onayıyla ortak DB'ye işlendi.
- ~~giriş-çıkış hareketleri~~ ✅ **canlıya uygulandı** — tek giriş noktası
  `stok_hareketi_kaydet()` fonksiyonu (`sql/migrations/003_stok_hareketi_fonksiyonu.sql`):
  atomik, mükerrer-gönderim korumalı (istemci kimliği ile), yeterli-stok kontrollü, işlemi
  yapan kullanıcı zorunlu, işlem tipine göre lokasyon zorunluluğu var.
- ~~sayım ve düzeltme hareketleri~~ ✅ kural netleşti ve canlıda test edildi — SAYIM_DEVRİ
  girişi personelin saydığı **toplam bakiyedir** (fark değil); fonksiyon gerçek ledger
  farkını kendisi hesaplayıp yazıyor. Gerekçe ve tam sözleşme: `docs/aktif-urun-veri-sozlesmesi.md`.
- ~~Appsmith `StokIslemi` sayfası~~ ✅ **tam bağlandı ve canlıda test edildi (2026-07-29)**:
  GİRİŞ/ÇIKIŞ/SAYIM DEVRİ/TRANSFER/DÜZELTME'nin beşi de çalışıyor (TRANSFER için ayrı
  "Hedef Lokasyon", DÜZELTME için "Yön" (Artış/Azalış) widget'ları eklendi). Kullanıcı
  gerçek `KaydetButton`'a tıklayarak `stok_hareketleri`'ne satır yazdırdı, `yapan_kullanici`
  ve lokasyon ataması doğru geldi. Detaylar ve karşılaşılan Appsmith şema tuhaflıkları
  (`SELECT_WIDGET` `options`→`sourceData` geçişi, `crypto.randomUUID()`'nin HTTP'de
  çalışmaması, `TABLE_WIDGET_V2` `computedValue` gerekliliği) `depo-appsmith-arayuz/CLAUDE.md`'de.
- Kalan: `lokasyonlar` tablosundaki 3 satır hâlâ test verisi, gerçek işletme lokasyonlarıyla
  değiştirilmeli; `stok_hareketleri`'nde bugünkü testlerden kalan birkaç kayıt var
  (kullanıcı bilerek "en son temizleriz" dedi, henüz silinmedi).

### Faz 5: Web ERP arayüzü ✅ BÜYÜK ÖLÇÜDE TAMAMLANDI (2026-07-29)

ChatGPT'nin planındaki Prompt 4 ("Ürün arama ve katalog ekranı") ve Prompt 7 ("Yönetim
ana sayfası") buraya karşılık geliyor — ikisi de mantıken "Web ERP arayüzü"nün parçası.

- ~~ürün arama~~ ✅ hem `v_aktif_urunler` view'ı hem de Appsmith tarafı hazır — **yeni
  `UrunlerKatalog` sayfası** kuruldu (arama + kategori filtresi + sonuç tablosu + görsel +
  detay paneli), canlıda test edildi (1.780 aktif ürün, kategori dağılımı doğrulandı:
  TOKA 526, ALTTAN DİKME DÜĞME 503, RİVET 191 ... KİLİT/BRİT/STOPER gibi 1'er ürünlü nadir
  kategoriler dahil, 31 üründe kategori boş).
- ~~görsel gösterimi~~ ✅ **statik dosya sunucusu kuruldu** — `docker-compose.yml`'e
  `gorsel-sunucu` servisi (nginx, port 8083) eklendi, `images/final/products/`'ı
  `http://<host>:8083/urun-gorselleri/<dosya_adi>` altında yayınlıyor (path traversal/dizin
  listeleme engellendiği test edildi). Hem `StokIslemi.UrunGorseli` hem
  `UrunlerKatalog.KatalogUrunGorseli` buna bağlı.
- ~~stok hareketleri~~ → Faz 4'e taşındı, bkz. yukarı.
- lokasyon yönetimi — henüz gerçek bir CRUD arayüzü yok, sadece test verisi var.
- kullanıcı yetkilendirmesi — Appsmith'in kendi kullanıcı sistemi kısmen kullanılıyor
  (self-hosted Community Edition, Developer/Viewer rolleri) ama uygulama içi "kim ne
  görebilir" ayrımı (örn. depo personeli vs. yönetici) henüz tasarlanmadı.
- **Yönetim ana sayfası** (ChatGPT'nin Prompt 7'si): toplam/kullanılabilir stok, kritik
  stoklu ürünler, son hareketler gibi özet kartları — henüz başlanmadı; kartların çoğu
  (açık sipariş, üretimdeki iş emri) Faz 6/7 olmadan anlamsız kalır, o yüzden bu iki fazın
  arkasına bırakıldı.
- **`UrunlerKatalog` arama limiti bilinçli olarak 200 satırda sınırlı** (tam 1780 ürünü
  gezinme değil, arama/filtre ile daraltma senaryosu için); `StokIslemi.UrunAra` da aynı
  şekilde 50'de — kullanıcı onayıyla şimdilik böyle bırakıldı, gerekirse yükseltilebilir.

### 📋 Sıradaki iş kalemleri (öncelik sırası, 2026-07-29'da planlandı) — ✅ 6/6 TAMAMLANDI (2026-07-30)

Kullanıcıyla web arayüzünün nihai ekran/tool setini gözden geçirdiğimiz konuşmadan çıkan,
üzerinde anlaşılan sıra. Hepsi `depo-appsmith-arayuz` reposunda uygulandı, canlı DB'ye
karşı test edildi ve `dev`'e pushlandı (detaylar o reponun `CLAUDE.md`'sinde):

1. **✅ Çoklu kategori seçimi** — `KategoriFilterSelect`, `SELECT_WIDGET` → `MULTI_SELECT_WIDGET_V2`'ye
   çevrildi, `KatalogUrunleriGetir` artık `kategori_adi = ANY(selectedOptionValues)` kullanıyor.
2. **✅ Gerçek lokasyon verisi + Lokasyon Yönetimi sayfası** — yeni `LokasyonYonetimi` sayfası
   (ekle/listele/pasifleştir) kuruldu. **Gerçek işletme lokasyonlarını girmek hâlâ kullanıcıya
   ait** — Claude lokasyon isimlerini bilmediği/uyduramayacağı için 3 test satırı
   (Ana Depo/Sevkiyat Alanı/Fason Atölye 1) henüz değiştirilmedi, sadece bunu değiştirecek araç
   hazır.
3. **✅ "Sadece stokta olanları listele" filtresi** — `SadeceStoktaOlanlarSwitch` +
   `v_toplam_stok` LEFT JOIN. Gerçek lokasyon/sayım verisi girilene kadar ~0 sonuç verecek,
   öngörüldüğü gibi.
4. **🔶 Galeri görünümü — iskelet tamam, List widget kullanıcıyı bekliyor**: anahtar/buton/
   büyüyen LIMIT/paylaşılan detay paneli hazır; asıl kart ızgarasını oluşturan Appsmith
   List (V2) widget'ı bilinçli olarak git üzerinden yazılmadı (bu repoda hiç örneği yok,
   yanlış yazılırsa sayfanın tamamını bozma riski var) — kullanıcı tarafından canlı Editor'de
   eklenmesi bekleniyor, tam talimat `depo-appsmith-arayuz/CLAUDE.md`'de.
5. **✅ Stok Özet / Envanter sayfası** — yeni `StokOzet` sayfası, şemada var olan ama hiç
   kullanılmayan `urunler.kritik_stok_esigi` kolonu ilk kez kullanıldı (kritik durumu işaretleme).
6. **✅ Yönetim Ana Sayfası (dashboard)** — kullanıcının onayıyla asıl plandaki sıranın önüne
   alınıp şimdiden kuruldu (özgün planda madde 5'in verisi olgunlaşana kadar bekletilecekti).
   Kartların çoğu gerçek lokasyon/sayım verisi girilene kadar 0/az gösterecek, beklenen.

### Faz 6: Barkod ve sipariş entegrasyonu

ChatGPT'nin Prompt 5'i ("Sipariş yönetimi") bu fazın sipariş kısmını detaylandırıyor,
henüz hiçbir parçası kurulmadı:

- sipariş ve rezervasyon akışı — önerilen varlıklar: `musteriler`, `siparisler`,
  `siparis_kalemleri`, `siparis_durum_gecmisi`, `stok_rezervasyonlari`. Kurallar arasında
  termin/kalan gün hesaplama, fiziksel/rezerve/kullanılabilir stok ayrımı, kısmi
  hazırlama-sevkiyat, siparişin silinmeyip iptal edilmesi var — detay için ChatGPT
  prompt'unun orijinali bu konuşmanın geçmişinde mevcut.
- barkod üretme ve okutma, ürün kabul, sevkiyat — henüz başlanmadı.

### Faz 7: Üretim takibi (yeni, 2026-07-29 — ChatGPT'nin Prompt 6'sından)

- Sipariş kalemlerinden iş emri oluşturma; iş emri + üretim kaydı (aşama, makine, kalıp,
  operatör, giren/sağlam/fire miktarı) ayrı varlıklar olarak öneriliyor.
- Aşamalar: BEKLİYOR → ZAMAKHANE → TEMİZLEME → KAPLAMA → FASON → MONTAJ →
  KALİTE_KONTROL → HAZIR → TAMAMLANDI → İPTAL.
- `data/reference/kalip_bilgileri_yedek.xlsx`'i kullanacak ama **Faz 3 (Kalıp modülü)**
  tamamlanmadan bu faz da tam anlamıyla başlayamaz — ikisi bağlantılı, ikisi de bilinçli
  olarak şimdilik ertelendi.
- İlk sürümde kapasite planlama/otomatik çizelgeleme yapılmayacak (kullanıcının kendi
  kısıtı) — sade bir pano/tablo yeterli.

---

## 📌 Güncel Çalışma Noktası

Veri temizleme, normalizasyon, karışık stok kodu çözümü, PostgreSQL aktarımı ve görsellerin `urun_gorselleri` tablosuna bağlanması (Faz 2) tamamlanmıştır. Veritabanında **2.973 ürün** (2.969 ANA_URUN, 3 ALT_PARCA, 2 VARYANT) ve **1.799 görsel kaydı** var (1.780 üründe ana görsel, 19 üründe çoklu görsel).

**2026-07-28 kapsam kararı:** Standartlaştırılamayan/eşleşmeyen uzun kuyruk (216 çözülemeyen karışık kod, 66 hiç işlenmemiş "ölçü karmaşık" satır, 6 stoksuz satır, 934 eski-adlı görsel) bilinçli olarak arşivlendi — muhtemelen çok eski/düşük cirolu ürünler, aktif sistemi bunlarla uğraştırmak yerine temiz bir temel üzerine odaklanıldı. Hiçbir şey silinmedi:

```text
data/reference/arsivlenen_eski_urunler.xlsx  (ürün tarafı, sebep sütunlarıyla)
images/arsiv/products/                        (934 görsel dosyası)
scripts/maintenance/eski_urunleri_arsivle.py   (bu arşivlemeyi üreten script)
```

**2026-07-29 güncellemesi:** `urunler.katalog_durumu` canlıya uygulandı — 1.780 ürün
`AKTIF` (doğrulanmış ana görseli var), 1.193 ürün `PASIF`. `v_aktif_urunler` view'ı
Appsmith'in tek okuma kaynağı olarak hazır. Appsmith arayüz katmanı ayrı bir git reposunda
(`depo-appsmith-arayuz`) geliştiriliyor — Faz 5'in gerçek UI çalışması orada; bu repoda
sadece veri/şema tarafı var. Detaylı mimari, branch modeli (`master`/`dev`/`review`, her
iki repoda aynı) ve tam sözleşme için `CLAUDE.md` ve `docs/aktif-urun-veri-sozlesmesi.md`'ye
bakın — güncel sayılar/durum artık orada takip ediliyor, bu bölüm sadece genel roadmap.

**2026-07-29 ikinci güncelleme — Faz 4 ve Faz 5'in çekirdeği tamamlandı:** migration 002
(`v_lokasyon_stok_ozet`/`v_toplam_stok`) ve 003 (`stok_hareketi_kaydet()`) kullanıcı
onayıyla ortak DB'ye uygulandı; Appsmith `StokIslemi` sayfası tüm 5 işlem tipiyle
(GİRİŞ/ÇIKIŞ/SAYIM DEVRİ/TRANSFER/DÜZELTME) canlıda test edildi; `images/final/products/`'ı
yayınlayan bir nginx statik dosya sunucusu (`docker-compose.yml`, port 8083) kuruldu; yeni
bir `UrunlerKatalog` sayfası (arama + kategori filtresi + görsel + detay) sıfırdan
oluşturulup test edildi. Süreçte birkaç Appsmith widget-şema sürprizi bulunup düzeltildi
(bkz. `depo-appsmith-arayuz/CLAUDE.md`) — hepsi git dosyalarına doğrudan yazılan
widget/sorgu tanımlarının, canlı Appsmith sürümünün gerçekte beklediği şemadan farklı
çıkması yüzündendi (`SELECT_WIDGET` `options`→`sourceData`/`optionLabel`/`optionValue`,
`crypto.randomUUID()`'nin düz HTTP'de çalışmaması, `TABLE_WIDGET_V2` kolonlarının açık
`computedValue` istemesi).

Kalan açık uçlar: `lokasyonlar`'daki 3 satır hâlâ test verisi (gerçek işletme
lokasyonlarıyla değiştirilmeli); bugünkü test sırasında `stok_hareketleri`'ne düşen birkaç
kayıt kullanıcının isteğiyle şimdilik siliniyor değil ("en son temizleriz"); Appsmith
"Yönetim ana sayfası" (Faz 5'in son parçası) henüz başlanmadı. Faz 3 (Kalıp Modülü) ve
Faz 7 (Üretim takibi) kullanıcı tarafından bilinçli olarak ertelendi.
