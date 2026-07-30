from datetime import datetime

from django.conf import settings
from django.db import models
from django.db.models import F, Func, Value


class AktifUrun(models.Model):
    """metaks_DB'deki v_aktif_urunler view'ının salt-okunur haritalaması.

    Alan adları ve sözleşme: metaks_DB/docs/aktif-urun-veri-sozlesmesi.md.
    managed = False -> Django bu tablo/view için hiçbir migration üretmez veya
    çalıştırmaz; şema tamamen metaks_DB/sql/01_schema.sql + sql/migrations/
    tarafından yönetilir. 'metaks' veritabanı bağlantısı üzerinden okunur
    (bkz. config/settings.py DATABASES).
    """

    stok_kodu = models.CharField(max_length=100, primary_key=True)
    urun_tipi = models.CharField(max_length=20)
    parent_stok_kodu = models.CharField(max_length=100, null=True)
    varyant_adi = models.CharField(max_length=255, null=True)
    olcu_mm = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    boy_ligne = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    boya_mine = models.CharField(max_length=255, null=True)
    gramaj_gr = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    montaj_durumu = models.CharField(max_length=255, null=True)
    aciklama = models.TextField(null=True)
    kritik_stok_esigi = models.IntegerField(null=True)
    kategori_id = models.IntegerField(null=True)
    kategori_adi = models.CharField(max_length=255, null=True)
    hammadde_id = models.IntegerField(null=True)
    hammadde_adi = models.CharField(max_length=255, null=True)
    kaplama_id = models.IntegerField(null=True)
    kaplama_adi = models.CharField(max_length=255, null=True)
    ana_gorsel_dosya_adi = models.CharField(max_length=255)
    arama_metni = models.TextField()

    # View'da olmayan, çalışma anında iliştirilen alanlar (views._stok_bilgisini_ekle).
    # Bunlar SADECE tip bildirimi: gövdede değer atanmadığı için Django'nun model
    # metaclass'ı bunları görmez (yalnızca Field örneklerini toplar), dolayısıyla ne
    # kolon olurlar ne migration üretirler. Amaç iki yönlü: şablonun beklediği
    # sözleşmeyi burada belgelemek ve tip denetçisinin "bilinmeyen öznitelik"
    # uyarısını kaynağında kesmek.
    toplam_stok: int | None
    stok_durumu: str  # 'var' | 'sifir' | 'sayilmadi'

    class Meta:
        managed = False
        db_table = 'v_aktif_urunler'
        ordering = ['stok_kodu']

    def __str__(self):
        return self.stok_kodu

    @property
    def gorsel_url(self):
        # gorsel-sunucu (nginx, port 8083) -> metaks_DB/CLAUDE.md, Faz 5
        return settings.GORSEL_SUNUCU_BASE_URL + self.ana_gorsel_dosya_adi


class ToplamStok(models.Model):
    """v_toplam_stok view'ının salt-okunur haritalaması (ürün başına tüm lokasyonlar).

    ÖNEMLİ: bu view'da satırı OLMAYAN ürün ile toplam_miktar=0 olan ürün aynı şey
    değil. Satır yoksa o ürün hiç sayılmamış/hiç hareket görmemiştir; 0 ise sayılmış
    ama boş çıkmıştır. Devam eden depo sayımında bu ayrım anlamlı olduğu için arayüz
    de ikisini ayrı gösteriyor (bkz. views.py::_stok_durumu).
    """

    stok_kodu = models.CharField(max_length=100, primary_key=True)
    toplam_miktar = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'v_toplam_stok'

    def __str__(self):
        return f'{self.stok_kodu}: {self.toplam_miktar}'


