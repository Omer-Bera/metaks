"""Stok işlemlerinin PostgreSQL yazma kapılarına ince Django adaptörü.

Migration 008 sonrasında yeni kayıtlar `stok_islemi_kaydet()` üzerinden yazılır;
`stok_hareketi_kaydet()` yalnız geçiş uyumluluğu içindir. Yeterli stok, amaç/defter
uyumu, SKU/parti/durum, sayım farkı, fason iş emri ve idempotency kuralları
veritabanında yaşar.

Bu modül bilinçli olarak o kuralları **tekrar etmiyor** — sadece parametreleri geçiriyor
ve fonksiyonun döndürdüğü Türkçe mesajı taşıyor. Kuralları burada da doğrulasaydık iki
kopya zamanla birbirinden ayrışırdı; tek otorite veritabanı.
"""

import json
import uuid

from django.db import DatabaseError, connections

# İşlem tipleri ve hangi lokasyonu istedikleri. Kaynak: stok_hareketleri'nin
# islem_tipi CHECK kısıtı + stok_hareketi_kaydet() gövdesindeki doğrulamalar.
# Buradaki `kaynak`/`hedef` bayrakları yalnızca formda hangi alanın gösterileceğini
# belirliyor (sunum); zorunluluğu asıl uygulayan yine veritabanı.
ISLEM_TIPLERI = [
    {
        'deger': 'GIRIS',
        'etiket': 'Giriş',
        'aciklama': 'Depoya yeni mal girişi.',
        'kaynak': False,
        'hedef': True,
        'hedef_etiketi': 'Girişin yapıldığı lokasyon',
        'miktar_etiketi': 'Giren miktar',
    },
    {
        'deger': 'CIKIS',
        'etiket': 'Çıkış',
        'aciklama': 'Depodan mal çıkışı.',
        'kaynak': True,
        'hedef': False,
        'kaynak_etiketi': 'Çıkışın yapıldığı lokasyon',
        'miktar_etiketi': 'Çıkan miktar',
    },
    {
        'deger': 'TRANSFER',
        'etiket': 'Transfer',
        'aciklama': 'İki lokasyon arasında taşıma. Toplam stok değişmez.',
        'kaynak': True,
        'hedef': True,
        'kaynak_etiketi': 'Nereden',
        'hedef_etiketi': 'Nereye',
        'miktar_etiketi': 'Taşınan miktar',
    },
    {
        'deger': 'SAYIM_DEVRI',
        'etiket': 'Sayım',
        # Sözleşmedeki kesinleşmiş kural: personel FARKI değil, saydığı TOPLAMI girer.
        # Farkı fonksiyon kendisi hesaplıyor. Personelin sistemdeki mevcut rakamı bilip
        # çıkarma yapması istenmiyor: hem önyargı yaratır hem elle hata payı ekler.
        'aciklama': 'Fiziksel sayım sonucu. Farkı değil, saydığınız TOPLAMI girin.',
        'kaynak': False,
        'hedef': True,
        'hedef_etiketi': 'Sayımın yapıldığı lokasyon',
        'miktar_etiketi': 'Sayılan toplam miktar',
    },
    {
        'deger': 'DUZELTME',
        'etiket': 'Düzeltme',
        'aciklama': 'Hatalı kaydın düzeltilmesi. Artırmak için "nereye", azaltmak için '
                    '"nereden" lokasyonunu doldurun.',
        'kaynak': True,
        'hedef': True,
        'kaynak_etiketi': 'Azaltılacak lokasyon',
        'hedef_etiketi': 'Artırılacak lokasyon',
        'miktar_etiketi': 'Düzeltme miktarı',
    },
]

ISLEM_TIPI_DEGERLERI = {tip['deger'] for tip in ISLEM_TIPLERI}

