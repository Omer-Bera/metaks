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

> ⚠️ Bu görsellerin **934 tanesi** (`reports/excel/gorsel_eslesme_raporu.xlsx`) henüz veritabanındaki hiçbir stok koduyla eşleşmiyor. Bunların hepsi orijinal Excel'de `/` ile birleştirilmiş çoklu stok kodlu ("karışık") satırlara ait — bu 857 satır (`data/interim/karisik_urunler.xlsx`) henüz normalize edilip veritabanına yüklenmedi. Faz 2'ye (`urun_gorselleri` tablosu) geçmeden önce bu iş bitirilmeli, aksi halde görsellerin ~%34'ü hiçbir ürüne bağlanamaz.

---

## ⭐ Nihai Veri Seti

Aşağıdaki dosya ve klasörler projenin güncel ve güvenilir ana veri setidir:

```text
data/raw/urun_listesi.xlsx
data/processed/temiz_urunler_final_v1.xlsx
data/reference/kalip_bilgileri_yedek.xlsx
images/final/products/
```

`data/processed/temiz_urunler_final_v1.xlsx` içindeki **1.831 satır**, `scripts/database/yukle.py` ile PostgreSQL'e yüklenmiş olan güncel nihai veridir. `data/interim/temiz_urunler_standart.xlsx` artık ara bir aşamadır (bkz. Normalizasyon Hattı bölümü); doğrudan referans alınmamalıdır.

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

### `data/processed/temiz_urunler_final_v1.xlsx`

PostgreSQL'e aktarılmış olan gerçek nihai veridir (**1.831 satır**). Normalizasyon Hattı'nın son adımı olan `final_excel_hazirla.py` tarafından üretilir; tekil stok kodları, parent-child/varyant ilişkileri ve `scripts/database/yukle.py`'nin beklediği tüm kolonları içerir.

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
│   ├── processed/                # temiz_urunler_final_v1.xlsx (DB'ye yüklenen)
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

klasöründe saklanır; veritabanında ise dosya adı ve `stok_kodu` ilişkisi tutulur. **934 görsel** henüz hiçbir stok koduna bağlı değil (bkz. yukarıdaki uyarı) — bu tabloya veri yüklemeden önce çözülmesi gerekiyor.

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
data/processed/temiz_urunler_final_v1.xlsx
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

### Faz 2: Ürün görsellerinin veritabanına bağlanması

- ~~`urun_gorselleri` tablosunun oluşturulması~~ ✅ tamamlandı (`sql/01_schema.sql`)
- **ön koşul:** 857 karışık ürün satırının (`data/interim/karisik_urunler.xlsx`) stok kodu ailelerine göre normalize edilip veritabanına yüklenmesi — aksi halde 934 görsel eşleşmeden kalır
- CSV eşleme raporunun veritabanına aktarılması
- ana görsel ve sıralama mantığının belirlenmesi
- eksik ürün-görsel ilişkilerinin raporlanması

### Faz 3: Kalıp modülü

- `kaliplar` tablosunun oluşturulması
- göz sayısı bilgisinin kalıplara bağlanması
- ürün-kalıp ilişkilerinin kurulması
- kalıp bakım ve durum kayıtlarının eklenmesi

### Faz 4: Depo yönetimi

- depo ve raf lokasyonları
- giriş-çıkış hareketleri
- mevcut stok hesaplama
- sayım ve düzeltme hareketleri

### Faz 5: Web ERP arayüzü

- ürün arama
- ürün kartı
- görsel gösterimi
- stok hareketleri
- lokasyon yönetimi
- kullanıcı yetkilendirmesi

### Faz 6: Barkod ve sipariş entegrasyonu

- barkod üretme ve okutma
- ürün kabul
- sevkiyat
- sipariş ve rezervasyon akışı

---

## 📌 Güncel Çalışma Noktası

Standart ürünler için veri temizleme, normalizasyon, PostgreSQL aktarımı (1.831 ürün) ve görsel eşleme süreci tamamlanmıştır. **Karışık stok kodlu 857 satır** ise henüz normalize edilip yüklenmedi — bu yüzden 2.733 görselin 934'ü veritabanında karşılıksız duruyor.

Bir sonraki teknik adım:

```text
"stok kodu aile kuralları"nın (karışık kodların hangi mantıkla ayrı ürünlere bölüneceği) yazılı hale getirilmesi
→ karisik_urunler.xlsx'i bu kurallara göre normalize eden yeni bir script
→ normalize edilmiş satırların temiz_urunler_final.xlsx akışına eklenip veritabanına yüklenmesi
→ gorsel_eslesme_raporu.py'nin yeniden çalıştırılıp eşleşmeyen görsel sayısının düşürülmesi
→ urun_gorselleri tablosunun doldurulması
→ ürün kartlarında görsellerin kullanılmaya başlanması
```