class Lokasyon(models.Model):
    """lokasyonlar tablosunun haritalaması — okuma İÇİN `LokasyonDetay` (aşağıda)
    tercih edilmeli, bu model asıl **yazma** (lokasyon ekleme) için var.

    Sadece `aktif_mi = True` olanlar arayüzde gösterilmeli: 2026-07-30'da eski üç
    lokasyon (Ana Depo, Sevkiyat Alanı, Fason Atölye 1) pasife alınıp yerlerine
    gerçekleri açıldı; pasif olanlar eski hareketlerde hâlâ görünüyor ama yeni işlemde
    seçilememeli.

    `ust_lokasyon` ve `kod`: metaks_DB migration 004'ün dolap→raf hiyerarşisi.
    `ust_lokasyon` NULL ise bu satır bir kök (depo/dolap), doluysa bir raf.

    `kok_mu` / `ust_kok_mu` GENERATED ALWAYS kolonları BİLEREK modele eklenmedi:
    Django INSERT'te modeldeki her alana değer yazmaya çalışır, üretilmiş bir kolona
    yazmak Postgres'te hata verir.

    `kod`'a bilerek `unique=True` KONULMADI: veritabanındaki kısıt tam bir UNIQUE
    değil, PARTIAL bir INDEX (`WHERE kod IS NOT NULL`, bkz. migration 004).
    `unique=True` koysaydık Django'nun kendi `validate_unique()`'i devreye girerdi
    ve bu, `Lokasyon._default_manager` üzerinden (yani `using('metaks')` OLMADAN)
    sorgu atar — proje henüz `DATABASE_ROUTERS` eklemediği için (CLAUDE.md) bu
    sorgu SQLite `default` bağlantısına gider ve tablo orada olmadığı için çöker.
    Aynı sebeple ekleme formu da `ModelForm.save()` değil `save(using='metaks')`
    kullanıyor (bkz. `lokasyon_yonetimi.py`). Kısıt ihlali formda önceden
    sorgulanmıyor, gerçek INSERT'in `IntegrityError`'ı yakalanıp Türkçeleştiriliyor.
    """

    lokasyon_id = models.AutoField(primary_key=True)
    lokasyon_adi = models.CharField(max_length=255)
    tip = models.CharField(max_length=50)
    aktif_mi = models.BooleanField(default=True)
    ust_lokasyon = models.ForeignKey(
        'self', models.DO_NOTHING, db_column='ust_lokasyon_id',
        null=True, blank=True, related_name='alt_lokasyonlar',
    )
    kod = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'lokasyonlar'
        ordering = ['lokasyon_adi']

    def __str__(self):
        return self.lokasyon_adi


class LokasyonDetay(models.Model):
    """v_lokasyonlar_detay view'ının salt-okunur haritalaması.

    Açılır listelerin ve lokasyon yönetimi ekranının TEK okuma kaynağı — `kod`,
    `tam_ad` (hiyerarşik görünen ad, "Numune Dolabı 1 · Raf 3") ve `yaprak_mi`
    (stok hareketi yazılabilir mi) buradan geliyor, ham `lokasyonlar`'dan değil.

    `yaprak_mi`'nin tanımı `stok_hareketi_kaydet()`'in içindeki kontrolle BİREBİR
    aynı olmalı (metaks_DB migration 004) — aksi hâlde arayüzde seçilebilen ama
    fonksiyonun reddettiği bir lokasyon oluşur.
    """

    lokasyon_id = models.IntegerField(primary_key=True)
    lokasyon_adi = models.CharField(max_length=255)
    kod = models.CharField(max_length=20, null=True)
    tip = models.CharField(max_length=50)
    aktif_mi = models.BooleanField()
    ust_lokasyon_id = models.IntegerField(null=True)
    ust_lokasyon_adi = models.CharField(max_length=255, null=True)
    ust_kod = models.CharField(max_length=20, null=True)
    tam_ad = models.CharField(max_length=511)
    yaprak_mi = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'v_lokasyonlar_detay'
        ordering = ['tam_ad']

    def __str__(self):
        return self.tam_ad


