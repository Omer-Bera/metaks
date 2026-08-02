from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Subquery
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import forms, stok_servisi
from .models import (
    AktifUrun,
    Kategori,
    Lokasyon,
    LokasyonDetay,
    LokasyonStok,
    StokHareketi,
    ToplamStok,
    Urun,
    yerel_tarih,
)

# Kart ızgarasının bir "sayfası". 2/3/4/6 kolona tam bölünüyor (bkz. _urun_kartlari.html
# breakpoint'leri) — son satır yarım kalmıyor.
SAYFA_BOYUTU = 48

# kategori_adi'nin NULL olduğu ürünler (2026-07-30: 1.780 ürünün 31'i) de filtrelenebilir
# olmalı; boş string "tüm kategoriler" anlamına geldiği için NULL'a ayrı bir sentinel gerekti.
KATEGORISIZ = '__kategorisiz__'

# Sıralama seçenekleri, tek yerde: anahtar -> (order_by ifadesi, arayüz etiketi).
# Şu an sadece stok_kodu üzerinden — "en son eklenen" bilinçli olarak yok, çünkü veride
# ürün başına gerçek bir ekleme zamanı bulunmuyor: urunler.created_at tüm satırlarda
# toplu yüklemenin tek timestamp'i (2026-07-28 21:31:10) ve v_aktif_urunler'da hiç yok.
# Sipariş verisi de henüz yok. Azalan stok kodu, o ihtiyacın bugünkü tek yaklaşık karşılığı.
SIRALAMALAR = {
    'kod_artan': ('stok_kodu', 'Stok kodu (artan)'),
    'kod_azalan': ('-stok_kodu', 'Stok kodu (azalan)'),
}
VARSAYILAN_SIRALAMA = 'kod_artan'


# Kullanıcının "giriş yapmadan devam et" dediğini session'da tutan anahtar.
# Kapının her açılışta değil, tarayıcı başına bir kez görünmesini sağlıyor: katalog
# ön büroda müşteri karşısında hızla açılan bir ekran, her seferinde araya bir sayfa
# koymak günde onlarca gereksiz tıklama olurdu. Çıkışta session flush edildiği için
# (Django'nun logout()'u) bu bayrak da temizlenir — "Çıkış" güvenilir biçimde giriş
# ekranına döner.
MISAFIR_ANAHTARI = 'misafir'


def misafir_devam(request):
    """"Giriş yapmadan devam et" — seçimi işaretleyip panele geçer."""
    request.session[MISAFIR_ANAHTARI] = True
    return redirect('katalog:ana_ekran')


def ana_ekran(request):
    """Panel: modüllere yönlendirme + sistemin özet sayıları + son hareketler.

    Aynı zamanda kök URL'in yönlendiricisi: giriş yapılmamış ve daha önce misafir
    olarak devam edilmemişse giriş ekranına gönderir. Giriş formu burada değil
    /giris/'te duruyor — iki kopya form olmasın diye yönlendirme tercih edildi.

    Sayılar bilinçli olarak grafiksiz: hepsi tek anlık değer, yani doğru biçim stat
    tile / meter — tek çubuklu grafik değil. Uydurma metrik yok, hepsi doğrudan
    v_aktif_urunler / v_toplam_stok / lokasyonlar'dan sayılıyor.
    """
    if not request.user.is_authenticated and not request.session.get(MISAFIR_ANAHTARI):
        return redirect('katalog:giris')

    urunler = AktifUrun.objects.using('metaks')
    aktif_urun = urunler.count()

    # Hareket görmüş ürün sayısı: v_toplam_stok'ta satırı olanlar. Sayım ilerlemesinin
    # bugünkü tek dürüst ölçüsü — "stoğu >0 olan" değil, çünkü sayılıp boş çıkan da
    # sayılmış sayılır (bkz. stok verisinin üç durumu).
    hareketli_urun = ToplamStok.objects.using('metaks').count()
    stogu_olan = ToplamStok.objects.using('metaks').filter(toplam_miktar__gt=0).count()

    # yerel_tarih(): stok_hareketleri'ndeki naive UTC damgasını aware hâle getiriyor,
    # yoksa şablon onu yerel saat sanıp 3 saat geri gösteriyor (bkz. models.py).
    son_hareketler = list(
        StokHareketi.objects.using('metaks')
        .annotate(tarih=yerel_tarih())
        .select_related('kaynak_lokasyon', 'hedef_lokasyon')[:5]
    )
    for hareket in son_hareketler:
        hareket.islem_etiketi = stok_servisi.ISLEM_TIPI_ETIKETLERI.get(
            hareket.islem_tipi, hareket.islem_tipi
        )

    return render(
        request,
        'katalog/ana_ekran.html',
        {
            'aktif_urun': aktif_urun,
            'kategori_sayisi': (
                urunler.exclude(kategori_adi__isnull=True)
                .order_by()  # Meta.ordering distinct'e sızmasın
                .values('kategori_adi')
                .distinct()
                .count()
            ),
            # yaprak_mi şart: migration 004'ten sonra "aktif lokasyon" ham lokasyonlar
            # tablosundan sayılırsa numune dolapları da (raflarının üstü, kendisi hiç
            # stok tutmaz) depo/dolap gibi sayılır ve bu tile "5 aktif lokasyon"
            # yerine "23" gibi yanıltıcı bir sayı gösterir. Doğru sayı: gerçekten stok
            # yazılabilen (yaprak) ve aktif lokasyon sayısı.
            'aktif_lokasyon': LokasyonDetay.objects.using('metaks')
            .filter(aktif_mi=True, yaprak_mi=True)
            .count(),
            'hareketli_urun': hareketli_urun,
            'stogu_olan': stogu_olan,
            'sayim_yuzdesi': round(100 * hareketli_urun / aktif_urun, 1) if aktif_urun else 0,
            'son_hareketler': son_hareketler,
        },
    )


# --------------------------------------------------------------------------------------
# Ortak filtre altyapısı — hem katalog hem stok sayfası aynı arama/kategori/sıralama
# davranışını kullanıyor. İki sayfa arasındaki tek fark stok bilgisinin gösterilmesi
# ve "sadece stokta olanlar" filtresi (bkz. stok_listesi).
# --------------------------------------------------------------------------------------


