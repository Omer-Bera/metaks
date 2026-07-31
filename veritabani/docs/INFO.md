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

Görsel eşleme hattı toplam **2.733 ürün görseli** üretti; bunların **1.799'u** aktif
klasörde (`images/final/products/`, DB ile birebir eşleşen), **934'ü** arşivde
(`images/arsiv/products/`) — aşağıdaki 2026-07-28 kapsam kararına bakın.

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

Stok kodlarıyla adlandırılmış **aktif** ürün görsellerini içerir (**1.799 dosya**, `urun_gorselleri` tablosuyla birebir eşleşiyor). Eşleşmeyen 934 dosya `images/arsiv/products/` altındadır. Çalışma/kontrol aşaması için kullanılan kopya `images/working/products/` klasöründedir; ham eşleme raporu (`gorsel_esleme_raporu.csv`) o klasörde tutulur, derlenmiş/özetlenmiş hâli ise `reports/excel/gorsel_eslesme_raporu.xlsx`'tir.

Bu rapor; Excel satırı, stok kodu, kaynak medya dosyası, oluşturulan dosya adı ve işlem durumunu kayıt altına alır.

> Bu klasör elle yeniden adlandırılmamalı veya eski görsel klasörleriyle birleştirilmemelidir.

---

## 📂 Ana Klasör Yapısı

Bu dizin 2026-07-31'de `metaks` deposunun `veritabani/` alt dizini oldu; aşağıdaki
yollar bu dizine görelidir (depo kökünden `veritabani/...` diye okunur).