class StokHareketi(models.Model):
    """stok_hareketleri tablosunun salt-okunur haritalaması (hareket geçmişi ekranı).

    YAZMA İÇİN KULLANILMAZ. Hareket eklemenin tek yolu stok_hareketi_kaydet()
    fonksiyonudur (bkz. katalog/stok_servisi.py); bu model sadece okuma içindir.

    ZAMAN DİLİMİ TUZAĞI: islem_tarihi/created_at `timestamp without time zone` ve
    Postgres oturumu UTC olduğu için CURRENT_TIMESTAMP buraya **UTC duvar saatini
    naive olarak** yazıyor. Yani 17:41'de yapılan bir işlem tabloda 14:41 görünür.
    Django USE_TZ=True ile çalıştığından bu naive değer olduğu gibi basılırsa
    kullanıcıya 3 saat geri gösterilir. Sorgularken `yerel_tarih()` yardımcısı
    kullanılmalı: değeri UTC kabul edip timestamptz'ye çevirir, Django da şablonda
    TIME_ZONE'a (Europe/Istanbul) göre yerelleştirir.
    """

    hareket_id = models.BigAutoField(primary_key=True)
    stok_kodu = models.CharField(max_length=100)
    miktar = models.IntegerField()
    kaynak_lokasyon = models.ForeignKey(
        'Lokasyon', models.DO_NOTHING, db_column='kaynak_lokasyon_id',
        null=True, related_name='+',
    )
    hedef_lokasyon = models.ForeignKey(
        'Lokasyon', models.DO_NOTHING, db_column='hedef_lokasyon_id',
        null=True, related_name='+',
    )
    islem_tipi = models.CharField(max_length=20)
    aciklama = models.TextField(null=True)
    islem_tarihi = models.DateTimeField()
    yapan_kullanici = models.CharField(max_length=255)

    # Çalışma anında iliştirilen alanlar (views.ana_ekran, views.hareket_gecmisi).
    # Sadece tip bildirimi, kolon değil — gerekçe için bkz. AktifUrun.
    islem_etiketi: str       # ISLEM_TIPI_ETIKETLERI'nden okunur ("SAYIM_DEVRI" -> "Sayım")
    urun: AktifUrun | None   # listedeki hareketin ürünü; katalogda yoksa None
    tarih: datetime          # yerel_tarih() annotate'i (aware, Europe/Istanbul)

    class Meta:
        managed = False
        db_table = 'stok_hareketleri'
        # En yeni önce. hareket_id ikincil: aynı saniyedeki hareketler kararlı sırada
        # kalsın (sayfalama tutarlılığı için şart).
        ordering = ['-islem_tarihi', '-hareket_id']

    def __str__(self):
        return f'{self.hareket_id}: {self.islem_tipi} {self.stok_kodu} x{self.miktar}'


class Kategori(models.Model):
    """`kategoriler` tablosunun haritalaması — hem okuma (açılır liste) hem yazma
    (ürün eklerken yeni kategori açma) için.

    `kategori_adi`'na bilerek `unique=True` KONULMADI — aynı gerekçe `Lokasyon.kod`
    ile birebir (bkz. o alanın docstring'i): proje henüz `DATABASE_ROUTERS`
    eklemediği için Django'nun otomatik `validate_unique()`'i `using('metaks')`
    olmadan SQLite `default`'a giderdi. Tekillik `katalog/urun_servisi.py::
    kategori_id_cozumle()`'de büyük/küçük harf DUYARSIZ olarak elle kontrol
    ediliyor (veritabanındaki kısıt harf duyarlı, "Toka"/"TOKA" yakalanmaz).
    """

    kategori_id = models.AutoField(primary_key=True)
    kategori_adi = models.CharField(max_length=100)
    aktif_mi = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'kategoriler'
        ordering = ['kategori_adi']

    def __str__(self):
        return self.kategori_adi


class Hammadde(models.Model):
    """`hammaddeler` tablosunun salt-okunur haritalaması (ürün formundaki seçim).

    Bugünkü veride (2026-07-30) 1.780 ürünün HİÇBİRİNDE dolu değil — bu yüzden
    kategori'nin aksine formda "yeni ekle" seçeneği yok, sadece var olanlardan seçim.
    """

    hammadde_id = models.AutoField(primary_key=True)
    hammadde_adi = models.CharField(max_length=100)
    aktif_mi = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'hammaddeler'
        ordering = ['hammadde_adi']

    def __str__(self):
        return self.hammadde_adi