class ListeFiltresi:
    """İstekteki filtre parametrelerini okur, queryset'e uygular ve URL'lerini üretir.

    Sayfalar arasında paylaşıldığı için `yol` (hangi sayfanın URL'i) ve `sadece_stok`
    da durumun parçası: üretilen her bağlantı kendi sayfasında kalıyor.
    """

    def __init__(self, request, yol):
        self.yol = yol
        self.arama = request.GET.get('q', '').strip()
        self.kategoriler = [k for k in request.GET.getlist('kategori') if k]
        self.sadece_stok = request.GET.get('stok') == '1'
        self.sirala = request.GET.get('sirala', VARSAYILAN_SIRALAMA)
        if self.sirala not in SIRALAMALAR:
            self.sirala = VARSAYILAN_SIRALAMA

    @property
    def filtre_var(self):
        return bool(self.arama or self.kategoriler or self.sadece_stok)

    def url(self, *, kategoriler=None, arama=None, sadece_stok=None, **ekstra):
        """Bu filtrenin URL'ini üretir; verilen alanlar geçersiz kılınır.

        Varsayılan değerler dışarıda bırakılıyor, böylece URL'ler temiz kalıyor
        ("/" == "/?sirala=kod_artan").
        """
        parametreler = QueryDict(mutable=True)
        arama = self.arama if arama is None else arama
        kategoriler = self.kategoriler if kategoriler is None else kategoriler
        sadece_stok = self.sadece_stok if sadece_stok is None else sadece_stok

        if arama:
            parametreler['q'] = arama
        if kategoriler:
            parametreler.setlist('kategori', kategoriler)
        if sadece_stok:
            parametreler['stok'] = '1'
        if self.sirala != VARSAYILAN_SIRALAMA:
            parametreler['sirala'] = self.sirala
        for anahtar, deger in ekstra.items():
            parametreler[anahtar] = deger

        sorgu = parametreler.urlencode()
        return f'{self.yol}?{sorgu}' if sorgu else self.yol

    def kategori_degistir(self, kategori):
        """Bir kategoriyi seçime ekleyip çıkaran URL (aç/kapa) — panel satırları için."""
        if kategori in self.kategoriler:
            yeni = [k for k in self.kategoriler if k != kategori]
        else:
            yeni = self.kategoriler + [kategori]
        return self.url(kategoriler=yeni)

    def aramaya_uygula(self, queryset):
        """Serbest metin aramasını v_aktif_urunler.arama_metni üzerinde uygular.

        arama_metni, stok_kodu + kategori/hammadde/kaplama adı + açıklamanın küçük harfe
        çevrilmiş birleşimi (bkz. veritabani/docs/aktif-urun-veri-sozlesmesi.md) — tek bir
        ILIKE ile hepsinde arama yapılabiliyor. .lower(), sözleşmedeki örnek sorgunun
        (`ILIKE '%' || lower(...) || '%'`) aynısı.
        """
        if self.arama:
            queryset = queryset.filter(arama_metni__icontains=self.arama.lower())
        return queryset

    def uygula(self, queryset):
        queryset = self.aramaya_uygula(queryset)

        if self.kategoriler:
            adlar = [k for k in self.kategoriler if k != KATEGORISIZ]
            kosul = Q()
            if adlar:
                kosul |= Q(kategori_adi__in=adlar)
            if KATEGORISIZ in self.kategoriler:
                kosul |= Q(kategori_adi__isnull=True)
            queryset = queryset.filter(kosul)

        if self.sadece_stok:
            # v_toplam_stok'ta satırı olmayan ürün "hiç sayılmadı" demek; buradaki filtre
            # yalnızca gerçekten stoğu olanları (>0) bırakıyor.
            stoklu = (
                ToplamStok.objects.using('metaks')
                .filter(toplam_miktar__gt=0)
                .values('stok_kodu')
            )
            queryset = queryset.filter(stok_kodu__in=Subquery(stoklu))

        return queryset.order_by(SIRALAMALAR[self.sirala][0])


def _kategori_secenekleri(filtre):
    """Kategori panelinin satırları: ad + ürün sayısı + aç/kapa URL'i.

    Sayılar aramaya (ve stok filtresine) göre daralır ama kategori seçimine göre
    daralmaz (faceted search): kullanıcı "toka" yazdığında her satırın yanında o
    aramanın o kategoride kaç sonuç verdiğini görür, kendi seçtiği kategori diğer
    sayıları sıfırlamaz.
    """
    temel = filtre.aramaya_uygula(AktifUrun.objects.using('metaks').all())
    if filtre.sadece_stok:
        stoklu = (
            ToplamStok.objects.using('metaks').filter(toplam_miktar__gt=0).values('stok_kodu')
        )
        temel = temel.filter(stok_kodu__in=Subquery(stoklu))

    dagilim = (
        temel.values('kategori_adi')
        .order_by()  # Meta.ordering'in GROUP BY'a sızmaması için
        .annotate(adet=Count('stok_kodu'))
        .order_by('-adet', 'kategori_adi')
    )

    secenekler = [
        {
            'deger': satir['kategori_adi'] or KATEGORISIZ,
            'etiket': satir['kategori_adi'] or 'Kategorisiz',
            'adet': satir['adet'],
            'secili': (satir['kategori_adi'] or KATEGORISIZ) in filtre.kategoriler,
            'url': filtre.kategori_degistir(satir['kategori_adi'] or KATEGORISIZ),
        }
        for satir in dagilim
    ]

    # Arama, seçili bir kategoride hiç sonuç bırakmadıysa o kategori dağılımdan düşer ve
    # satırı kaybolur — kullanıcı da seçimden çıkamaz hâle gelir. Sıfır sayısıyla ekle.
    gorunen = {secenek['deger'] for secenek in secenekler}
    for kategori in filtre.kategoriler:
        if kategori not in gorunen:
            secenekler.insert(
                0,
                {
                    'deger': kategori,
                    'etiket': 'Kategorisiz' if kategori == KATEGORISIZ else kategori,
                    'adet': 0,
                    'secili': True,
                    'url': filtre.kategori_degistir(kategori),
                },
            )
    return secenekler


def _secili_kategori_seritleri(filtre):
    """Sonuçların üstünde görünen, tek tıkla kaldırılabilen seçim şeritleri."""
    return [
        {
            'etiket': 'Kategorisiz' if kategori == KATEGORISIZ else kategori,
            'url': filtre.kategori_degistir(kategori),
        }
        for kategori in filtre.kategoriler
    ]


