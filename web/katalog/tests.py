import csv
from datetime import datetime, timezone as dt_timezone
from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse
from openpyxl import load_workbook

from . import disa_aktarim, views


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
            (f'S{sira:04d}', 'Metal', None, 'Sayılmadı')
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
        self.assertEqual(dosya_satirlari[2][3], 'Sayılmadı')

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
