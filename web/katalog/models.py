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
    """lokasyonlar tablosunun salt-okunur haritalaması (stok işlem formundaki seçimler).

    Sadece `aktif_mi = True` olanlar arayüzde gösterilmeli: 2026-07-30'da eski üç
    lokasyon (Ana Depo, Sevkiyat Alanı, Fason Atölye 1) pasife alınıp yerlerine
    gerçekleri açıldı; pasif olanlar eski hareketlerde hâlâ görünüyor ama yeni işlemde
    seçilememeli.
    """

    lokasyon_id = models.AutoField(primary_key=True)
    lokasyon_adi = models.CharField(max_length=255)
    tip = models.CharField(max_length=50)
    aktif_mi = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'lokasyonlar'
        ordering = ['lokasyon_adi']

    def __str__(self):
        return self.lokasyon_adi


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