def _stok_bilgisini_ekle(urunler):
    """Sayfadaki ürünlere toplam stoğu iliştirir (tek ek sorgu, N+1 yok).

    `toplam_stok` None kalırsa o ürün v_toplam_stok'ta yok demektir: hiç sayılmamış.
    0 ise sayılmış ama boş çıkmış. Şablon bu ikisini ayrı gösteriyor.
    """
    kodlar = [urun.stok_kodu for urun in urunler]
    if not kodlar:
        return urunler
    stoklar = dict(
        ToplamStok.objects.using('metaks')
        .filter(stok_kodu__in=kodlar)
        .values_list('stok_kodu', 'toplam_miktar')
    )
    for urun in urunler:
        miktar = stoklar.get(urun.stok_kodu)
        urun.toplam_stok = miktar
        # Durum şablonda değil burada belirleniyor: Django şablon dilinde None
        # karşılaştırması yok, ayrıca "hiç sayılmadı" ile "sayıldı, sıfır" ayrımı
        # tek yerde tanımlı kalsın.
        urun.stok_durumu = (
            'sayilmadi' if miktar is None else ('var' if miktar > 0 else 'sifir')
        )
    return urunler


def _liste_context(request, filtre, *, stok_goster):
    """İki liste sayfasının ortak context'i."""
    urunler = filtre.uygula(AktifUrun.objects.using('metaks').all())

    sayfalayici = Paginator(urunler, SAYFA_BOYUTU)
    sayfa = sayfalayici.get_page(request.GET.get('sayfa'))

    if stok_goster:
        _stok_bilgisini_ekle(sayfa.object_list)

    return {
        'sayfa': sayfa,
        'filtre': filtre,
        'stok_goster': stok_goster,
        'siralamalar': [(anahtar, etiket) for anahtar, (_, etiket) in SIRALAMALAR.items()],
        'kategori_secenekleri': _kategori_secenekleri(filtre),
        'secili_seritler': _secili_kategori_seritleri(filtre),
        'toplam': sayfalayici.count,
        'temiz_url': filtre.url(arama='', kategoriler=[], sadece_stok=False),
        'stok_ac_url': filtre.url(sadece_stok=True),
        'stok_kapat_url': filtre.url(sadece_stok=False),
        'sonraki_url': (
            filtre.url(sayfa=sayfa.next_page_number()) if sayfa.has_next() else None
        ),
    }


def _liste_yanit(request, context):
    """Aynı URL'den üç farklı yanıt: sayfalama parçası, filtre bloğu veya tam sayfa."""
    if request.headers.get('HX-Request'):
        if context['sayfa'].number > 1:
            return render(request, 'katalog/_urun_kartlari.html', context)
        return render(request, 'katalog/_govde_yanit.html', context)
    return render(request, 'katalog/liste.html', context)


def urun_listesi(request):
    """Ürün kataloğu: görsel galeri, stok bilgisi göstermez.

    Ön büroda müşteriye ürün gösterirken kullanılıyor — orada ilgilenilen şey ürünün
    kendisi, deposu değil. Stok görünümü bilinçli olarak ayrı sayfada (stok_listesi).
    """
    filtre = ListeFiltresi(request, reverse('katalog:urun_listesi'))
    context = _liste_context(request, filtre, stok_goster=False)
    context.update({
        'sayfa_basligi': 'Ürün Kataloğu',
        'aktif_sekme': 'katalog',
        'detay_url_adi': 'katalog:urun_detay',
    })
    return _liste_yanit(request, context)


def stok_listesi(request):
    """Stok görünümü: aynı galeri + stok miktarı + "sadece stokta olanlar" filtresi."""
    filtre = ListeFiltresi(request, reverse('katalog:stok_listesi'))
    context = _liste_context(request, filtre, stok_goster=True)
    context.update({
        'sayfa_basligi': 'Stok Durumu',
        'aktif_sekme': 'stok',
        'detay_url_adi': 'katalog:stok_urun_detay',
    })
    return _liste_yanit(request, context)


# --------------------------------------------------------------------------------------
# Detay paneli
# --------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------
# Hareket geçmişi
# --------------------------------------------------------------------------------------

HAREKET_SAYFA_BOYUTU = 50


def _tarih_cozumle(metin):
    """<input type="date">'ten gelen YYYY-AA-GG metnini date'e çevirir; geçersizse None."""
    try:
        return date.fromisoformat(metin.strip())
    except (AttributeError, ValueError):
        return None


