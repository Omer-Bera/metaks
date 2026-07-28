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

---

## ⭐ Nihai Veri Seti

Aşağıdaki dosya ve klasörler projenin güncel ve güvenilir ana veri setidir:

```text
urun_listesi.xlsx
temiz_urunler_standart.xlsx
kalip_bilgileri_yedek.xlsx
urun_gorselleri_stoklu_duzeltilmis/
```

### `urun_listesi.xlsx`

Ürün kataloğunun görselleri düzeltilmiş nihai Excel kaynağıdır.

Bu dosyada:

- ürün satırları,
- stok kodları,
- ürün açıklamaları,
- Excel içine gömülü ürün görselleri

bulunur.

Görsel eşleme işlemi bu dosya esas alınarak yapılmıştır. Dosya, görsel konumlarının ve ilişkilerinin korunması için ana klasörde saklanmalıdır.

### `temiz_urunler_standart.xlsx`

PostgreSQL'e aktarılmaya hazır, temizlenmiş ve standartlaştırılmış ürün ana verisidir.

Bu dosyada:

- standart kategori adları,
- tekil stok kodları,
- sayısal ölçü alanları,
- açıklama alanları,
- parent-child ilişkileri

bulunur.

### `kalip_bilgileri_yedek.xlsx`

Ürünlerden ayrılan kalıp göz sayısı bilgilerinin stok kodlarıyla birlikte tutulduğu güvenli yedektir.

Bu veri ileride geliştirilecek Kalıp Modülü için korunmaktadır.

### `urun_gorselleri_stoklu_duzeltilmis/`

Stok kodlarıyla adlandırılmış nihai ürün görsellerini içerir.

Klasörde ayrıca:

```text
gorsel_esleme_raporu.csv
```

dosyası bulunur. Bu rapor; Excel satırı, stok kodu, kaynak medya dosyası, oluşturulan dosya adı ve işlem durumunu kayıt altına alır.

> Bu klasör elle yeniden adlandırılmamalı veya eski görsel klasörleriyle birleştirilmemelidir.

---

## 📂 Ana Klasör Yapısı

```text
metaks_DB/
├── archive/
├── ayir.py
├── docker-compose.yml
├── duzelt.py
├── gorsel_esle_duzeltilmis_v2.py
├── INFO.md
├── init_db.sql
├── kalip_bilgileri_yedek.xlsx
├── kalip_yedekle.py
├── olcu_temizle.py
├── temiz_urunler_standart.xlsx
├── temizle.py
├── urun_gorselleri_stoklu_duzeltilmis/
├── urun_listesi.xlsx
├── venv/
└── yukle.py
```

---

## 🐍 Python Scriptleri

### Veri temizleme hattı

Scriptlerin temel çalışma sırası:

```text
temizle.py
→ olcu_temizle.py
→ duzelt.py
→ kalip_yedekle.py
→ ayir.py
→ yukle.py
```

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

### `yukle.py`

Nihai temiz ürün verisini PostgreSQL'e aktaran migration scriptidir.

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
python3 gorsel_esle_duzeltilmis_v2.py urun_listesi.xlsx
```

Bu komut mevcut çıktı klasörüyle çalıştırılmadan önce eski klasörün arşivlenmesi veya çıktı klasörünün boş olduğunun doğrulanması gerekir.

---

## 🐘 PostgreSQL Yapısı

### `docker-compose.yml`

PostgreSQL konteynerini çalıştırır.

```bash
docker compose up -d
```

### `init_db.sql`

Veritabanı tablolarını, ilişkileri, kısıtlamaları ve indeksleri tanımlar.

Temel tablolar:

```text
kategoriler
urunler
hammaddeler
kaplamalar
lokasyonlar
stok_hareketleri
```

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

## 🖼️ Ürün Görselleri İçin Planlanan Veritabanı Yapısı

Bir ürüne birden fazla görsel bağlanabilmesi için görsel bilgilerinin ayrı tabloda tutulması önerilir.

Önerilen yapı:

```sql
CREATE TABLE urun_gorselleri (
    id              BIGSERIAL PRIMARY KEY,
    urun_id         BIGINT NOT NULL REFERENCES urunler(id) ON DELETE CASCADE,
    dosya_adi       TEXT NOT NULL,
    ana_gorsel_mi   BOOLEAN NOT NULL DEFAULT FALSE,
    sira_no         INTEGER NOT NULL DEFAULT 1,
    aciklama        TEXT,
    UNIQUE (urun_id, dosya_adi)
);
```

Dosyalar fiziksel olarak:

```text
urun_gorselleri_stoklu_duzeltilmis/
```

klasöründe saklanır; veritabanında ise dosya adı ve ürün ilişkisi tutulur.

---

## 🗃️ Arşiv Yapısı

`archive/` klasörü aktif sistemde kullanılmayan ancak veri geçmişini ve yeniden üretilebilirliği koruyan dosyaları içerir.

```text
archive/
├── extracted_excel/
├── intermediate_data/
├── notebooks/
├── old_images/
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

### `archive/reports/`

Görsel analizi, çoklu görsel kontrolü ve eski-yeni karşılaştırma raporlarını içerir.

### `archive/scripts/`

Ana işlem hattında artık kullanılmayan ancak denetim veya yeniden analiz için saklanan yardımcı scriptleri içerir.

---

## 🔒 Dosya Koruma Kuralları

Aşağıdaki dosya ve klasörler yedek alınmadan silinmemeli veya toplu olarak değiştirilmemelidir:

```text
urun_listesi.xlsx
temiz_urunler_standart.xlsx
kalip_bilgileri_yedek.xlsx
urun_gorselleri_stoklu_duzeltilmis/
init_db.sql
yukle.py
```

Özellikle `urun_listesi.xlsx`, gömülü görseller nedeniyle yaklaşık 195 MB boyutundadır. Dosyanın normal Excel kaydı sırasında görsel anchor yapısı değişebileceğinden, toplu düzenlemelerden önce yedek alınmalıdır.

Excel tarafından oluşturulan şu tip geçici dosyalar gerçek veri değildir:

```text
~$urun_listesi.xlsx
~$temiz_urunler_standart.xlsx
```

Bu dosyalar yalnızca ilgili Excel dosyası kapalıyken silinebilir.

---

## 🧪 Temel Kontrol Komutları

Nihai görsel sayısı:

```bash
find urun_gorselleri_stoklu_duzeltilmis -maxdepth 1 -type f \
\( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) \
| wc -l
```

Beklenen sonuç:

```text
2733
```

Eşleme raporunun varlığını kontrol etme:

```bash
ls -lh urun_gorselleri_stoklu_duzeltilmis/gorsel_esleme_raporu.csv
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

- `urun_gorselleri` tablosunun oluşturulması
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

Veri temizleme, PostgreSQL aktarımı ve görsel eşleme süreci tamamlanmıştır.

Bir sonraki teknik adım:

```text
urun_gorselleri tablosunun oluşturulması
→ gorsel_esleme_raporu.csv verisinin PostgreSQL'e aktarılması
→ ürün kartlarında görsellerin kullanılmaya başlanması
```
