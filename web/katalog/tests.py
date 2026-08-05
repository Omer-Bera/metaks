import csv
from datetime import datetime, timezone as dt_timezone
from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse
from openpyxl import load_workbook

from . import disa_aktarim, stok_servisi, views
from .forms import LokasyonSecici
from .models import StokBakiye
from .stok_yonetimi import (
    _amac_iznini_denetle,
    _izinli_amaclar,
    eski_stok_url_yonlendir,
)
from .views import hareket_gecmisi, stok_listesi
from .yetkiler import izni_var_mi


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



class FiltreSozlesmesiTestleri(SimpleTestCase):
    def setUp(self):
        self.istek_fabrikasi = RequestFactory()

    def test_liste_disa_aktarim_urlsi_tum_filtreleri_korur_sayfayi_atlar(self):
        istek = self.istek_fabrikasi.get(
            '/katalog/',
            {
                'q': '  toka  ',
                'kategori': ['Metal', views.KATEGORISIZ],
                'stok': '1',
                'sirala': 'kod_azalan',
                'sayfa': '9',
                'bilinmeyen': 'deger',
            },
        )
        filtre = views.ListeFiltresi(istek, '/katalog/')

        url = filtre.url(yol='/katalog/disa-aktar/csv/')
        parametreler = parse_qs(urlsplit(url).query)

        self.assertEqual(urlsplit(url).path, '/katalog/disa-aktar/csv/')
        self.assertEqual(parametreler['q'], ['toka'])
        self.assertEqual(parametreler['kategori'], ['Metal', views.KATEGORISIZ])
        self.assertEqual(parametreler['stok'], ['1'])
        self.assertEqual(parametreler['sirala'], ['kod_azalan'])
        self.assertNotIn('sayfa', parametreler)
        self.assertNotIn('bilinmeyen', parametreler)

    def test_hareket_filtresi_tarihleri_ve_kanonik_urlsi_cozer(self):
        istek = self.istek_fabrikasi.get(
            '/stok/hareketler/',
            {
                'q': '  00123 ',
                'tip': 'TRANSFER',
                'lokasyon': '7',
                'kullanici': 'ömer',
                'baslangic': '2026-08-01',
                'bitis': '2026-08-04',
                'sayfa': '4',
            },
        )
        filtre = views.HareketFiltresi(istek)
        parametreler = parse_qs(urlsplit(filtre.url('/disa-aktar/xlsx/')).query)

        self.assertEqual(filtre.baslangic.isoformat(), '2026-08-01')
        self.assertEqual(filtre.bitis.isoformat(), '2026-08-04')
        self.assertEqual(parametreler['lokasyon'], ['7'])
        self.assertEqual(parametreler['kullanici'], ['ömer'])
        self.assertNotIn('sayfa', parametreler)
        self.assertIn('Başlangıç: 2026-08-01', filtre.kapsam_ozeti())

    def test_hareket_amac_filtresi_url_ve_kapsama_giriyor(self):
        # Amaç filtresi migration 008'le eklendi; dosya yolu ekranla aynı sözleşmeyi
        # kullanmazsa indirilen küme ekranda görünenden farklı olur.
        istek = self.istek_fabrikasi.get(
            '/stok/hareketler/', {'amac': 'FASON_SEVK', 'sayfa': '3'}
        )
        filtre = views.HareketFiltresi(istek)
        parametreler = parse_qs(urlsplit(filtre.url('/disa-aktar/csv/')).query)

        self.assertEqual(parametreler['amac'], ['FASON_SEVK'])
        self.assertNotIn('sayfa', parametreler)
        self.assertEqual(filtre.secili['amac'], 'FASON_SEVK')
        self.assertTrue(filtre.filtre_var)
        self.assertIn('Amaç: ', filtre.kapsam_ozeti())

    def test_stok_sku_filtreleri_dosya_kapsaminda_okunuyor(self):
        # Kapsam satırı dosyayı açan kişinin gördüğü tek filtre kaydı; 008'in SKU
        # filtreleri buraya girmezse sayı bağlamsız aktarılır.
        istek = self.istek_fabrikasi.get(
            '/stok/',
            {
                'yer': 'FASON',
                'montaj': 'MONTE',
                'stok_turu': 'SATISA_HAZIR',
                'seviye': 'KRITIK',
                'fason_durum': 'GECIKMIS',
                'parti': 'P-2026-01',
                'kaplama': '4',
            },
        )
        kapsam = views.ListeFiltresi(istek, '/stok/').kapsam_ozeti(stok_goster=True)

        self.assertIn('Yer: Fasonda', kapsam)
        self.assertIn('Montaj: monte', kapsam)
        self.assertIn('Stok türü: Satışa hazır', kapsam)
        self.assertIn('Seviye: Kritik altı', kapsam)
        self.assertIn('Fason: Gecikmiş', kapsam)
        self.assertIn('Parti: P-2026-01', kapsam)
        self.assertIn('Kaplama #4', kapsam)