def hareket_gecmisi(request):
    """stok_hareketleri dökümü: kim, ne zaman, hangi üründe, nereden nereye.

    Salt-okunur — yazmanın tek yolu stok_hareketi_kaydet() (bkz. stok_servisi).

    Tarihler `yerel_tarih()` ile aware hâle getiriliyor; hem gösterim hem de tarih
    aralığı filtresi bunun üzerinden çalışıyor. Ham naive UTC kolonuna göre filtrelemek
    gün sınırlarında 3 saatlik kaymaya yol açardı (bkz. models.py::StokHareketi).
    """
    arama = request.GET.get('q', '').strip()
    tip = request.GET.get('tip', '').strip()
    lokasyon = _tam_sayi(request.GET.get('lokasyon', ''))
    kullanici = request.GET.get('kullanici', '').strip()
    baslangic = _tarih_cozumle(request.GET.get('baslangic', ''))
    bitis = _tarih_cozumle(request.GET.get('bitis', ''))

    hareketler = (
        StokHareketi.objects.using('metaks')
        .annotate(tarih=yerel_tarih())
        .select_related('kaynak_lokasyon', 'hedef_lokasyon')
    )

    if arama:
        hareketler = hareketler.filter(
            Q(stok_kodu__icontains=arama) | Q(aciklama__icontains=arama)
        )
    if tip in stok_servisi.ISLEM_TIPI_DEGERLERI:
        hareketler = hareketler.filter(islem_tipi=tip)
    if lokasyon:
        hareketler = hareketler.filter(
            Q(kaynak_lokasyon_id=lokasyon) | Q(hedef_lokasyon_id=lokasyon)
        )
    if kullanici:
        hareketler = hareketler.filter(yapan_kullanici=kullanici)
    if baslangic:
        hareketler = hareketler.filter(tarih__date__gte=baslangic)
    if bitis:
        hareketler = hareketler.filter(tarih__date__lte=bitis)

    sayfalayici = Paginator(hareketler, HAREKET_SAYFA_BOYUTU)
    sayfa = sayfalayici.get_page(request.GET.get('sayfa'))

    # Ürün görselleri tek ek sorguda (N+1 yok). Hareket, katalogda olmayan (PASİF) bir
    # ürüne de ait olabilir — o zaman görsel yok, şablon yer tutucu basıyor.
    kodlar = {hareket.stok_kodu for hareket in sayfa.object_list}
    urunler = {
        urun.stok_kodu: urun
        for urun in AktifUrun.objects.using('metaks').filter(stok_kodu__in=kodlar)
    }
    for hareket in sayfa.object_list:
        hareket.urun = urunler.get(hareket.stok_kodu)
        # Ham değer ('SAYIM_DEVRI') yerine okunur etiket. Şablonda sözlük araması
        # yapılamadığı için (değişken anahtar desteklenmiyor) burada iliştiriliyor.
        hareket.islem_etiketi = stok_servisi.ISLEM_TIPI_ETIKETLERI.get(
            hareket.islem_tipi, hareket.islem_tipi
        )

    parametreler = QueryDict(mutable=True)
    for anahtar, deger in [
        ('q', arama), ('tip', tip), ('lokasyon', lokasyon or ''),
        ('kullanici', kullanici),
        ('baslangic', baslangic.isoformat() if baslangic else ''),
        ('bitis', bitis.isoformat() if bitis else ''),
    ]:
        if deger:
            parametreler[anahtar] = deger

    context = {
        'sayfa': sayfa,
        'toplam': sayfalayici.count,
        'aktif_sekme': 'hareketler',
        'islem_tipleri': stok_servisi.ISLEM_TIPLERI,
        # yaprak_mi: numune dolapları (kendisi hiç hareket taşımaz, yalnızca rafları
        # taşır) filtrede seçilebilir görünüp hep "0 hareket" dönmesin. tam_ad
        # hiyerarşiyi gösteriyor ("Numune Dolabı 1 · Raf 3") — düz lokasyon_adi
        # birden çok dolaptaki aynı isimli rafları ayırt edemezdi.
        'lokasyonlar': list(
            LokasyonDetay.objects.using('metaks').filter(yaprak_mi=True)
        ),
        'kullanicilar': sorted(
            StokHareketi.objects.using('metaks')
            .order_by()
            .values_list('yapan_kullanici', flat=True)
            .distinct()
        ),
        'secili': {
            'q': arama, 'tip': tip, 'lokasyon': lokasyon, 'kullanici': kullanici,
            'baslangic': baslangic.isoformat() if baslangic else '',
            'bitis': bitis.isoformat() if bitis else '',
        },
        'filtre_var': bool(arama or tip or lokasyon or kullanici or baslangic or bitis),
        'sonraki_url': None,
    }
    if sayfa.has_next():
        sonraki = parametreler.copy()
        # str(): QueryDict değerleri metindir. urlencode() zaten str'e çevirdiği için
        # int vermek çalışıyordu, ama sözleşmeye uymuyordu.
        sonraki['sayfa'] = str(sayfa.next_page_number())
        context['sonraki_url'] = '?' + sonraki.urlencode()

    if request.headers.get('HX-Request'):
        if sayfa.number > 1:
            return render(request, 'katalog/_hareket_satirlari.html', context)
        return render(request, 'katalog/_hareket_govde.html', context)
    return render(request, 'katalog/hareketler.html', context)


def _sayi(deger, birim):
    """Decimal'i Türkçe biçimde, gereksiz sıfırları atarak yazar: 5.00 -> "5 mm".

    normalize() tek başına 100 -> 1E+2 üretir; format(..., 'f') bunu engelliyor.
    """
    if deger is None:
        return None
    metin = format(Decimal(deger).normalize(), 'f').replace('.', ',')
    return f'{metin} {birim}'.strip()


def _detay_alanlari(urun):
    """Detay panelinde gösterilecek (etiket, değer) çiftleri — boş olanlar atlanır.

    v_aktif_urunler'ın alanlarının çoğu bugün ya tamamen boş ya tek değerli
    (2026-07-30, 1.780 aktif ürün üzerinde: boya_mine 0, montaj_durumu 0,
    hammadde_adi 0, kaplama_adi 0 dolu satır; kritik_stok_esigi her satırda 0).
    Hepsini sabit bir tabloda göstermek panelin tamamını "—" ile doldururdu; bunun
    yerine sadece gerçekten değeri olan alanlar listeleniyor. Boş alanlar veri
    girildikçe kendiliğinden görünür hâle gelir, burada değişiklik gerekmez.

    kritik_stok_esigi bilinçli olarak listede yok: ürünü tanımlayan bir özellik değil,
    stok uyarı eşiği — ve şu an her üründe 0.

    Kaplama / boya-mine / montaj durumu 2026-07-31'de bu listeden ÇIKARILDI:
    artık ürünün değil o parti stoğun özellikleri (veritabani migration 007) ve
    ürün formu onları yazmıyor. Kaplama bilgisini görmek isteyen yer stok detay
    paneli — orada kova kırılımı olarak gösteriliyor. Kolonlar `urunler`de hâlâ
    duruyor ama hepsi NULL, yani buradan kaldırmak görünür hiçbir şeyi eksiltmiyor.
    """
    adaylar = [
        ('Kategori', urun.kategori_adi),
        ('Ölçü', _sayi(urun.olcu_mm, 'mm')),
        ('Boy', _sayi(urun.boy_ligne, 'ligne')),
        ('Gramaj', _sayi(urun.gramaj_gr, 'gr')),
        ('Hammadde', urun.hammadde_adi),
        ('Varyant', urun.varyant_adi),
        ('Açıklama', urun.aciklama),
    ]
    return [
        {'etiket': etiket, 'deger': deger}
        for etiket, deger in adaylar
        if deger not in (None, '')
    ]


# urun_tipi 1.780 ürünün 1.776'sında ANA_URUN — her kartta göstermek gürültü olurdu,
# sadece ayırt edici olduğu iki durumda etiket basılıyor (bkz. _urun_detay.html).
URUN_TIPI_ETIKETLERI = {
    'VARYANT': 'Varyant',
    'ALT_PARCA': 'Alt parça',
}


