from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Subquery
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from . import stok_servisi
from .models import (
    AktifUrun,
    Lokasyon,
    LokasyonStok,
    StokHareketi,
    ToplamStok,
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


def ana_ekran(request):
    """Giriş noktası: modüllere yönlendirme + sistemin özet sayıları + giriş kutusu.

    Sayılar bilinçli olarak grafiksiz: hepsi tek anlık değer, yani doğru biçim stat
    tile / meter — tek çubuklu grafik değil. Uydurma metrik yok, hepsi doğrudan
    v_aktif_urunler / v_toplam_stok / lokasyonlar'dan sayılıyor.
    """
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
            'aktif_lokasyon': Lokasyon.objects.using('metaks').filter(aktif_mi=True).count(),
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
        çevrilmiş birleşimi (bkz. metaks_DB/docs/aktif-urun-veri-sozlesmesi.md) — tek bir
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
        'lokasyonlar': list(Lokasyon.objects.using('metaks').all()),
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
        sonraki['sayfa'] = sayfa.next_page_number()
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
    """
    adaylar = [
        ('Kategori', urun.kategori_adi),
        ('Ölçü', _sayi(urun.olcu_mm, 'mm')),
        ('Boy', _sayi(urun.boy_ligne, 'ligne')),
        ('Gramaj', _sayi(urun.gramaj_gr, 'gr')),
        ('Hammadde', urun.hammadde_adi),
        ('Kaplama', urun.kaplama_adi),
        ('Boya / mine', urun.boya_mine),
        ('Montaj durumu', urun.montaj_durumu),
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
    urun = get_object_or_404(AktifUrun.objects.using('metaks'), pk=stok_kodu)
    sonuc = None
    hata = None
    # Gönderilen değerler: hata durumunda formu boşaltmamak için geri basılıyor.
    girilen = {
        'islem_tipi': request.POST.get('islem_tipi', 'SAYIM_DEVRI'),
        'miktar': request.POST.get('miktar', ''),
        'kaynak_lokasyon_id': request.POST.get('kaynak_lokasyon_id', ''),
        'hedef_lokasyon_id': request.POST.get('hedef_lokasyon_id', ''),
        'aciklama': request.POST.get('aciklama', ''),
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
            }
            islem_kimligi = stok_servisi.yeni_islem_kimligi()

    return render(
        request,
        'katalog/stok_islem.html',
        {
            'urun': urun,
            'islem_tipleri': stok_servisi.ISLEM_TIPLERI,
            'lokasyonlar': list(Lokasyon.objects.using('metaks').filter(aktif_mi=True)),
            'mevcut_stok': _lokasyon_stok(stok_kodu),
            'girilen': girilen,
            'istemci_kimligi': islem_kimligi,
            'sonuc': sonuc,
            'hata': hata,
            'aktif_sekme': 'stok',
        },
    )