class DisaAktarimEndpointTestleri(SimpleTestCase):
    def setUp(self):
        self.istek_fabrikasi = RequestFactory()

    @staticmethod
    def _csv_satirlari(yanit):
        try:
            icerik = b''.join(yanit.streaming_content).decode('utf-8-sig')
        finally:
            yanit.close()
        return list(csv.reader(StringIO(icerik), delimiter=';'))

    def test_uc_dosya_turu_urlsi_dogru_anonymous_viewa_cozulur(self):
        for url_adi, view in (
            ('katalog:urun_disa_aktar', views.urun_disa_aktar),
            ('katalog:stok_disa_aktar', views.stok_disa_aktar),
            ('katalog:hareket_disa_aktar', views.hareket_disa_aktar),
        ):
            with self.subTest(url_adi=url_adi):
                yol = reverse(url_adi, kwargs={'dosya_turu': 'csv'})
                self.assertIs(resolve(yol).func, view)

    def test_katalog_endpointi_canli_filtreyi_korur_ve_48_satirda_kesmez(self):
        satirlar = [
            (
                f'K{sira:04d}', 'Metal', 'Ana ürün', '', '', None,
                None, None, '', '', '',
            )
            for sira in range(55)
        ]
        istek = self.istek_fabrikasi.get(
            '/katalog/disa-aktar/csv/',
            {
                'q': '  toka  ',
                'kategori': ['Metal', views.KATEGORISIZ],
                'sirala': 'kod_azalan',
                'sayfa': '3',
            },
        )

        with patch.object(
            views,
            '_katalog_disa_aktarim_satirlari',
            return_value=iter(satirlar),
        ) as satir_kaynagi:
            dosya_satirlari = self._csv_satirlari(
                views.urun_disa_aktar(istek, 'csv')
            )

        filtre = satir_kaynagi.call_args.args[0]
        self.assertEqual(filtre.arama, 'toka')
        self.assertEqual(filtre.kategoriler, ['Metal', views.KATEGORISIZ])
        self.assertEqual(filtre.sirala, 'kod_azalan')
        self.assertEqual(len(dosya_satirlari) - 2, 55)

    def test_stok_endpointi_48_sinirini_asar_ve_uc_durumu_tasir(self):
        satirlar = [
            (f'S{sira:04d}', 'Metal', None, None, 'Sayılmadı')
            for sira in range(49)
        ]
        istek = self.istek_fabrikasi.get(
            '/stok/disa-aktar/csv/',
            {'stok': '1', 'sayfa': '2'},
        )

        with patch.object(
            views,
            '_stok_disa_aktarim_satirlari',
            return_value=iter(satirlar),
        ) as satir_kaynagi:
            dosya_satirlari = self._csv_satirlari(
                views.stok_disa_aktar(istek, 'csv')
            )

        filtre = satir_kaynagi.call_args.args[0]
        self.assertTrue(filtre.sadece_stok)
        self.assertEqual(len(dosya_satirlari) - 2, 49)
        self.assertEqual(dosya_satirlari[2][4], 'Sayılmadı')

    def test_hareket_endpointi_50_sinirini_asar_ve_tarih_filtresini_korur(self):
        tarih = datetime(2026, 8, 4, 9, 0, tzinfo=dt_timezone.utc)
        satirlar = [
            (tarih, f'H{sira:04d}', 'Metal', 'Giriş', 1, '', 'Depo', 'ömer', '')
            for sira in range(51)
        ]
        istek = self.istek_fabrikasi.get(
            '/stok/hareketler/disa-aktar/csv/',
            {'tip': 'GIRIS', 'baslangic': '2026-08-04', 'sayfa': '2'},
        )

        with patch.object(
            views,
            '_hareket_disa_aktarim_satirlari',
            return_value=iter(satirlar),
        ) as satir_kaynagi:
            dosya_satirlari = self._csv_satirlari(
                views.hareket_disa_aktar(istek, 'csv')
            )

        filtre = satir_kaynagi.call_args.args[0]
        self.assertEqual(filtre.tip, 'GIRIS')
        self.assertEqual(filtre.baslangic.isoformat(), '2026-08-04')
        self.assertEqual(len(dosya_satirlari) - 2, 51)