def _urun_detay(request, stok_kodu, *, stok_goster):
    urun = get_object_or_404(AktifUrun.objects.using('metaks'), pk=stok_kodu)

    # parent_stok_kodu, v_aktif_urunler'da olmayan bir ürünü de gösterebilir: ana ürün
    # PASİF olabilir (geçerli ana görseli yoksa katalog dışında kalıyor). 2026-07-30
    # itibarıyla parent'ı olan 4 satırın ana ürünlerinin ikisi de (2108, 1805012) PASİF.
    # Bu yüzden panelde ana ürüne geçiş bağlantısı ancak ürün gerçekten katalogdaysa
    # basılıyor — yoksa buton 404 alıp sessizce hiçbir şey yapmıyordu.
    ana_urun_katalogda = bool(
        urun.parent_stok_kodu
        and AktifUrun.objects.using('metaks').filter(pk=urun.parent_stok_kodu).exists()
    )

    context = {
        'urun': urun,
        'alanlar': _detay_alanlari(urun),
        'tip_etiketi': URUN_TIPI_ETIKETLERI.get(urun.urun_tipi),
        'ana_urun_katalogda': ana_urun_katalogda,
        'stok_goster': stok_goster,
        'detay_url_adi': 'katalog:stok_urun_detay' if stok_goster else 'katalog:urun_detay',
    }

    if stok_goster:
        context['lokasyonlar'] = _lokasyon_stok(stok_kodu)
        context['toplam_stok'] = next(
            iter(
                ToplamStok.objects.using('metaks')
                .filter(pk=stok_kodu)
                .values_list('toplam_miktar', flat=True)
            ),
            None,
        )

    return render(request, 'katalog/_urun_detay.html', context)


def urun_detay(request, stok_kodu):
    """Katalog sayfasından açılan detay paneli — stok bilgisi içermez."""
    return _urun_detay(request, stok_kodu, stok_goster=False)


def stok_urun_detay(request, stok_kodu):
    """Stok sayfasından açılan detay paneli — lokasyon bazlı stok dökümü de gösterir."""
    return _urun_detay(request, stok_kodu, stok_goster=True)


# --------------------------------------------------------------------------------------
# Stok işlemi (ilk yazma modülü)
# --------------------------------------------------------------------------------------


def _tam_sayi(deger):
    """Formdan gelen metni int'e çevirir; boş/geçersizse None."""
    try:
        return int(str(deger).strip())
    except (TypeError, ValueError):
        return None


def _lokasyon_stok(stok_kodu):
    """Ürünün lokasyon bazlı stoğu; pasif lokasyonlar işaretlenmiş olarak.

    v_lokasyon_stok_ozet, artık kullanılmayan lokasyonlardaki geçmiş hareketleri de
    gösteriyor (2026-07-30'da Ana Depo / Sevkiyat Alanı / Fason Atölye 1 pasife alındı).
    Satırları gizlemek geçmişi saklamak olurdu; işaretlemeden bırakmak ise "neden bu
    lokasyonu seçemiyorum?" sorusunu doğuruyordu — bu yüzden gösterilip etiketleniyor.
    """
    aktif_idler = set(
        Lokasyon.objects.using('metaks')
        .filter(aktif_mi=True)
        .values_list('lokasyon_id', flat=True)
    )
    satirlar = list(LokasyonStok.objects.using('metaks').filter(stok_kodu=stok_kodu))
    for satir in satirlar:
        satir.pasif = satir.lokasyon_id not in aktif_idler
    return satirlar


def _islem_urunu(stok_kodu):
    """Stok işlem ekranının ürün kaynağı: AKTİF **ve** PASİF ürünlerin ikisi de.

    Eskiden bu ekran ürünü doğrudan `AktifUrun`'dan (`v_aktif_urunler`) alıyordu ve o
    view yalnızca `katalog_durumu='AKTIF'` satırları gösteriyor — yani kataloğun
    %40'ına (2026-07-31: 2.973 ürünün 1.193'ü PASİF) arayüzden hiç stok işlemi
    yapılamıyordu. Bu bir iş kuralı değildi, kaynak seçiminin yan etkisiydi:
    `AktifUrun` görsel ve kategori adını hazır verdiği için seçilmişti.
    Veritabanı tarafında böyle bir kısıt YOK — `stok_hareketi_kaydet()` PASİF bir
    ürünü sorunsuz kabul ediyor (canlı şemada BEGIN/ROLLBACK içinde ölçüldü).
    Devam eden depo sayımında elinde ürünle duran personelin kodu girememesi
    gerçek bir eksikti; 3b (hızlı giriş) bunu görünür kıldı.

    Dönen nesne her iki durumda da şablonun beklediği üç alanı taşıyor:
    `stok_kodu`, `kategori_adi`, `gorsel_url` (+ `pasif` bayrağı).
    """
    urun = AktifUrun.objects.using('metaks').filter(pk=stok_kodu).first()
    if urun is not None:
        urun.pasif = False
        return urun

    urun = get_object_or_404(Urun.objects.using('metaks'), pk=stok_kodu)
    urun.pasif = True
    # PASİF ürünün görseli YOK — bu bir varsayım değil, tanımın kendisi:
    # katalog_durumu AKTİF olmanın koşulu zaten doğrulanmış bir ana görseli olması
    # (migration 001). Ölçüldü de: 1.193 PASİF ürünün 0'ında herhangi bir
    # urun_gorselleri satırı var. Şablon bu None'da yer tutucuya düşüyor.
    urun.gorsel_url = None
    urun.kategori_adi = (
        Kategori.objects.using('metaks')
        .filter(pk=urun.kategori_id)
        .values_list('kategori_adi', flat=True)
        .first()
        if urun.kategori_id
        else None
    )
    return urun


