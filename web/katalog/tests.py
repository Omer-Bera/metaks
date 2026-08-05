from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

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
