"""Stok hareketi yazma katmanı.

Tek kural: `stok_hareketleri`'ne **asla doğrudan INSERT yok**, sadece
`stok_hareketi_kaydet()` çağrısı (metaks_DB/CLAUDE.md; Appsmith de aynı kurala uyuyor).
Bunun sebebi iş kurallarının tek bir yerde, veritabanında yaşaması: yeterli stok
kontrolü, işlem tipine göre lokasyon zorunlulukları, SAYIM_DEVRI'nin fark hesabı ve
mükerrer gönderim koruması hep o fonksiyonun içinde.

Bu modül bilinçli olarak o kuralları **tekrar etmiyor** — sadece parametreleri geçiriyor
ve fonksiyonun döndürdüğü Türkçe mesajı taşıyor. Kuralları burada da doğrulasaydık iki
kopya zamanla birbirinden ayrışırdı; tek otorite veritabanı.
"""

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


class StokIslemHatasi(Exception):
    """stok_hareketi_kaydet()'in RAISE EXCEPTION ile döndürdüğü iş kuralı hatası.

    Mesaj zaten Türkçe ve kullanıcıya gösterilmeye uygun (ör. "Yetersiz stok: bu
    lokasyonda 5 adet var, 10 adet çıkış isteniyor.").
    """


def yeni_islem_kimligi():
    """Mükerrer gönderim koruması için istemci işlem kimliği.

    Form her basıldığında yeni bir UUID gömülüyor; kullanıcı çift tıklarsa ya da ağ
    isteği tekrarlanırsa aynı kimlik gider ve fonksiyon ikinci satırı yazmaz
    (uq_stok_hareketleri_istemci_kimligi). Asıl güvence veritabanındaki UNIQUE kısıt —
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
):
    """stok_hareketi_kaydet() çağrısı. Sonucu dict olarak döndürür.

    `atlandi=True` iki durumda gelir ve ikisi de hata değildir: aynı istemci kimliği
    daha önce kaydedilmiştir (mükerrer gönderim), ya da sayılan miktar sistemdekiyle
    aynıdır (yazacak fark yok).
    """
    with connections['metaks'].cursor() as imlec:
        try:
            imlec.execute(
                'SELECT hareket_id, uygulanan_miktar, atlandi, mesaj '
                'FROM stok_hareketi_kaydet(%s, %s, %s, %s, %s, %s, %s, %s)',
                [
                    istemci_kimligi,
                    stok_kodu,
                    islem_tipi,
                    miktar,
                    kaynak_lokasyon_id,
                    hedef_lokasyon_id,
                    aciklama or None,
                    yapan_kullanici,
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