def _islem_baglami(request, urun, *, varsayilan_tip, hizli=False):
    """Stok işlem formunun bağlamını üretir ve POST geldiyse hareketi kaydeder.

    `stok_islem` (tam sayfa) ile `hizli_islem` (tek sayfa depo ekranı) **aynı** formu
    kullanıyor; form da iş kuralları da tek yerde kalsın diye ortak. İş kuralları yine
    burada DEĞİL — `stok_hareketi_kaydet()` içinde; bu fonksiyon yalnızca tip dönüşümü
    yapıp dönen Türkçe mesajı taşıyor (bkz. stok_servisi).

    `varsayilan_tip` iki ekranda farklı, çünkü kullanım senaryoları farklı: ürün detay
    panelinden gelen yol sayım içindir (devam eden depo sayımı), hızlı ekran ise mal
    kabul/sevkiyat içindir — orada GİRİŞ daha sık.
    """
    sonuc = None
    hata = None
    girilen = {
        'islem_tipi': request.POST.get('islem_tipi', varsayilan_tip),
        'miktar': request.POST.get('miktar', ''),
        'kaynak_lokasyon_id': request.POST.get('kaynak_lokasyon_id', ''),
        'hedef_lokasyon_id': request.POST.get('hedef_lokasyon_id', ''),
        'aciklama': request.POST.get('aciklama', ''),
        # Kova alanları (migration 007). Boş string = "belirtilmemiş" kovası;
        # _tam_sayi/montaj_cozumle onu None'a çeviriyor.
        'kaplama_id': request.POST.get('kaplama_id', ''),
        'kaplama_cesidi': request.POST.get('kaplama_cesidi', ''),
        'montaj': request.POST.get('montaj', ''),
        'boya': request.POST.get('boya', ''),
        'mine': request.POST.get('mine', ''),
    }
    islem_kimligi = request.POST.get('istemci_kimligi') or stok_servisi.yeni_islem_kimligi()

    if request.method == 'POST':
        if girilen['islem_tipi'] not in stok_servisi.ISLEM_TIPI_DEGERLERI:
            hata = 'Geçersiz işlem tipi.'
        elif _tam_sayi(girilen['miktar']) is None:
            hata = 'Miktar bir tam sayı olmalıdır.'
        else:
            try:
                sonuc = stok_servisi.hareket_kaydet(
                    istemci_kimligi=islem_kimligi,
                    stok_kodu=urun.stok_kodu,
                    islem_tipi=girilen['islem_tipi'],
                    miktar=_tam_sayi(girilen['miktar']),
                    kaynak_lokasyon_id=_tam_sayi(girilen['kaynak_lokasyon_id']),
                    hedef_lokasyon_id=_tam_sayi(girilen['hedef_lokasyon_id']),
                    aciklama=girilen['aciklama'].strip(),
                    yapan_kullanici=request.user.email or request.user.get_username(),
                    kaplama_id=_tam_sayi(girilen['kaplama_id']),
                    kaplama_cesidi=girilen['kaplama_cesidi'],
                    montaj=stok_servisi.montaj_cozumle(girilen['montaj']),
                    boya=girilen['boya'].strip(),
                    mine=girilen['mine'].strip(),
                )
            except stok_servisi.StokIslemHatasi as istisna:
                hata = str(istisna)

        if sonuc and not sonuc['atlandi']:
            # Kayıt gerçekleşti: formu temizle ve YENİ bir işlem kimliği ver, yoksa
            # sonraki gönderim "zaten kaydedilmiş" diye atlanırdı.
            girilen = {
                'islem_tipi': girilen['islem_tipi'],
                'miktar': '',
                'kaynak_lokasyon_id': '',
                'hedef_lokasyon_id': '',
                'aciklama': '',
                # Kova seçimi KORUNUYOR (miktar/lokasyonun aksine): aynı partiden
                # arka arkaya işlem yapmak normal, kaplamayı her seferinde yeniden
                # seçtirmek gereksiz sürtünme olurdu. /stok/ekle/ ile aynı duruş.
                'kaplama_id': girilen['kaplama_id'],
                'kaplama_cesidi': girilen['kaplama_cesidi'],
                'montaj': girilen['montaj'],
                'boya': girilen['boya'],
                'mine': girilen['mine'],
            }
            islem_kimligi = stok_servisi.yeni_islem_kimligi()

    return {
        'urun': urun,
        'islem_tipleri': stok_servisi.ISLEM_TIPLERI,
        # aktif_mi + yaprak_mi: dolaplar burada seçilebilir görünürse
        # stok_hareketi_kaydet() onları reddeder (migration 004, "sadece yaprak
        # lokasyona yazılabilir") — kullanıcı formu doldurup gönderdikten SONRA
        # hatayı görürdü, bunun yerine seçilemez olsunlar.
        'lokasyonlar': list(
            LokasyonDetay.objects.using('metaks').filter(aktif_mi=True, yaprak_mi=True)
        ),
        # Kova seçimi (migration 007). Renkler `kaplamalar` tablosundan okunuyor,
        # sabit liste değil — yeni renk eklemek migration değil tek INSERT.
        'kaplamalar': stok_servisi.kaplama_secenekleri(),
        'kaplama_cesitleri': stok_servisi.KAPLAMA_CESITLERI,
        'montaj_secenekleri': stok_servisi.MONTAJ_SECENEKLERI,
        'mevcut_stok': _lokasyon_stok(urun.stok_kodu),
        'girilen': girilen,
        'istemci_kimligi': islem_kimligi,
        'sonuc': sonuc,
        'hata': hata,
        # Formun nereye gönderileceğini ve HTMX ile mi çalışacağını şablona söyler.
        'hizli': hizli,
        'aktif_sekme': 'stok',
    }


@login_required
def stok_islem(request, stok_kodu):
    """Bir ürün için stok hareketi kaydı (GİRİŞ/ÇIKIŞ/TRANSFER/SAYIM/DÜZELTME).

    İş kuralları bilinçli olarak burada tekrarlanmıyor: bu view yalnızca tip dönüşümü
    yapıp stok_hareketi_kaydet()'i çağırıyor, zorunluluk/yeterlilik denetimleri ve
    kullanıcıya gösterilen Türkçe mesajlar veritabanı fonksiyonundan geliyor
    (bkz. stok_servisi). Kuralların iki kopyası olsaydı zamanla ayrışırlardı.

    Giriş zorunlu çünkü stok_hareketleri.yapan_kullanici NOT NULL ve Postgres'e tek bir
    paylaşılan `depo_admin` kullanıcısıyla bağlanıldığı için current_user'a güvenilemez —
    "kim yaptı" bilgisi uygulamadan açıkça geçirilmek zorunda.
    """
    urun = _islem_urunu(stok_kodu)
    # Bu yol ürün detay panelinden geliyor ve bugünkü asıl kullanımı devam eden depo
    # sayımı — varsayılan SAYIM. Hızlı ekranın varsayılanı GİRİŞ (bkz. hizli_islem).
    baglam = _islem_baglami(request, urun, varsayilan_tip='SAYIM_DEVRI')
    return render(request, 'katalog/stok_islem.html', baglam)