```text
veritabani/
├── archive/                    # kullanılmayan eski dosyalar (gitignored, bkz. Arşiv Yapısı)
├── backups/                    # yedek_al.sh çıktısı: pg_dump + görsel aynası (gitignored)
├── data/
│   ├── raw/                    # urun_listesi.xlsx (görsel gömülü, ~195 MB, gitignored)
│   ├── interim/                 # temizlik/normalizasyon ara dosyaları
│   ├── processed/                # temiz_urunler_final_v2.xlsx (DB'ye yüklenen)
│   └── reference/                 # kalip_bilgileri_yedek.xlsx vb.
├── docker/nginx/gorseller.conf       # görsel sunucusunun yapılandırması
├── docker-compose.yml                 # name: metaks_db (SABİT — bkz. CLAUDE.md)
├── docs/
│   ├── INFO.md                          # bu dosya
│   ├── aktif-urun-veri-sozlesmesi.md     # arayüzün okuduğu view/fonksiyon sözleşmesi
│   └── karisik_stok_kodu_kurali.md        # karışık kod çözme kuralı + kanıtı
├── images/
│   ├── working/products/                    # işlem gören görseller + gorsel_esleme_raporu.csv
│   ├── final/products/                       # aktif 1.799 görsel (DB ile eşleşen)
│   └── arsiv/products/                        # eşleşmeyen 934 görsel
├── reports/excel/                      # kontrol ve dönüşüm raporları
├── scripts/
│   ├── cleaning/                        # temizle.py, olcu_temizle.py, duzelt.py, ayir.py
│   ├── normalization/                    # birlesik_stok_kodlarini_duzelt.py, final_excel_hazirla.py
│   ├── maintenance/                       # kalip_yedekle.py, *_tekrarlarini_sil.py, yedek_al.sh
│   ├── database/                           # yukle.py, gorselleri_yukle.py, urun_ara.py
│   └── images/                              # gorsel_esle_duzeltilmis_v2.py ve türevleri
├── sql/
│   ├── 01_schema.sql                    # GÜNCEL şema (docker-compose tarafından kullanılıyor)
│   ├── migrations/                       # 001–006 + rollback'leri, ELLE uygulanır
│   └── legacy/init_db.sql                 # eski şema, hiçbir yerde kullanılmıyor
└── venv/                               # pipeline venv'i (web/venv ile karıştırılmamalı)
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

Güncel ve `docker-compose.yml` tarafından fiilen kullanılan şemadır (`docker-entrypoint-initdb.d` altına mount edilir). `sql/legacy/init_db.sql` daha eski/basit bir sürümdür ve artık konteyner tarafından kullanılmaz — referans olarak saklanmaktadır (2026-07-31'e kadar bu dizinin kökündeydi, güncel şemayla karıştırılmasın diye taşındı).

Şema **canlıda değiştirilirken bu dosya tek başına yeterli değildir**: uygulanmış her
değişiklik `sql/migrations/` altında numaralı bir dosyadır (`00N_x.sql` +
`00N_x_rollback.sql`, her biri `BEGIN`/`COMMIT` içinde). Bugün 001–006 uygulanmış
durumda; ayrıntı için `CLAUDE.md`'nin "Database schema" bölümü.

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

Aktif görsel sayısı (DB'deki `urun_gorselleri` satır sayısıyla eşit olmalı):

```bash
find images/final/products -maxdepth 1 -type f \
\( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) \
| wc -l
```

Beklenen sonuç:

```text
1799
```

Arşivdeki (eşleşmeyen) görseller ayrıca: `ls images/arsiv/products | wc -l` → `934`.

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

- ~~depo ve raf lokasyonları~~ ✅ **gerçek işletme lokasyonları girildi (2026-07-30)** —
  `Metaks`/`Depo 1`/`Fabrika` (DAHILI), `Kaplama`/`Skor` (FASON). Eski 3 test/placeholder
  satırı (Ana Depo/Sevkiyat Alanı/Fason Atölye 1) soft-deactivate edildi (`aktif_mi = false`,
  hard-delete değil — `stok_hareketleri`'ndeki 21 test kaydı bunlara FK ile bağlı).
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
- ~~stok işlem ekranı~~ ✅ **canlıda test edildi**: GİRİŞ/ÇIKIŞ/SAYIM DEVRİ/TRANSFER/
  DÜZELTME'nin beşi de çalışıyor, `yapan_kullanici` ve lokasyon ataması doğru yazılıyor.
  Bugünkü hâli `web/`in `/stok/islem/<stok_kodu>/` sayfası.
- ~~Kalan: test lokasyonları ve test hareketleri~~ ✅ **temizlendi (2026-07-31)**:
  `lokasyonlar` artık kullanıcının doğruladığı üç gerçek konum (Metaks, Fabrika, Skor),
  `stok_hareketleri` ise migration 006 ile tamamen boşaltıldı — defterdeki 30 satırın
  tamamı test girişiydi. Sayım verisi bugün hâlâ Excel'de tutuluyor.

### Faz 5: Web ERP arayüzü ✅ TAMAMLANDI (2026-07-31)

Arayüz `web/` dizininde (Django + HTMX). Bu belge veri/şema tarafını izliyor; ekranların
ayrıntısı, tasarım kararları ve yapılacaklar listesi `web/CLAUDE.md` ile
`web/YAPILACAKLAR.md`'de — burada tekrarlanmıyor.

Şema tarafından bakınca durum: `v_aktif_urunler` ürün kataloğunu,
`v_lokasyon_stok_ozet`/`v_toplam_stok` stok ekranlarını, `v_lokasyonlar_detay` ise tüm
lokasyon açılır listelerini besliyor; yazma tarafında `stok_hareketi_kaydet()` ve
`urun_kaydet()` tek kapı. Arayüzün ihtiyaç duyduğu her şey bu view/fonksiyon katmanından
geçiyor, hiçbir tablo doğrudan yazılmıyor.

- ~~ürün arama~~ ✅ `v_aktif_urunler` + katalog/stok galerileri (1.780 aktif ürün,
  35 kategori; 31 üründe kategori boş).
- ~~görsel gösterimi~~ ✅ `gorsel-sunucu` (nginx, port 8083) `images/final/products/`'ı
  salt-okunur yayınlıyor; path traversal ve dizin listeleme engellendiği test edildi.
- ~~lokasyon yönetimi~~ ✅ `/yonetim/lokasyonlar/` — hiyerarşik liste, ekleme, pasife
  alma, hiç kullanılmamışsa silme.
- ~~yönetim ana sayfası~~ ✅ `/` (Panel) — özet sayılar ve son hareketler.
- kullanıcı yetkilendirmesi — Django auth, `is_staff` yönetim panelini kapatıyor.
  Django'nun kendi tabloları 2026-07-31'den beri **aynı Postgres sunucusunda ayrı bir
  veritabanında** (`metaks_web`; öncesinde SQLite'tı). `depo_sistemi`'ye hâlâ hiç
  `migrate` çalıştırılmıyor — ayrım korundu, yalnızca motor tekleşti ve kullanıcı
  hesapları da `pg_dumpall` kapsamına girdi. İnce rol ayrımı (depo personeli vs.
  yönetici vs. fason) henüz tasarlanmadı; `web/YAPILACAKLAR.md` madde 2b.

### Faz 6: Barkod ve sipariş entegrasyonu

ChatGPT'nin Prompt 5'i ("Sipariş yönetimi") bu fazın sipariş kısmını detaylandırıyor,
henüz hiçbir parçası kurulmadı. **2026-07-30'da kullanıcı onayı**: barkod tarafı zor
değil, ama depo/ürün sistemi (Faz 4/5) tamamen bitmeden ele alınmayacak — bilinçli olarak
sona bırakıldı.

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

### Faz 8: Numune takibi (şema tarafı ✅ tamamlandı 2026-07-30)

Hangi numunenin hangi dolapta/rafta olduğunu "kütüphanede kitap bulur gibi" bulmak
("Numune Dolabı 1 · Raf 3"). Sayım devam ederken aciliyet kazandı: numune dolabını açıp
3 adet bulan kişinin bunu yazacağı dürüst bir yer yoktu.

**Bu notun önceki hâli ayrı bir varlık gerektireceğini söylüyordu — o değerlendirme
düzeltildi.** Gerekçe (numune, `urunler`'in "sadece değişmeyen fiziksel öznitelikler"
ilkesine uymaz) doğru, ama yalnızca numune yerinin `urunler` üzerinde bir **kolon**
olmasını eler; ayrı bir varlık gerektiğini kanıtlamaz. Numune fiziksel olarak ürünün bir
adedinin bir yerde durmasıdır ve "depodan numune dolabına taşındı" tam olarak bir
TRANSFER'dir — yani var olan `lokasyonlar` + `stok_hareketleri` mekanizmasına oturur.
Bu sayede numune ödünç alınıp geri konduğunda hareket kaydı bedavaya gelir.

`sql/migrations/004_numune_lokasyonlari.sql` canlıya uygulandı: `lokasyonlar.tip`'e
`NUMUNE`, iki seviyeli dolap→raf hiyerarşisi (`ust_lokasyon_id`, `kod`), yeni
`v_lokasyonlar_detay` / `v_fiziksel_stok` / `v_numune_konumlari` view'ları,
`stok_hareketi_kaydet()`'e yaprak kontrolü. `v_toplam_stok` artık **satılabilir** stok
(numune hariç). Ayrıntı: `docs/aktif-urun-veri-sozlesmesi.md`.

**Sırada ne var:** (1) iki arayüzün lokasyon açılır listeleri `v_lokasyonlar_detay` +
`yaprak_mi`'ye taşınmalı, (2) ancak ondan sonra gerçek dolap/raf satırları girilmeli.
Kaç dolap/raf olacağı henüz kullanıcıdan alınmadı.

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
arayüzün tek okuma kaynağı.

**2026-07-31 durumu.** Şema tarafında altı migration canlıya uygulanmış durumda: 001
(`katalog_durumu`), 002 (`v_lokasyon_stok_ozet`/`v_toplam_stok`), 003
(`stok_hareketi_kaydet()`), 004 (numune lokasyon hiyerarşisi + `v_lokasyonlar_detay` +
`v_fiziksel_stok`), 005 (`urun_kaydet()`), 006 (defterdeki test hareketlerinin temizliği).

Canlı verinin bugünkü hâli: **2.973 ürün** (1.780 AKTİF), **1.799 görsel**, **35
kategori**, **3 lokasyon** (Metaks, Fabrika — DAHILI; Skor — FASON) ve **0 stok
hareketi**. Defter bilerek boş: devam eden depo sayımı hâlâ Excel'de tutuluyor,
veritabanına ilk gerçek hareket girildiğinde `hareket_id` 1'den başlayacak.

Aynı gün iki yapısal değişiklik daha oldu: `metaks_DB` ve `depo-web-arayuz` repoları tek
depoda birleştirildi (`veritabani/` + `web/`), ve bir süre arayüzün yanında çalışan
düşük-kod katmanı projeden tamamen çıkarıldı — yedeği `~/arsiv-appsmith/` altında.

Faz 3 (Kalıp Modülü), Faz 6 (Barkod/sipariş) ve Faz 7 (Üretim takibi) kullanıcı
tarafından bilinçli olarak ertelendi.