class DosyaYaziciTestleri(SimpleTestCase):
    SUTUNLAR = (
        ('Stok kodu', 18),
        ('Açıklama', 30),
        ('Tarih', 20),
        ('Miktar', 12),
    )

    @staticmethod
    def _yanit_baytlari(yanit):
        try:
            return b''.join(yanit.streaming_content)
        finally:
            yanit.close()

    def test_csv_bom_noktali_virgul_turkce_formul_ve_yerel_tarih(self):
        utc_tarih = datetime(2026, 8, 3, 21, 30, tzinfo=dt_timezone.utc)
        yanit = disa_aktarim.dosya_yaniti(
            'csv',
            'stok-durumu-2026-08-04',
            'Stok durumu',
            'Arama: Çıtçıt',
            self.SUTUNLAR,
            [
                ('00123', '=2+2', utc_tarih, 7),
                ('+ABC', 'Ç, Ğ, İ, Ö, Ş, Ü; satır', utc_tarih, 0),
            ],
        )

        ham = self._yanit_baytlari(yanit)
        self.assertTrue(ham.startswith(b'\xef\xbb\xbf'))
        satirlar = list(csv.reader(StringIO(ham.decode('utf-8-sig')), delimiter=';'))

        self.assertEqual(satirlar[0][0], 'Kapsam: Arama: Çıtçıt')
        self.assertEqual(satirlar[1], [baslik for baslik, _ in self.SUTUNLAR])
        self.assertEqual(satirlar[2], ['00123', "'=2+2", '2026-08-04 00:30:00', '7'])
        self.assertEqual(satirlar[3][0], "'+ABC")
        self.assertEqual(satirlar[3][1], 'Ç, Ğ, İ, Ö, Ş, Ü; satır')

    def test_csv_tum_satirlari_akar_ve_bos_sonucta_baslik_kalir(self):
        dolu_yanit = disa_aktarim.dosya_yaniti(
            'csv',
            'katalog-2026-08-04',
            'Katalog',
            'Tüm kayıtlar',
            (('Kod', 12),),
            ((f'{sira:05d}',) for sira in range(75)),
        )
        dolu_satirlar = list(
            csv.reader(
                StringIO(self._yanit_baytlari(dolu_yanit).decode('utf-8-sig')),
                delimiter=';',
            )
        )
        self.assertEqual(len(dolu_satirlar), 77)
        self.assertEqual(dolu_satirlar[-1], ['00074'])

        bos_yanit = disa_aktarim.dosya_yaniti(
            'csv',
            'katalog-2026-08-04',
            'Katalog',
            'Sonuç yok',
            (('Kod', 12),),
            iter(()),
        )
        bos_satirlar = list(
            csv.reader(
                StringIO(self._yanit_baytlari(bos_yanit).decode('utf-8-sig')),
                delimiter=';',
            )
        )
        self.assertEqual(bos_satirlar, [['Kapsam: Sonuç yok'], ['Kod']])

    def test_xlsx_tipleri_guvenligi_sabit_basligi_ve_filtresi(self):
        utc_tarih = datetime(2026, 8, 3, 21, 30, tzinfo=dt_timezone.utc)
        yanit = disa_aktarim.dosya_yaniti(
            'xlsx',
            'stok-hareketleri-2026-08-04',
            'Stok hareketleri',
            'Tüm kayıtlar',
            self.SUTUNLAR,
            [('00123', '=2+2', utc_tarih, 9)],
        )
        kitap = load_workbook(BytesIO(self._yanit_baytlari(yanit)), data_only=False)
        sayfa = kitap['Stok hareketleri']

        self.assertEqual(sayfa.freeze_panes, 'A3')
        self.assertEqual(sayfa.auto_filter.ref, 'A2:D3')
        self.assertEqual(sayfa['A2'].value, 'Stok kodu')
        self.assertEqual(sayfa['A3'].value, '00123')
        self.assertEqual(sayfa['A3'].data_type, 's')
        self.assertEqual(sayfa['B3'].value, '=2+2')
        self.assertEqual(sayfa['B3'].data_type, 's')
        self.assertEqual(sayfa['C3'].value, datetime(2026, 8, 4, 0, 30))
        self.assertEqual(sayfa['C3'].data_type, 'd')
        self.assertEqual(sayfa['D3'].value, 9)
        self.assertEqual(sayfa['D3'].data_type, 'n')
        kitap.close()

    def test_csv_dort_formul_baslangicini_ve_bastaki_boslugu_etkisizlestirir(self):
        degerler = ('=1+1', '+1', '-1', '@komut', '  =2+2')
        yanit = disa_aktarim.dosya_yaniti(
            'csv',
            'guvenlik-2026-08-04',
            'Güvenlik',
            'Tüm kayıtlar',
            (('Değer', 20),),
            ((deger,) for deger in degerler),
        )
        satirlar = list(
            csv.reader(
                StringIO(self._yanit_baytlari(yanit).decode('utf-8-sig')),
                delimiter=';',
            )
        )

        self.assertEqual(
            [satir[0] for satir in satirlar[2:]],
            ["'=1+1", "'+1", "'-1", "'@komut", "'  =2+2"],
        )

    def test_desteklenmeyen_bicim_404_dondurur(self):
        with self.assertRaises(Http404):
            disa_aktarim.dosya_yaniti(
                'pdf',
                'dosya-2026-08-04',
                'Sayfa',
                'Kapsam',
                (('Kod', 12),),
                (),
            )