@login_required
def stok_ekle(request):
    """Depoya yeni stok girişi — her zaman bir GİRİŞ hareketi (`/stok/ekle/`).

    Stok sayfasının "+ Stok ekle" bağlantısının hedefi; kataloğun "+ Ürün ekle"
    bağlantısının stok tarafındaki karşılığı. İkisinin ayrı olması bu projenin
    "her sayfa kendi işini anlatır" kuralının devamı: katalog ÜRÜN kaydının yeri,
    stok STOĞUN.

    `stok_islem`/`hizli_islem`'den farkı işlem tipi sormaması — burada tek bir
    senaryo var (mal kabul). Yazma yolu yine aynı tek kapı: `hareket_kaydet()`.

    Ürünün varlığı POST'tan ÖNCE kontrol ediliyor. `stok_hareketleri.stok_kodu`'nun
    FK'sı zaten reddederdi ama mesajı psycopg2'nin İngilizce kısıt hatası olurdu;
    bunun yerine Türkçe bir mesaj ve "bu kodla ürün oluştur" bağlantısı veriliyor —
    hızlı ekranın "bulunamadı" dalıyla aynı davranış.
    """
    form = forms.StokEkleFormu(request.POST or None)
    sonuc = None
    hata = None
    bilinmeyen_kod = None
    islem_kimligi = request.POST.get('istemci_kimligi') or stok_servisi.yeni_islem_kimligi()

    if request.method == 'POST' and form.is_valid():
        stok_kodu = form.cleaned_data['stok_kodu'].strip()
        varsa = (
            Urun.objects.using('metaks').filter(pk=stok_kodu).values_list('stok_kodu', flat=True).first()
            or Urun.objects.using('metaks').filter(stok_kodu__iexact=stok_kodu)
            .values_list('stok_kodu', flat=True).first()
        )
        if varsa is None:
            bilinmeyen_kod = stok_kodu
            hata = f'"{stok_kodu}" kodlu bir ürün bulunamadı.'
        else:
            try:
                sonuc = stok_servisi.hareket_kaydet(
                    istemci_kimligi=islem_kimligi,
                    stok_kodu=varsa,
                    islem_tipi='GIRIS',
                    miktar=form.cleaned_data['miktar'],
                    kaynak_lokasyon_id=None,
                    hedef_lokasyon_id=form.cleaned_data['hedef_lokasyon_id'],
                    aciklama=form.cleaned_data.get('aciklama', ''),
                    yapan_kullanici=request.user.email or request.user.get_username(),
                    kaplama_id=form.cleaned_data.get('kaplama_id'),
                    kaplama_cesidi=form.cleaned_data.get('kaplama_cesidi'),
                    montaj=stok_servisi.montaj_cozumle(form.cleaned_data.get('montaj')),
                    boya=form.cleaned_data.get('boya'),
                    mine=form.cleaned_data.get('mine'),
                )
            except stok_servisi.StokIslemHatasi as istisna:
                hata = str(istisna)

        if sonuc and not sonuc['atlandi']:
            # Başarılı kayıttan sonra form SIFIRDAN kurulmuyor: lokasyon ve kova
            # alanları KORUNUYOR, yalnızca stok kodu ve miktar temizleniyor. Mal
            # kabulde aynı partiden onlarca ürün arka arkaya giriliyor; kaplamayı
            # her seferinde yeniden seçtirmek gereksiz sürtünme olurdu.
            # Yeni istemci kimliği şart, yoksa sonraki gönderim "zaten kaydedilmiş"
            # diye atlanırdı (uq_stok_hareketleri_istemci_kimligi).
            form = forms.StokEkleFormu(initial={
                'hedef_lokasyon_id': form.cleaned_data['hedef_lokasyon_id'],
                'kaplama_id': form.cleaned_data.get('kaplama_id'),
                'kaplama_cesidi': form.cleaned_data.get('kaplama_cesidi'),
                'montaj': form.cleaned_data.get('montaj'),
                'boya': form.cleaned_data.get('boya'),
                'mine': form.cleaned_data.get('mine'),
            })
            islem_kimligi = stok_servisi.yeni_islem_kimligi()

    return render(request, 'katalog/stok_ekle.html', {
        'form': form,
        'sonuc': sonuc,
        'hata': hata,
        'bilinmeyen_kod': bilinmeyen_kod,
        'istemci_kimligi': islem_kimligi,
        'aktif_sekme': 'stok',
    })


# --------------------------------------------------------------------------------------
# Hızlı stok işlemi girişi (/stok/hizli/)
#
# Günde onlarca kez aynı işlemi yapan depo personeli için kısayol. Bugünkü yol (stok
# sayfası -> kart ızgarasından ürünü gözle bul -> detay panelinden "Stok işlemi yap")
# KALIYOR — ürünü görselinden tanımak için doğru yol o. Burası yalnızca kodu bilen/
# okutan kişinin ızgarayı atlaması için.
#
# Yeni bir işlem formu YAZILMIYOR: burası yalnızca doğru stok_islem sayfasına
# yönlendiriyor. O form zaten uçtan uca doğrulanmış, ikinci bir kopyası zamanla ondan
# ayrışırdı.
#
# Barkod okuyucular ek kod GEREKTİRMİYOR: USB/Bluetooth okuyucular klavye gibi davranır
# (kodu yazıp Enter'a basar), yani aşağıdaki düz <form> gönderimi onlarla çalışır.
# Bu yüzden ana yol bilinçli olarak JS'siz. Telefon kamerasıyla QR okuma ayrı bir iş ve
# bugün mümkün değil: getUserMedia "secure context" (HTTPS) istiyor, site düz HTTP
# (bkz. YAPILACAKLAR.md, "Sırası gelmemiş" -> HTTPS).
# --------------------------------------------------------------------------------------

# Öneri listesinde gösterilecek en fazla satır. Kutunun altına sığacak kadar; burası
# stok sayfasının kart ızgarasının yerini almaya çalışmıyor.
ONERI_SAYISI = 8


