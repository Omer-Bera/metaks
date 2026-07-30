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