class Kaplama(models.Model):
    """`kaplamalar` tablosunun salt-okunur haritalaması — bkz. `Hammadde` (aynı gerekçe)."""

    kaplama_id = models.AutoField(primary_key=True)
    kaplama_adi = models.CharField(max_length=100)
    aktif_mi = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'kaplamalar'
        ordering = ['kaplama_adi']

    def __str__(self):
        return self.kaplama_adi


class Urun(models.Model):
    """`urunler` tablosunun ham haritalaması — `AktifUrun`'un (view) aksine
    PASİF/taslak satırları da kapsar.

    SADECE ürün düzenleme formunu ÖN DOLDURMAK için var. `AktifUrun` burada
    yetmez: `v_aktif_urunler` yalnızca `katalog_durumu = 'AKTIF'` satırları
    gösteriyor, ama düzenlemenin asıl anlamlı olduğu durumlardan biri tam olarak
    PASİF bir taslağı tamamlamak (görsel ekleyip AKTİF'e geçirmek) — o ürün bu
    view'da hiç yok. Ayrıca `AktifUrun`'da bulunmayan `stok_takip_edilsin_mi`,
    `kalip_versiyonu`, `katalog_durumu`, `aktif_mi` de formun ihtiyacı.

    YAZMA İÇİN KULLANILMAZ: tek yazma kapısı `urun_servisi.py::urun_kaydet()`
    (`urun_kaydet()` DB fonksiyonu). Bu model salt-okunur.
    """

    stok_kodu = models.CharField(max_length=100, primary_key=True)
    kategori_id = models.IntegerField(null=True)
    hammadde_id = models.IntegerField(null=True)
    kaplama_id = models.IntegerField(null=True)
    parent_stok_kodu = models.CharField(max_length=100, null=True)
    urun_tipi = models.CharField(max_length=20)
    varyant_adi = models.CharField(max_length=100, null=True)
    kalip_versiyonu = models.CharField(max_length=100, null=True)
    olcu_mm = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    boy_ligne = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    boya_mine = models.CharField(max_length=100, null=True)
    gramaj_gr = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    montaj_durumu = models.CharField(max_length=50, null=True)
    aciklama = models.TextField(null=True)
    kritik_stok_esigi = models.IntegerField()
    stok_takip_edilsin_mi = models.BooleanField()
    aktif_mi = models.BooleanField()
    katalog_durumu = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'urunler'

    def __str__(self):
        return self.stok_kodu


def yerel_tarih(alan='islem_tarihi'):
    """Naive UTC timestamp'i timestamptz'ye çeviren ORM ifadesi.

    Postgres'in `timezone('UTC', ts)` fonksiyonu (yani `ts AT TIME ZONE 'UTC'`)
    naive değeri UTC kabul edip timestamptz üretiyor; Django bunu aware datetime
    olarak alıyor ve şablonda TIME_ZONE'a göre yerelleştiriyor.
    """
    return Func(Value('UTC'), F(alan), function='timezone', output_field=models.DateTimeField())


class LokasyonStok(models.Model):
    """v_lokasyon_stok_ozet view'ının salt-okunur haritalaması (ürün × lokasyon).

    View'ın kendi birincil anahtarı yok (stok_kodu + lokasyon_id birlikte tekil).
    Django her modelde bir pk istediği için stok_kodu pk olarak işaretlendi — bu model
    yalnızca .filter(...) ile liste okumak için kullanılıyor, pk ile tekil erişim
    yapılmıyor, dolayısıyla bu işaretleme sorgu sonuçlarını etkilemiyor.
    """

    stok_kodu = models.CharField(max_length=100, primary_key=True)
    lokasyon_id = models.IntegerField()
    lokasyon_adi = models.CharField(max_length=255)
    lokasyon_tipi = models.CharField(max_length=50)
    mevcut_miktar = models.IntegerField()

    # Çalışma anında iliştiriliyor (views._lokasyon_stok): lokasyon artık aktif mi.
    # Sadece tip bildirimi, kolon değil — gerekçe için bkz. AktifUrun.
    pasif: bool

    class Meta:
        managed = False
        db_table = 'v_lokasyon_stok_ozet'
        ordering = ['lokasyon_adi']

    def __str__(self):
        return f'{self.stok_kodu} @ {self.lokasyon_adi}: {self.mevcut_miktar}'