def _oneriler(kod, *, limit=ONERI_SAYISI):
    """Koda benzeyen ürünler — yazım hatası / yanlış okunan barkod için.

    `AktifUrun.arama_metni` yerine ham `urunler.stok_kodu` üzerinde arıyor, iki sebeple:
    (1) `arama_metni` yalnızca `v_aktif_urunler`'da var, yani 2.973 ürünün 1.780'ini
    kapsıyor — bu kutu artık PASİF ürünleri de bulmak zorunda; (2) buraya kod yazılıyor,
    açıklama değil. Kategori ve görsel ayrı birer toplu sorguyla ekleniyor (ürün başına
    sorgu değil).
    """
    if not kod:
        return []

    urunler = list(
        Urun.objects.using('metaks')
        .filter(stok_kodu__icontains=kod)
        .order_by('stok_kodu')[:limit]
    )
    if not urunler:
        return []

    kodlar = [u.stok_kodu for u in urunler]
    kategoriler = dict(
        Kategori.objects.using('metaks')
        .filter(pk__in={u.kategori_id for u in urunler if u.kategori_id})
        .values_list('kategori_id', 'kategori_adi')
    )
    # Görsel yalnızca AKTİF ürünlerde var (PASİF'lerin 0'ında görsel kaydı bulunuyor),
    # yani bu sorgu doğal olarak sadece bir kısmını dolduruyor.
    gorseller = dict(
        AktifUrun.objects.using('metaks')
        .filter(pk__in=kodlar)
        .values_list('stok_kodu', 'ana_gorsel_dosya_adi')
    )

    for urun in urunler:
        urun.kategori_adi = kategoriler.get(urun.kategori_id)
        dosya = gorseller.get(urun.stok_kodu)
        urun.gorsel_url = settings.GORSEL_SUNUCU_BASE_URL + dosya if dosya else None
        urun.pasif = urun.katalog_durumu != 'AKTIF'
    return urunler


def _kodu_coz(kod):
    """Yazılan/okutulan kodu **gösterime hazır** bir ürüne çevirir; bulunamazsa None.

    Eşleştirme önce harf duyarlı, sonra `iexact`: `urunler`de yalnızca büyük/küçük
    harfte ayrışan iki kod YOK (ölçüldü), yani `iexact` belirsizlik üretmiyor. 2.973
    kodun 306'sı harf içerdiği için (`1805012-YENI`) duyarlılık gerçek bir sorun —
    okuyucudan ya da klavyeden farklı büyüklükte gelebilir.

    Bulunan satır ham bırakılmıyor, `_islem_urunu()`'ne veriliyor: `gorsel_url`,
    `kategori_adi` ve `pasif` oradan geliyor ve şablon üçünü de bekliyor. Ham `Urun`
    döndürüldüğü ilk sürümde AKTİF ürünlerin görseli hiç basılmıyor, PASİF ürünlerin
    de "katalogda pasif" açıklaması çıkmıyordu — süsleme tek yerde kalsın.
    """
    if not kod:
        return None
    eslesen = (
        Urun.objects.using('metaks').filter(stok_kodu=kod).first()
        or Urun.objects.using('metaks').filter(stok_kodu__iexact=kod).first()
    )
    return _islem_urunu(eslesen.stok_kodu) if eslesen is not None else None


@login_required
def hizli_islem(request):
    """Tek sayfalık depo ekranı: kodu okut, işlemi aynı ekranda kaydet, sıradakine geç.

    İlk sürümü (2026-07-31) yalnızca bir yönlendiriciydi — kod alıp `stok_islem`
    sayfasına atıyordu. Kullanıcı geri bildirimi üzerine tek sayfaya çevrildi: mal
    kabul/sevkiyat günde onlarca kez tekrarlanan bir iş, her seferinde sayfa
    değiştirmek gereksiz sürtünme. Kaydedince kutu temizlenip yeniden odaklanıyor,
    yani okut-kaydet-okut döngüsü hiç kesilmiyor.

    Form KOPYALANMADI: `stok_islem` ile aynı `_stok_islem_govde.html` parçasını ve aynı
    `_islem_baglami()` mantığını kullanıyor. İki kopya olsaydı zamanla ayrışırlardı —
    `stok_servisi`'nin `stok_hareketi_kaydet()` karşısındaki duruşunun aynısı.

    Giriş zorunlu: yazma ekranı ve `stok_hareketleri.yapan_kullanici` NOT NULL.
    """
    if request.method == 'POST':
        urun = _kodu_coz(request.POST.get('stok_kodu', '').strip())
        if urun is None:
            # Yalnızca kurcalanmış bir POST'ta olur; sessizce boş alana dönmek yerine
            # kullanıcıya kodu yeniden okutturuyoruz.
            return render(request, 'katalog/_hizli_alan.html', {'kod': '', 'bulunamadi': False})
        baglam = _islem_baglami(request, urun, varsayilan_tip='GIRIS', hizli=True)
        baglam['kod'] = urun.stok_kodu
        baglam['oob'] = True  # kayıt/hata sonrası da eski öneriler ekranda kalmasın
        return render(request, 'katalog/_hizli_alan.html', baglam)

    kod = request.GET.get('kod', '').strip()
    htmx = bool(request.headers.get('HX-Request'))

    # ?ara=1 kullanıcı YAZARKEN geliyor: yalnızca öneri listesi, AYRI bir hedefe
    # (#oneriler). Enter/gönderim ise onsuz gelir ve #islem-alani'nı tazeler.
    # İki tetikleyicinin ayrı hedefleri olması şart — aynı hedefi paylaştıkları ilk
    # sürümde yarışıyorlardı (gerçek tarayıcıda ölçüldü: Enter formu getiriyor, son
    # karakterin bekleyen 200 ms'lik isteği hemen ardından düşüp formu eziyordu).
    # Ayrıca her tuş vuruşunda "bulunamadı" basmak gürültü olurdu; o uyarı ancak
    # kullanıcı gerçekten gönderdiğinde bir şey anlatıyor.
    if request.GET.get('ara') == '1':
        return render(request, 'katalog/_hizli_oneriler.html', {'oneriler': _oneriler(kod)})

    urun = _kodu_coz(kod)
    baglam = {
        'kod': kod,
        'bulunamadi': bool(kod) and urun is None,
        'oneriler': _oneriler(kod),
        # Ürün geldiyse kutunun altındaki eski öneriler out-of-band temizlenir;
        # tam sayfa basımında gerekmez (zaten sıfırdan basılıyor) ve orada
        # mükerrer id üretirdi.
        'oob': htmx and urun is not None,
    }
    if urun is not None:
        # Varsayılan GİRİŞ: bu ekranın senaryosu mal kabul/sevkiyat (ürün detayından
        # gelen yolun senaryosu ise sayım — bkz. stok_islem).
        baglam = {**_islem_baglami(request, urun, varsayilan_tip='GIRIS', hizli=True), **baglam}

    # HTMX yalnızca değişen alanı istiyor; HTMX yoksa (ya da sayfa doğrudan
    # açıldıysa) aynı parçayı içeren tam sayfa basılıyor. Böylece düz <form>
    # gönderimi de çalışmaya devam ediyor — barkod okuyucunun Enter'ı için önemli.
    return render(request, 'katalog/_hizli_alan.html' if htmx else 'katalog/hizli_islem.html', baglam)