# --------------------------------------------------------------------------------------
# Kova (stok partisi) alanları — veritabani migration 007
#
# Kaplama rengi, kaplama çeşidi ve montaj birlikte bir stok "kovası" tanımlıyor:
# aynı stok kodunun "light gold / askıda / montajlı" stoğu ile "ham / dolap /
# montajsız" stoğu AYRI izleniyor ve çıkışta hangi kovadan düşüleceği sorulmak
# zorunda. Yeterli stok kontrolü de kova bazında (bkz. stok_hareketi_kaydet).
#
# Boya ve mine bilerek kovanın DIŞINDA: ikisi de serbest metin ve kimlik anahtarına
# girerlerse "kırmızı"/"Kırmızı"/"kırmızı " üç ayrı kova açar, stok sessizce
# kaybolurdu. Onlar partinin açıklayıcı bilgisi.
#
# Kaplama RENKLERİ burada sabit değil — `kaplamalar` tablosundan okunuyor
# (kaplama_secenekleri), çünkü yeni renk eklemek migration değil tek INSERT olsun.
# --------------------------------------------------------------------------------------

KAPLAMA_CESITLERI = [
    ('ASKIDA', 'Askıda'),
    ('DOLAP', 'Dolap'),
]

KAPLAMA_CESIDI_DEGERLERI = {deger for deger, _ in KAPLAMA_CESITLERI}

# BooleanField değil ChoiceField: "Evet/Hayır" üç durumlu olmak zorunda —
# işaretlenmemiş bir checkbox "hayır" mı "belirtilmedi" mi ayırt edilemezdi,
# oysa kova kimliğinde NULL (belirtilmemiş) ile FALSE (montajsız) AYRI kovalar.
MONTAJ_SECENEKLERI = [
    ('', '— belirtilmedi —'),
    ('EVET', 'Evet'),
    ('HAYIR', 'Hayır'),
]

MONTAJ_DEGERLERI = {'EVET': True, 'HAYIR': False}


def montaj_cozumle(deger):
    """Form değerini ('EVET'/'HAYIR'/'') veritabanının beklediği BOOLEAN/None'a çevirir."""
    return MONTAJ_DEGERLERI.get((deger or '').strip().upper())


def kaplama_secenekleri():
    """`kaplamalar` tablosundaki aktif renkler — (id, ad) çiftleri.

    Sabit liste DEĞİL: migration 007 onbir rengi tabloya yükledi ve yeni renk
    eklemek tek INSERT. Burada sabitleseydik tablo ile kod ayrışırdı.
    """
    from .models import Kaplama

    return list(
        Kaplama.objects.using('metaks')
        .filter(aktif_mi=True)
        .order_by('kaplama_adi')
        .values_list('kaplama_id', 'kaplama_adi')
    )

# Hareket geçmişinde ham değerleri ('SAYIM_DEVRI') değil okunur etiketleri göstermek için.
ISLEM_TIPI_ETIKETLERI = {tip['deger']: tip['etiket'] for tip in ISLEM_TIPLERI}

# Kullanıcı teknik GIRIS/CIKIS seçmez; iş amacını seçer. View bu amaçtan gereken
# defter satırlarını üretir, veritabanı da nedeni başlıkta saklar.
ISLEM_AMACLARI = [
    ('SATIN_ALMA_KABUL', 'Satın alma kabulü'),
    ('URETIM_GIRIS', 'Üretimden giriş'),
    ('SATIS_SEVKI', 'Satış sevkiyatı'),
    ('IC_TRANSFER', 'Yer değiştir'),
    ('FASON_SEVK', 'Fasona gönder'),
    ('FASON_DONUS', 'Fasondan al'),
    ('FIRE', 'Fason fire kaydı'),
    ('SAYIM', 'Sayım'),
    ('DUZELTME', 'Düzeltme'),
]

ISLEM_AMACI_ETIKETLERI = dict(ISLEM_AMACLARI)
STOK_DURUMLARI = [
    ('SERBEST', 'Serbest'),
    ('KALITE_BEKLIYOR', 'Kalite bekliyor'),
    ('BLOKE', 'Bloke'),
]
MONTAJ_DURUMLARI = [
    ('HAM', 'Ham'),
    ('YARI_MONTE', 'Yarı monte'),
    ('MONTE', 'Monte'),
]


