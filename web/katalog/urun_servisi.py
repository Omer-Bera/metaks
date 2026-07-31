"""Ürün ekleme/düzenleme yazma katmanı.

Tek kural `stok_servisi.py` ile aynı: `urunler`'e **asla doğrudan INSERT/UPDATE
yok**, sadece `urun_kaydet()` çağrısı (metaks_DB migration 005). İş kuralları
(mod/mevcut durum tutarlılığı, kategori/hammadde/kaplama/üst ürün referans
doğrulaması, ALT_PARCA/VARYANT'ın üst ürüne bağlanma zorunluluğu, AKTİF/PASİF
geçişi) bu modülde tekrarlanmıyor — sadece parametre geçiriyor ve dönen Türkçe
mesajı taşıyor.

Görsel dosyası ayrı bir kaygı: `urun_kaydet()` yalnızca dosya ADINI (metadata)
`urun_gorselleri`'ne yazıyor, dosyanın kendisini diske yazmıyor. O iş burada —
nginx `gorsel-sunucu`'nun `:ro` bağladığı, `metaks_DB`'nin sahip olduğu
`images/final/products/` dizinine. Sıra ÖNCE dosya SONRA veritabanı: fonksiyon
hata verirse (ör. geçersiz kategori) az önce yazılan dosya silinir; ters sırada
çökme olsaydı var olmayan bir dosyayı gösteren kırık ürün kalırdı.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, connections

from .models import Kategori

MODLAR = {'EKLE', 'GUNCELLE'}

URUN_TIPLERI = [
    ('ANA_URUN', 'Ana ürün'),
    ('ALT_PARCA', 'Alt parça'),
    ('VARYANT', 'Varyant'),
]

# gorsel-sunucu (nginx, urun_gorselleri.dosya_adi bunu olduğu gibi saklıyor) sadece
# bu üçünü sunuyor bugün (metaks_DB/images/final/products üzerinde ölçüldü: 1.799
# dosyanın tamamı jpg/jpeg/png). Kapsamı genişletmek burada + Pillow'un desteklediği
# formatlar arasında ayrı bir karar.
GECERLI_UZANTILAR = {'.jpg', '.jpeg', '.png'}


class UrunIslemHatasi(Exception):
    """`urun_kaydet()`'in RAISE EXCEPTION ile döndürdüğü iş kuralı hatası.

    Mesaj zaten Türkçe ve kullanıcıya gösterilmeye uygun (ör. "\"1005120\" stok kodu
    zaten kayıtlı. Mevcut ürünü değiştirmek istiyorsanız düzenleme ekranını kullanın.").
    """


def _hata_mesaji(hata):
    """psycopg2'nin CONTEXT satırlarını atıp fonksiyonun kendi mesajını bırakır."""
    return str(hata).strip().splitlines()[0].strip()


def gorsel_dizini():
    return Path(settings.URUN_GORSEL_DIZINI)


def sonraki_gorsel_dosya_adi(stok_kodu, yuklenen_dosya):
    """`<stok_kodu>_<sıra>.<uzantı>` — sıra `urun_sonraki_gorsel_sirasi()`'ndan.

    Bu fonksiyon ayrıca çağrılıyor (urun_kaydet() içinde de aynısı tekrar
    hesaplanıyor) çünkü dosyayı DİSKE yazmadan önce adını bilmemiz gerekiyor —
    sıralama "önce dosya sonra DB". Aynı ürüne eşzamanlı iki görsel yüklemesi
    (nadir: tek ekip, tek kullanıcı bir ürünü aynı anda düzenlemez) sıra numarasında
    çakışabilir; `uq_urun_gorselleri_dosya` bunu veritabanında engeller, en kötü
    ihtimalle ikinci yükleme Türkçe bir hata mesajıyla geri döner.
    """
    uzanti = Path(yuklenen_dosya.name).suffix.lower()
    if uzanti not in GECERLI_UZANTILAR:
        raise UrunIslemHatasi(
            f'Desteklenmeyen dosya türü: "{uzanti}". '
            f'Kabul edilenler: {", ".join(sorted(GECERLI_UZANTILAR))}.'
        )
    with connections['metaks'].cursor() as imlec:
        imlec.execute('SELECT urun_sonraki_gorsel_sirasi(%s)', [stok_kodu])
        (sira,) = imlec.fetchone()
    return f'{stok_kodu}_{sira}{uzanti}'


def gorsel_yaz(dosya_adi, yuklenen_dosya):
    """Yüklenen dosyayı `gorsel-sunucu`'nun sunduğu dizine yazar."""
    hedef = gorsel_dizini() / dosya_adi
    with open(hedef, 'wb') as çıktı:
        for parça in yuklenen_dosya.chunks():
            çıktı.write(parça)


def gorsel_sil(dosya_adi):
    """`urun_kaydet()` hata verdiğinde az önce yazılan dosyayı geri alır.

    Var olmayan bir dosya için sessizce geçiliyor: `gorsel_yaz` hiç
    çağrılmadan bu noktaya gelinmiş olabilir (ör. dosya adı hesaplanırken
    hata verildi).
    """
    (gorsel_dizini() / dosya_adi).unlink(missing_ok=True)


def yeni_islem_kimligi():
    return str(uuid.uuid4())


def kategori_id_cozumle(kategori_adi):
    """Var olan kategoriyi (büyük/küçük harf duyarsız) bulur, yoksa yeni açar.

    Duyarsız arama bilinçli: `kategoriler.kategori_adi`'nin UNIQUE kısıtı
    Postgres'te varsayılan olarak harf duyarlı, yani "Toka" ile "TOKA"
    veritabanı düzeyinde farklı satırlar sayılır ve ikisi de sessizce
    açılabilirdi. Kullanıcının yazdığı isim var olan bir kategoriyle sadece
    büyük/küçük harfte ayrışıyorsa yenisini açmak yerine var olanı kullanıyoruz.
    """
    eslesen = (
        Kategori.objects.using('metaks')
        .filter(kategori_adi__iexact=kategori_adi)
        .first()
    )
    if eslesen:
        return eslesen.kategori_id
    yeni = Kategori.objects.using('metaks').create(kategori_adi=kategori_adi)
    return yeni.kategori_id


def mevcut_ana_gorsel(stok_kodu):
    """Düzenleme formunu ön doldururken gösterilecek bugünkü ana görsel dosya adı."""
    with connections['metaks'].cursor() as imlec:
        imlec.execute(
            'SELECT dosya_adi FROM urun_gorselleri '
            'WHERE stok_kodu = %s AND ana_gorsel_mi = TRUE AND aktif_mi = TRUE',
            [stok_kodu],
        )
        satir = imlec.fetchone()
    return satir[0] if satir else None


def urun_kaydet(
    *,
    mod,
    stok_kodu,
    yapan_kullanici,
    kategori_id=None,
    hammadde_id=None,
    kaplama_id=None,
    urun_tipi='ANA_URUN',
    parent_stok_kodu=None,
    varyant_adi=None,
    kalip_versiyonu=None,
    olcu_mm=None,
    boy_ligne=None,
    boya_mine=None,
    gramaj_gr=None,
    montaj_durumu=None,
    aciklama=None,
    kritik_stok_esigi=0,
    stok_takip_edilsin_mi=True,
    ana_gorsel_dosya_adi=None,
):
    """`urun_kaydet()` çağrısı. Sonucu dict olarak döndürür.

    DİKKAT — GUNCELLE modu KISMİ GÜNCELLEME DEĞİL: fonksiyon her çağrıda TÜM
    alanları yeniden yazıyor (`urunler.<alan> = p_<alan>`). Bu, "boş bırakılan
    alan dokunulmaz kalır" değil "boş bırakılan alan NULL'a döner" demek —
    tek istisna görsel (verilmezse mevcut durum korunur, aşağıya bakın). Bu
    yüzden `urun_yonetimi.urun_duzenle` formu HER ZAMAN ürünün güncel tüm
    alanlarını `initial` olarak dolduruyor; formun kendisi normal bir HTML
    formu olduğu için değiştirilmeyen alanlar zaten mevcut değerleriyle geri
    gönderiliyor — burada ayrıca bir "değişmeyenleri koru" mantığı yok.

    `ana_gorsel_dosya_adi=None` özel: GUNCELLE'de görsel HİÇ değişmez (mevcut
    ana görsel kaydı ve AKTİF/PASİF durumu olduğu gibi kalır). EKLE'de ise
    ürün görselsiz PASİF taslak olarak doğar — bu bir hata değil, kasıtlı bir
    "sonra tamamla" akışı.
    """
    if mod not in MODLAR:
        raise ValueError(f'Geçersiz mod: {mod!r}')

    with connections['metaks'].cursor() as imlec:
        try:
            imlec.execute(
                'SELECT stok_kodu, katalog_durumu, gorsel_id, mesaj '
                'FROM urun_kaydet(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '
                '%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                [
                    mod, stok_kodu, yapan_kullanici,
                    kategori_id, hammadde_id, kaplama_id,
                    urun_tipi, parent_stok_kodu, varyant_adi, kalip_versiyonu,
                    olcu_mm, boy_ligne, boya_mine, gramaj_gr, montaj_durumu,
                    aciklama, kritik_stok_esigi, stok_takip_edilsin_mi,
                    ana_gorsel_dosya_adi,
                ],
            )
        except DatabaseError as hata:
            raise UrunIslemHatasi(_hata_mesaji(hata)) from hata

        sonuc_stok_kodu, katalog_durumu, gorsel_id, mesaj = imlec.fetchone()

    return {
        'stok_kodu': sonuc_stok_kodu,
        'katalog_durumu': katalog_durumu,
        'gorsel_id': gorsel_id,
        'mesaj': mesaj,
    }
