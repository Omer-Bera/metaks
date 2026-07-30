from django.conf import settings
from django.db import models


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

    class Meta:
        managed = False
        db_table = 'v_lokasyon_stok_ozet'
        ordering = ['lokasyon_adi']

    def __str__(self):
        return f'{self.stok_kodu} @ {self.lokasyon_adi}: {self.mevcut_miktar}'