class StokIslemHatasi(Exception):
    """PostgreSQL yazma kapılarının RAISE EXCEPTION ile döndürdüğü iş kuralı hatası.

    Mesaj zaten Türkçe ve kullanıcıya gösterilmeye uygun (ör. "Yetersiz stok: bu
    lokasyonda 5 adet var, 10 adet çıkış isteniyor.").
    """


def yeni_islem_kimligi():
    """Mükerrer gönderim koruması için istemci işlem kimliği.

    Form her basıldığında yeni bir UUID gömülüyor; kullanıcı çift tıklarsa ya da ağ
    isteği tekrarlanırsa aynı kimlik gider ve fonksiyon ikinci satırı yazmaz
    (`stok_islemleri.istemci_islem_kimligi`). Asıl güvence veritabanındaki UNIQUE kısıt —
    butonu pasifleştirmek tek başına yeterli değil, ağ tekrarı onu atlayabilir.
    """
    return str(uuid.uuid4())


def _hata_mesaji(hata):
    """psycopg2'nin CONTEXT satırlarını atıp fonksiyonun kendi mesajını bırakır."""
    return str(hata).strip().splitlines()[0].strip()


def hareket_kaydet(
    *,
    istemci_kimligi,
    stok_kodu,
    islem_tipi,
    miktar,
    kaynak_lokasyon_id,
    hedef_lokasyon_id,
    aciklama,
    yapan_kullanici,
    kaplama_id=None,
    kaplama_cesidi=None,
    montaj=None,
    boya=None,
    mine=None,
):
    """stok_hareketi_kaydet() çağrısı. Sonucu dict olarak döndürür.

    `atlandi=True` iki durumda gelir ve ikisi de hata değildir: aynı istemci kimliği
    daha önce kaydedilmiştir (mükerrer gönderim), ya da sayılan miktar sistemdekiyle
    aynıdır (yazacak fark yok).

    Kova alanları (kaplama_id/kaplama_cesidi/montaj) hepsi opsiyonel ve varsayılanları
    None: belirtilmezse hareket "belirtilmemiş kaplama" kovasına düşer. Bu, migration
    007 öncesi yazılmış 5 hareketin bugünkü durumu ve doğru olan da bu — geçmiş
    hareketlere uydurma bir renk atamaktansa "bilinmiyor" demek.

    TRANSFER'de kova TAŞINIR: mal fiziksel olarak aynı kaplamada kaldığı için tek
    parametre seti hareketin iki ucuna da uygulanıyor (fonksiyonun kendi davranışı).
    """
    with connections['metaks'].cursor() as imlec:
        try:
            imlec.execute(
                'SELECT hareket_id, uygulanan_miktar, atlandi, mesaj '
                'FROM stok_hareketi_kaydet(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                [
                    istemci_kimligi,
                    stok_kodu,
                    islem_tipi,
                    miktar,
                    kaynak_lokasyon_id,
                    hedef_lokasyon_id,
                    aciklama or None,
                    yapan_kullanici,
                    kaplama_id,
                    kaplama_cesidi or None,
                    montaj,
                    boya or None,
                    mine or None,
                ],
            )
        except DatabaseError as hata:
            raise StokIslemHatasi(_hata_mesaji(hata)) from hata

        hareket_id, uygulanan_miktar, atlandi, mesaj = imlec.fetchone()

    return {
        'hareket_id': hareket_id,
        'uygulanan_miktar': uygulanan_miktar,
        'atlandi': atlandi,
        'mesaj': mesaj,
    }


