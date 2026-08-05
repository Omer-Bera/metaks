from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from . import stok_servisi
from .forms import LokasyonSecici
from .models import StokBakiye
from .stok_yonetimi import (
    _amac_iznini_denetle,
    _izinli_amaclar,
    eski_stok_url_yonlendir,
)
from .yetkiler import izni_var_mi
from .views import hareket_gecmisi, stok_listesi


class _Kullanici:
    def __init__(self, *izinler, staff=False, giris=True):
        self._izinler = set(izinler)
        self.is_staff = staff
        self.is_authenticated = giris

    def has_perm(self, izin):
        return izin in self._izinler


class StokYetkiVeYonlendirmeTestleri(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_anonim_stok_izni_alamaz(self):
        self.assertFalse(izni_var_mi(_Kullanici(giris=False), 'goruntule'))

    def test_anonim_dogrudan_stok_adresi_giris_ekranina_yonlenir(self):
        istek = self.factory.get('/stok/', HTTP_HX_REQUEST='true')
        istek.user = _Kullanici(giris=False)
        yanit = stok_listesi(istek)
        self.assertEqual(yanit.status_code, 302)
        self.assertIn(reverse('katalog:giris'), yanit.url)

    def test_oturumlu_ama_izinsiz_hareket_adresi_reddedilir(self):
        istek = self.factory.get('/stok/hareketler/', HTTP_HX_REQUEST='true')
        istek.user = _Kullanici()
        with self.assertRaises(PermissionDenied):
            hareket_gecmisi(istek)

    def test_staff_gecis_suresince_tam_yetkilidir(self):
        self.assertTrue(izni_var_mi(_Kullanici(staff=True), 'duzeltme'))
        self.assertTrue(izni_var_mi(_Kullanici(staff=True), 'fason'))

    def test_operator_izni_olmayan_amaclari_gormez(self):
        istek = self.factory.get('/stok/islem/')
        istek.user = _Kullanici('katalog.stok_islem_yap')
        amaclar = _izinli_amaclar(istek)
        self.assertNotIn('SAYIM', amaclar)
        self.assertNotIn('DUZELTME', amaclar)
        self.assertNotIn('FASON_SEVK', amaclar)
        self.assertNotIn('FIRE', amaclar)

    def test_yetkisiz_duzeltme_sunucu_tarafinda_reddedilir(self):
        istek = self.factory.post('/stok/islem/')
        istek.user = _Kullanici('katalog.stok_islem_yap')
        with self.assertRaises(PermissionDenied):
            _amac_iznini_denetle(istek, 'DUZELTME')

    def test_eski_stok_adresi_sorguyu_koruyarak_kanonik_adrese_yonlenir(self):
        istek = self.factory.get('/stok/hizli/', {'kod': '1005910'})
        yanit = eski_stok_url_yonlendir(istek)
        self.assertEqual(yanit.status_code, 302)
        self.assertEqual(yanit.url, f"{reverse('katalog:stok_merkezi')}?kod=1005910")

    def test_oneri_sabit_yolu_dinamik_stok_kodu_yoluna_dusmez(self):
        eslesen = resolve('/stok/islem/oneriler/')
        self.assertEqual(eslesen.url_name, 'stok_kodu_onerileri')

    def test_bakiye_view_bilesik_satir_anahtarini_primary_key_kullanir(self):
        self.assertEqual(StokBakiye._meta.pk.name, 'bakiye_anahtari')

    def test_urun_onerileri_sabit_yolu_kendi_view_ine_gider(self):
        eslesen = resolve('/stok/varyant/oneriler/')
        self.assertEqual(eslesen.url_name, 'urun_kodu_onerileri')


class LokasyonSeciciTestleri(SimpleTestCase):
    """Süzmenin dayandığı `data-tip` özniteliği gerçekten basılıyor mu?

    Veritabanı gerekmiyor: widget seçenekleri parametre olarak alıyor.
    """

    def _secim(self):
        secici = LokasyonSecici(choices=[('', '— seçilmedi —'), (8, 'Fabrika'), (10, 'Skor')])
        secici.tipler = {'8': 'DAHILI', '10': 'FASON'}
        return secici

    def test_lokasyon_secenekleri_tipini_tasir(self):
        html = self._secim().render('kaynak_lokasyon_id', None)
        self.assertIn('data-tip="DAHILI"', html)
        self.assertIn('data-tip="FASON"', html)

    def test_bos_secenek_tipsiz_kalir_ve_her_amacta_gorunur(self):
        # JS boş `data-tip`'i süzgeçten muaf tutuyor; dolu bir tip alsaydı
        # "— seçilmedi —" bazı amaçlarda listeden düşerdi. Öznitelik SIRASINA
        # bakılmıyor: boş seçenek `selected` de alıyor ve sıra Django'nun işi.
        html = self._secim().render('kaynak_lokasyon_id', None)
        bos_secenek = next(
            satir for satir in html.splitlines() if 'value=""' in satir
        )
        self.assertIn('data-tip=""', bos_secenek)


class TuretilmisIslemKimligiTestleri(SimpleTestCase):
    """Fason dönüşünün yanında yazılan fire belgesinin kimliği.

    İkinci belgenin kimliği rastgele olsaydı çift gönderimde dönüş atlanır ama
    fire ikinci kez yazılırdı; kararlı olması mükerrer koruma için şart.
    """

    KIMLIK = '0f7d2f9c-1c3a-4a9e-9a1a-2f5b6d8e0a11'

    def test_ayni_gonderim_ayni_kimligi_uretir(self):
        self.assertEqual(
            stok_servisi.turetilmis_islem_kimligi(self.KIMLIK, 'fason-fire'),
            stok_servisi.turetilmis_islem_kimligi(self.KIMLIK, 'fason-fire'),
        )

    def test_turetilen_kimlik_kaynaktan_farklidir(self):
        self.assertNotEqual(
            stok_servisi.turetilmis_islem_kimligi(self.KIMLIK, 'fason-fire'), self.KIMLIK
        )

    def test_farkli_gonderim_farkli_kimlik_uretir(self):
        digeri = '1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d'
        self.assertNotEqual(
            stok_servisi.turetilmis_islem_kimligi(self.KIMLIK, 'fason-fire'),
            stok_servisi.turetilmis_islem_kimligi(digeri, 'fason-fire'),
        )