def stok_islemi_kaydet(
    *,
    istemci_kimligi,
    islem_nedeni,
    satirlar,
    yapan_kullanici,
    is_ortagi_id=None,
    belge_no='',
    fason_is_emri_id=None,
    duzelttigi_stok_islem_id=None,
    aciklama='',
):
    """Migration 008'in çok satırlı, atomik stok belgesi yazma kapısı."""
    with connections['metaks'].cursor() as imlec:
        try:
            imlec.execute(
                'SELECT stok_islem_id, hareket_sayisi, atlandi, mesaj '
                'FROM stok_islemi_kaydet(%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)',
                [
                    istemci_kimligi,
                    islem_nedeni,
                    is_ortagi_id,
                    belge_no or None,
                    fason_is_emri_id,
                    duzelttigi_stok_islem_id,
                    aciklama or None,
                    yapan_kullanici,
                    json.dumps(satirlar),
                ],
            )
        except DatabaseError as hata:
            raise StokIslemHatasi(_hata_mesaji(hata)) from hata

        stok_islem_id, hareket_sayisi, atlandi, mesaj = imlec.fetchone()
    return {
        'stok_islem_id': stok_islem_id,
        'hareket_sayisi': hareket_sayisi,
        'atlandi': atlandi,
        'mesaj': mesaj,
    }


def stok_kalemi_kaydet(
    *, urun_kodu, kaplama_id, boya_renk, mine_renk, montaj_durumu, yapan_kullanici
):
    """Gerçekten kullanılan tek bir ürün varyantı için SKU üretir."""
    with connections['metaks'].cursor() as imlec:
        try:
            imlec.execute(
                'SELECT stok_kalemi_id, sku_kodu, atlandi, mesaj '
                'FROM stok_kalemi_kaydet(%s, %s, %s, %s, %s, %s)',
                [
                    urun_kodu, kaplama_id, boya_renk or None, mine_renk or None,
                    montaj_durumu, yapan_kullanici,
                ],
            )
        except DatabaseError as hata:
            raise StokIslemHatasi(_hata_mesaji(hata)) from hata
        stok_kalemi_id, sku_kodu, atlandi, mesaj = imlec.fetchone()
    return {
        'stok_kalemi_id': stok_kalemi_id,
        'sku_kodu': sku_kodu,
        'atlandi': atlandi,
        'mesaj': mesaj,
    }


def fason_is_emri_kaydet(
    *,
    istemci_kimligi,
    is_ortagi_id,
    fason_lokasyon_id,
    kaynak_stok_kalemi_id,
    hedef_stok_kalemi_id,
    islem_turu,
    planlanan_miktar,
    beklenen_donus_tarihi,
    kaplama_cesidi,
    aciklama,
    yapan_kullanici,
):
    with connections['metaks'].cursor() as imlec:
        try:
            imlec.execute(
                'SELECT fason_is_emri_id, emir_no, atlandi, mesaj '
                'FROM fason_is_emri_kaydet(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                [
                    istemci_kimligi, is_ortagi_id, fason_lokasyon_id,
                    kaynak_stok_kalemi_id, hedef_stok_kalemi_id, islem_turu,
                    planlanan_miktar, beklenen_donus_tarihi, kaplama_cesidi or None,
                    aciklama or None, yapan_kullanici,
                ],
            )
        except DatabaseError as hata:
            raise StokIslemHatasi(_hata_mesaji(hata)) from hata
        fason_is_emri_id, emir_no, atlandi, mesaj = imlec.fetchone()
    return {
        'fason_is_emri_id': fason_is_emri_id,
        'emir_no': emir_no,
        'atlandi': atlandi,
        'mesaj': mesaj,
    }


def is_ortagi_kaydet(*, kod, unvan, roller, yapan_kullanici):
    with connections['metaks'].cursor() as imlec:
        try:
            imlec.execute(
                'SELECT is_ortagi_id, atlandi, mesaj '
                'FROM is_ortagi_kaydet(%s, %s, %s::jsonb, %s)',
                [kod, unvan, json.dumps(roller), yapan_kullanici],
            )
        except DatabaseError as hata:
            raise StokIslemHatasi(_hata_mesaji(hata)) from hata
        is_ortagi_id, atlandi, mesaj = imlec.fetchone()
    return {'is_ortagi_id': is_ortagi_id, 'atlandi': atlandi, 'mesaj': mesaj}
