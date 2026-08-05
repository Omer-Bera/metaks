from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import forms, stok_servisi
from .models import (
    AktifUrun,
    FasonIsEmriOzet,
    Hammadde,
    IsOrtagi,
    IsOrtagiRolu,
    Kaplama,
    Kategori,
    LokasyonDetay,
    StokBakiye,
    StokHareketi,
    StokIslemi,
    StokKalemi,
    Renk,
    StokUrunOzet,
    Urun,
    yerel_tarih,
)
from .yetkiler import izin_gerekli, izni_var_mi

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
    v_aktif_urunler / v_stok_urun_ozet / lokasyonlardan sayılıyor.
    """
    if not request.user.is_authenticated and not request.session.get(MISAFIR_ANAHTARI):
        return redirect('katalog:giris')

    urunler = AktifUrun.objects.using('metaks')
    aktif_urun = urunler.count()

    stok_gorebilir = izni_var_mi(request.user, 'goruntule')
    hareket_gorebilir = izni_var_mi(request.user, 'hareket')
    hareketli_urun = stogu_olan = aktif_lokasyon = 0
    son_hareketler = []

    # Misafir ve yetkisiz kullanıcı için stok tablolarına hiç sorgu atılmaz. Bu,
    # yalnız şablonda rakam gizlemekten farklıdır: HTML/HTMX yanında sorgu tarafında
    # da yetki sınırı aynı yerde uygulanır.
    if stok_gorebilir:
        hareketli_urun = StokUrunOzet.objects.using('metaks').count()
        stogu_olan = StokUrunOzet.objects.using('metaks').filter(
            sahip_olunan_toplam__gt=0
        ).count()
        aktif_lokasyon = (
            LokasyonDetay.objects.using('metaks')
            .filter(aktif_mi=True, yaprak_mi=True)
            .count()
        )

    if hareket_gorebilir:
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
            'aktif_lokasyon': aktif_lokasyon,
            'hareketli_urun': hareketli_urun,
            'stogu_olan': stogu_olan,
            'sayim_yuzdesi': round(100 * hareketli_urun / aktif_urun, 1) if aktif_urun else 0,
            'son_hareketler': son_hareketler,
            'stok_gorebilir': stok_gorebilir,
            'hareket_gorebilir': hareket_gorebilir,
            'stok_yazabilir': izni_var_mi(request.user, 'islem'),
        },
    )


# --------------------------------------------------------------------------------------
# Ortak filtre altyapısı — hem katalog hem stok sayfası aynı arama/kategori/sıralama
# davranışını kullanıyor. İki sayfa arasındaki tek fark stok bilgisinin gösterilmesi
# ve "sadece stokta olanlar" filtresi (bkz. stok_listesi).
# --------------------------------------------------------------------------------------


def _tam_sayi(deger):
    """Sorgu dizgesinden gelen metni int'e çevirir; boş/geçersizse None."""
    try:
        return int(str(deger).strip())
    except (TypeError, ValueError):
        return None


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
        self.yer = request.GET.get('yer', '').strip()
        self.lokasyon = _tam_sayi(request.GET.get('lokasyon', ''))
        self.kaplama = _tam_sayi(request.GET.get('kaplama', ''))
        self.montaj = request.GET.get('montaj', '').strip()
        self.durum = request.GET.get('durum', '').strip()
        self.boya = _tam_sayi(request.GET.get('boya', ''))
        self.mine = _tam_sayi(request.GET.get('mine', ''))
        self.stok_turu = request.GET.get('stok_turu', '').strip()
        self.seviye = request.GET.get('seviye', '').strip()
        self.fasoncu = _tam_sayi(request.GET.get('fasoncu', ''))
        self.fason_durum = request.GET.get('fason_durum', '').strip()
        self.parti = request.GET.get('parti', '').strip()
        self.olcu = request.GET.get('olcu', '').strip()
        if self.sirala not in SIRALAMALAR:
            self.sirala = VARSAYILAN_SIRALAMA

    @property
    def filtre_var(self):
        return bool(
            self.arama or self.kategoriler or self.sadece_stok or self.yer
            or self.lokasyon or self.kaplama or self.montaj or self.durum
            or self.boya or self.mine or self.stok_turu or self.seviye
            or self.fasoncu or self.fason_durum or self.parti or self.olcu
        )

    def url(
        self, *, kategoriler=None, arama=None, sadece_stok=None,
        yer=None, lokasyon=None, kaplama=None, montaj=None, durum=None,
        boya=None, mine=None, stok_turu=None, seviye=None, fasoncu=None,
        fason_durum=None, parti=None, olcu=None, **ekstra
    ):
        """Bu filtrenin URL'ini üretir; verilen alanlar geçersiz kılınır.

        Varsayılan değerler dışarıda bırakılıyor, böylece URL'ler temiz kalıyor
        ("/" == "/?sirala=kod_artan").
        """
        parametreler = QueryDict(mutable=True)
        arama = self.arama if arama is None else arama
        kategoriler = self.kategoriler if kategoriler is None else kategoriler
        sadece_stok = self.sadece_stok if sadece_stok is None else sadece_stok
        yer = self.yer if yer is None else yer
        lokasyon = self.lokasyon if lokasyon is None else lokasyon
        kaplama = self.kaplama if kaplama is None else kaplama
        montaj = self.montaj if montaj is None else montaj
        durum = self.durum if durum is None else durum
        boya = self.boya if boya is None else boya
        mine = self.mine if mine is None else mine
        stok_turu = self.stok_turu if stok_turu is None else stok_turu
        seviye = self.seviye if seviye is None else seviye
        fasoncu = self.fasoncu if fasoncu is None else fasoncu
        fason_durum = self.fason_durum if fason_durum is None else fason_durum
        parti = self.parti if parti is None else parti
        olcu = self.olcu if olcu is None else olcu

        if arama:
            parametreler['q'] = arama
        if kategoriler:
            parametreler.setlist('kategori', kategoriler)
        if sadece_stok:
            parametreler['stok'] = '1'
        for anahtar, deger in [
            ('yer', yer), ('lokasyon', lokasyon), ('kaplama', kaplama),
            ('montaj', montaj), ('durum', durum),
            ('boya', boya), ('mine', mine), ('stok_turu', stok_turu),
            ('seviye', seviye), ('fasoncu', fasoncu),
            ('fason_durum', fason_durum), ('parti', parti), ('olcu', olcu),
        ]:
            if deger:
                parametreler[anahtar] = str(deger)
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
            # Yeni özet içinde yalnız şirketin sahip olduğu pozitif bakiyesi bulunan
            # ürünler; FASON ve NUMUNE de mülkiyet toplamına dahildir.
            stoklu = (
                StokUrunOzet.objects.using('metaks')
                .filter(sahip_olunan_toplam__gt=0)
                .values('urun_kodu')
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
            StokUrunOzet.objects.using('metaks')
            .filter(sahip_olunan_toplam__gt=0)
            .values('urun_kodu')
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
    """Sayfadaki ürünlere satışa hazır stoğu iliştirir (tek ek sorgu, N+1 yok).

    Özet satırı yoksa ürün hiç hareket görmemiştir; satır var ve satışa hazır miktar
    sıfırsa ürün fasonda/numunede/bloke olabilir veya gerçekten boş olabilir.
    """
    kodlar = [urun.stok_kodu for urun in urunler]
    if not kodlar:
        return urunler
    ozetler = {
        o.urun_kodu: o
        for o in StokUrunOzet.objects.using('metaks').filter(urun_kodu__in=kodlar)
    }
    for urun in urunler:
        ozet = ozetler.get(urun.stok_kodu)
        miktar = ozet.satisa_hazir_toplam if ozet else None
        urun.toplam_stok = miktar
        urun.stok_ozeti = ozet
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


def _stok_kategori_secenekleri(filtre):
    dagilim = {
        satir['kategori_id']: satir['adet']
        for satir in Urun.objects.using('metaks').filter(stok_takip_edilsin_mi=True)
        .values('kategori_id').annotate(adet=Count('stok_kodu'))
    }
    kategoriler = list(Kategori.objects.using('metaks').filter(aktif_mi=True))
    sonuc = [
        {
            'deger': k.kategori_adi,
            'etiket': k.kategori_adi,
            'adet': dagilim.get(k.kategori_id, 0),
            'secili': k.kategori_adi in filtre.kategoriler,
            'url': filtre.kategori_degistir(k.kategori_adi),
        }
        for k in kategoriler if dagilim.get(k.kategori_id, 0)
    ]
    if dagilim.get(None):
        sonuc.append({
            'deger': KATEGORISIZ, 'etiket': 'Kategorisiz', 'adet': dagilim[None],
            'secili': KATEGORISIZ in filtre.kategoriler,
            'url': filtre.kategori_degistir(KATEGORISIZ),
        })
    return sonuc


def _stok_liste_context(request, filtre):
    """Aktif görsel şartı olmadan bütün stok takipli ürünleri SKU bakiyesiyle listeler."""
    urunler = Urun.objects.using('metaks').filter(stok_takip_edilsin_mi=True)
    if filtre.arama:
        sku_urunleri = StokKalemi.objects.using('metaks').filter(
            sku_kodu__icontains=filtre.arama
        ).values('urun_kodu')
        urunler = urunler.filter(
            Q(stok_kodu__icontains=filtre.arama)
            | Q(aciklama__icontains=filtre.arama)
            | Q(stok_kodu__in=Subquery(sku_urunleri))
        )
    if filtre.kategoriler:
        adlar = [k for k in filtre.kategoriler if k != KATEGORISIZ]
        kategori_idleri = Kategori.objects.using('metaks').filter(
            kategori_adi__in=adlar
        ).values('kategori_id')
        kosul = Q(kategori_id__in=Subquery(kategori_idleri))
        if KATEGORISIZ in filtre.kategoriler:
            kosul |= Q(kategori_id__isnull=True)
        urunler = urunler.filter(kosul)
    if filtre.olcu:
        try:
            urunler = urunler.filter(olcu_mm=Decimal(filtre.olcu.replace(',', '.')))
        except InvalidOperation:
            urunler = urunler.none()

    bakiyeler = StokBakiye.objects.using('metaks')
    bakiye_filtresi_var = bool(
        filtre.sadece_stok or filtre.yer or filtre.lokasyon
        or filtre.kaplama or filtre.montaj or filtre.durum or filtre.boya
        or filtre.mine or filtre.stok_turu or filtre.fasoncu or filtre.parti
    )
    if filtre.sadece_stok:
        bakiyeler = bakiyeler.filter(mevcut_miktar__gt=0)
    if filtre.yer in ('DAHILI', 'FASON', 'NUMUNE'):
        bakiyeler = bakiyeler.filter(lokasyon_tipi=filtre.yer)
    if filtre.lokasyon:
        bakiyeler = bakiyeler.filter(lokasyon_id=filtre.lokasyon)
    if filtre.kaplama:
        bakiyeler = bakiyeler.filter(kaplama_id=filtre.kaplama)
    if filtre.montaj in ('BELIRSIZ', 'HAM', 'YARI_MONTE', 'MONTE'):
        bakiyeler = bakiyeler.filter(montaj_durumu=filtre.montaj)
    if filtre.durum in ('SERBEST', 'KALITE_BEKLIYOR', 'BLOKE'):
        bakiyeler = bakiyeler.filter(stok_durumu_kodu=filtre.durum)
    if filtre.boya:
        bakiyeler = bakiyeler.filter(boya_renk_id=filtre.boya)
    if filtre.mine:
        bakiyeler = bakiyeler.filter(mine_renk_id=filtre.mine)
    if filtre.fasoncu:
        bakiyeler = bakiyeler.filter(is_ortagi_id=filtre.fasoncu)
    if filtre.parti:
        bakiyeler = bakiyeler.filter(parti_no__icontains=filtre.parti)
    if filtre.stok_turu == 'SATISA_HAZIR':
        bakiyeler = bakiyeler.filter(
            lokasyon_tipi='DAHILI', stok_durumu_kodu='SERBEST',
            satilabilir_mi=True, mevcut_miktar__gt=0,
        )
    elif filtre.stok_turu == 'FASONDA':
        bakiyeler = bakiyeler.filter(lokasyon_tipi='FASON', mevcut_miktar__gt=0)
    elif filtre.stok_turu == 'KALITE':
        bakiyeler = bakiyeler.filter(stok_durumu_kodu='KALITE_BEKLIYOR', mevcut_miktar__gt=0)
    elif filtre.stok_turu == 'BLOKE':
        bakiyeler = bakiyeler.filter(stok_durumu_kodu='BLOKE', mevcut_miktar__gt=0)
    if bakiye_filtresi_var:
        urunler = urunler.filter(stok_kodu__in=Subquery(bakiyeler.values('urun_kodu')))

    ozet_urunleri = StokUrunOzet.objects.using('metaks')
    if filtre.seviye == 'STOKLU':
        urunler = urunler.filter(
            stok_kodu__in=Subquery(ozet_urunleri.filter(sahip_olunan_toplam__gt=0).values('urun_kodu'))
        )
    elif filtre.seviye == 'SIFIR':
        urunler = urunler.filter(
            stok_kodu__in=Subquery(ozet_urunleri.filter(sahip_olunan_toplam=0).values('urun_kodu'))
        )
    elif filtre.seviye == 'SAYILMAMIS':
        urunler = urunler.exclude(stok_kodu__in=Subquery(ozet_urunleri.values('urun_kodu')))
    elif filtre.seviye == 'KRITIK':
        satisa_hazir_alt_sorgu = ozet_urunleri.filter(
            urun_kodu=OuterRef('stok_kodu')
        ).values('satisa_hazir_toplam')[:1]
        urunler = urunler.annotate(
            filtre_satisa_hazir=Subquery(satisa_hazir_alt_sorgu)
        ).filter(
            kritik_stok_esigi__gt=0,
            filtre_satisa_hazir__lte=F('kritik_stok_esigi'),
        )

    if filtre.fason_durum in ('ACIK', 'GECIKMIS'):
        emirler = FasonIsEmriOzet.objects.using('metaks').filter(durum='ACIK', acik_miktar__gt=0)
        if filtre.fason_durum == 'GECIKMIS':
            emirler = emirler.filter(beklenen_donus_tarihi__lt=date.today())
        ilgili_sku = StokKalemi.objects.using('metaks').filter(
            Q(stok_kalemi_id__in=Subquery(emirler.values('kaynak_stok_kalemi_id')))
            | Q(stok_kalemi_id__in=Subquery(emirler.values('hedef_stok_kalemi_id')))
        ).values('urun_kodu')
        urunler = urunler.filter(stok_kodu__in=Subquery(ilgili_sku))

    urunler = urunler.order_by(SIRALAMALAR[filtre.sirala][0])
    sayfalayici = Paginator(urunler, SAYFA_BOYUTU)
    sayfa = sayfalayici.get_page(request.GET.get('sayfa'))
    kodlar = [u.stok_kodu for u in sayfa.object_list]
    kategori_adlari = dict(
        Kategori.objects.using('metaks').filter(
            kategori_id__in={u.kategori_id for u in sayfa.object_list if u.kategori_id}
        ).values_list('kategori_id', 'kategori_adi')
    )
    gorseller = dict(
        AktifUrun.objects.using('metaks').filter(stok_kodu__in=kodlar)
        .values_list('stok_kodu', 'ana_gorsel_dosya_adi')
    )
    ozetler = {
        o.urun_kodu: o for o in StokUrunOzet.objects.using('metaks').filter(urun_kodu__in=kodlar)
    }
    for urun in sayfa.object_list:
        urun.kategori_adi = kategori_adlari.get(urun.kategori_id)
        dosya = gorseller.get(urun.stok_kodu)
        urun.gorsel_url = settings.GORSEL_SUNUCU_BASE_URL + dosya if dosya else None
        ozet = ozetler.get(urun.stok_kodu)
        urun.toplam_stok = ozet.satisa_hazir_toplam if ozet else None
        urun.stok_durumu = (
            'sayilmadi' if ozet is None else ('var' if ozet.satisa_hazir_toplam > 0 else 'sifir')
        )
        urun.stok_ozeti = ozet

    return {
        'sayfa': sayfa, 'filtre': filtre, 'stok_goster': True,
        'siralamalar': [(k, e) for k, (_, e) in SIRALAMALAR.items()],
        'kategori_secenekleri': _stok_kategori_secenekleri(filtre),
        'secili_seritler': _secili_kategori_seritleri(filtre),
        'toplam': sayfalayici.count,
        'temiz_url': filtre.url(
            arama='', kategoriler=[], sadece_stok=False, yer='', lokasyon='',
            kaplama='', montaj='', durum='', boya='', mine='', stok_turu='',
            seviye='', fasoncu='', fason_durum='', parti='', olcu='',
        ),
        'stok_ac_url': filtre.url(sadece_stok=True),
        'stok_kapat_url': filtre.url(sadece_stok=False),
        'sonraki_url': filtre.url(sayfa=sayfa.next_page_number()) if sayfa.has_next() else None,
        'lokasyonlar': list(LokasyonDetay.objects.using('metaks').filter(aktif_mi=True, yaprak_mi=True)),
        'kaplamalar': stok_servisi.kaplama_secenekleri(),
        'renkler': list(Renk.objects.using('metaks').filter(aktif_mi=True)),
        'fasoncular': list(IsOrtagi.objects.using('metaks').filter(
            aktif_mi=True,
            is_ortagi_id__in=Subquery(
                IsOrtagiRolu.objects.using('metaks').filter(rol='FASONCU').values('is_ortagi_id')
            ),
        )),
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


@izin_gerekli('goruntule')
def stok_listesi(request):
    """Stok görünümü: aynı galeri + stok miktarı + "sadece stokta olanlar" filtresi."""
    filtre = ListeFiltresi(request, reverse('katalog:stok_listesi'))
    context = _stok_liste_context(request, filtre)
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


# StokBakiye.varyant_adi ile aynı etiketler; orası view'dan (adlar hazır) okuyor,
# burası ham `stok_kalemleri`'nden kuruyor.
MONTAJ_ETIKETLERI = {
    'HAM': 'ham',
    'YARI_MONTE': 'yarı monte',
    'MONTE': 'monte',
    'BELIRSIZ': 'eski/belirsiz varyant',
}


def _sku_ozetlerini_ekle(hareketler):
    """Sayfadaki hareketlere SKU kodunu ve varyant özetini iliştirir.

    Hareket satırı ürün kodunu taşıyor ama iki farklı kaplama/montaj varyantı aynı
    ürün kodunda görünüyordu — "1005910 çıktı" satırından hangi malın çıktığı
    anlaşılmıyordu. Kaplama ve renk ADLARI `stok_kalemleri`'nde değil ayrı referans
    tablolarında; üçü de sayfa başına tek toplu sorgu (ürün başına sorgu yok).

    Migration 008 öncesi yazılmış hareketlerde `stok_kalemi_id` NULL olabilir;
    o satırlar özetsiz kalır ve şablon yalnız ürün kodunu basar.
    """
    for hareket in hareketler:
        hareket.sku = None
        hareket.varyant_ozeti = ''

    sku_idleri = {h.stok_kalemi_id for h in hareketler if h.stok_kalemi_id}
    if not sku_idleri:
        return

    skular = {
        s.stok_kalemi_id: s
        for s in StokKalemi.objects.using('metaks').filter(stok_kalemi_id__in=sku_idleri)
    }
    kaplama_adlari = dict(
        Kaplama.objects.using('metaks')
        .filter(kaplama_id__in={s.kaplama_id for s in skular.values() if s.kaplama_id})
        .values_list('kaplama_id', 'kaplama_adi')
    )
    renk_idleri = {
        renk_id
        for s in skular.values()
        for renk_id in (s.boya_renk_id, s.mine_renk_id)
        if renk_id
    }
    renk_adlari = dict(
        Renk.objects.using('metaks').filter(renk_id__in=renk_idleri)
        .values_list('renk_id', 'renk_adi')
    )

    for hareket in hareketler:
        sku = skular.get(hareket.stok_kalemi_id)
        if sku is None:
            continue
        boya = renk_adlari.get(sku.boya_renk_id)
        mine = renk_adlari.get(sku.mine_renk_id)
        parcalar = [
            kaplama_adlari.get(sku.kaplama_id),
            f'boya: {boya}' if boya else None,
            f'mine: {mine}' if mine else None,
            MONTAJ_ETIKETLERI.get(sku.montaj_durumu),
        ]
        hareket.sku = sku
        hareket.varyant_ozeti = ' · '.join(p for p in parcalar if p)


@izin_gerekli('hareket')
def hareket_gecmisi(request):
    """stok_hareketleri dökümü: kim, ne zaman, hangi üründe, nereden nereye.

    Salt-okunur — yazmanın tek yolu stok_islemi_kaydet() (bkz. stok_servisi).

    Tarihler `yerel_tarih()` ile aware hâle getiriliyor; hem gösterim hem de tarih
    aralığı filtresi bunun üzerinden çalışıyor. Ham naive UTC kolonuna göre filtrelemek
    gün sınırlarında 3 saatlik kaymaya yol açardı (bkz. models.py::StokHareketi).
    """
    arama = request.GET.get('q', '').strip()
    tip = request.GET.get('tip', '').strip()
    amac = request.GET.get('amac', '').strip()
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
        eslesen_islemler = StokIslemi.objects.using('metaks').filter(
            Q(belge_no__icontains=arama)
            | Q(aciklama__icontains=arama)
            | Q(islem_nedeni__icontains=arama)
        ).values('stok_islem_id')
        hareketler = hareketler.filter(
            Q(stok_kodu__icontains=arama) | Q(aciklama__icontains=arama)
            | Q(stok_islem_id__in=Subquery(eslesen_islemler))
        )
    if tip in stok_servisi.ISLEM_TIPI_DEGERLERI:
        hareketler = hareketler.filter(islem_tipi=tip)
    # İş amacı belge BAŞLIĞINDA (`stok_islemleri.islem_nedeni`), hareket satırında
    # değil: aynı belgenin satırları farklı teknik tiplerde olabiliyor (fason
    # dönüşü bir CIKIS + bir GIRIS üretiyor). Bu yüzden filtre başlık üzerinden
    # alt sorguyla kuruluyor — "Fason dönüşü" seçildiğinde o belgenin İKİ satırı
    # da listede kalıyor, teknik tip filtresi ise yalnız birini bırakırdı.
    if amac in stok_servisi.ISLEM_AMACI_ETIKETLERI:
        amac_islemleri = StokIslemi.objects.using('metaks').filter(
            islem_nedeni=amac
        ).values('stok_islem_id')
        hareketler = hareketler.filter(stok_islem_id__in=Subquery(amac_islemleri))
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
    islem_idleri = {h.stok_islem_id for h in sayfa.object_list if h.stok_islem_id}
    islem_basliklari = {
        i.stok_islem_id: i
        for i in StokIslemi.objects.using('metaks').filter(stok_islem_id__in=islem_idleri)
    }
    ortak_idleri = {i.is_ortagi_id for i in islem_basliklari.values() if i.is_ortagi_id}
    ortak_adlari = dict(
        IsOrtagi.objects.using('metaks').filter(is_ortagi_id__in=ortak_idleri)
        .values_list('is_ortagi_id', 'unvan')
    )
    for hareket in sayfa.object_list:
        hareket.urun = urunler.get(hareket.stok_kodu)
        # Ham değer ('SAYIM_DEVRI') yerine okunur etiket. Şablonda sözlük araması
        # yapılamadığı için (değişken anahtar desteklenmiyor) burada iliştiriliyor.
        hareket.islem_etiketi = stok_servisi.ISLEM_TIPI_ETIKETLERI.get(
            hareket.islem_tipi, hareket.islem_tipi
        )
        hareket.belge = islem_basliklari.get(hareket.stok_islem_id)
        if hareket.belge:
            hareket.islem_amaci = stok_servisi.ISLEM_AMACI_ETIKETLERI.get(
                hareket.belge.islem_nedeni, hareket.belge.islem_nedeni
            )
            hareket.is_ortagi_adi = ortak_adlari.get(hareket.belge.is_ortagi_id)
    _sku_ozetlerini_ekle(sayfa.object_list)

    parametreler = QueryDict(mutable=True)
    for anahtar, deger in [
        ('q', arama), ('tip', tip), ('amac', amac), ('lokasyon', lokasyon or ''),
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
        # Teknik tip (Giriş/Çıkış/Transfer) ile İŞ AMACI ayrı iki filtre ve ikisi de
        # gerekli: "Fasona giden ne var?" sorusunun cevabı tipte değil amaçta,
        # "bu raftan ne çıktı?" sorusununki ise tipte.
        'islem_amaclari': stok_servisi.ISLEM_AMACLARI,
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
            'q': arama, 'tip': tip, 'amac': amac, 'lokasyon': lokasyon,
            'kullanici': kullanici,
            'baslangic': baslangic.isoformat() if baslangic else '',
            'bitis': bitis.isoformat() if bitis else '',
        },
        'filtre_var': bool(
            arama or tip or amac or lokasyon or kullanici or baslangic or bitis
        ),
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


def _detay_urunu(stok_kodu, *, pasif_dahil=False):
    """Katalogda görünmeyen/görselsiz stok kalemini de ortak karta hazırlar."""
    urun = AktifUrun.objects.using('metaks').filter(pk=stok_kodu).first()
    if urun:
        return urun

    if not pasif_dahil:
        return get_object_or_404(AktifUrun.objects.using('metaks'), pk=stok_kodu)

    urun = get_object_or_404(Urun.objects.using('metaks'), pk=stok_kodu)
    urun.kategori_adi = next(iter(
        Kategori.objects.using('metaks').filter(pk=urun.kategori_id)
        .values_list('kategori_adi', flat=True)
    ), None)
    urun.hammadde_adi = next(iter(
        Hammadde.objects.using('metaks').filter(pk=urun.hammadde_id)
        .values_list('hammadde_adi', flat=True)
    ), None)
    urun.ana_gorsel_dosya_adi = None
    urun.gorsel_url = None
    urun.arama_metni = ''
    return urun


def _urun_detay(request, stok_kodu, *, pasif_dahil=False):
    urun = _detay_urunu(stok_kodu, pasif_dahil=pasif_dahil)
    stok_goster = izni_var_mi(request.user, 'goruntule')
    hareket_goster = izni_var_mi(request.user, 'hareket')
    fason_goster = izni_var_mi(request.user, 'fason')

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
        'hareket_goster': hareket_goster,
        'fason_goster': fason_goster,
        'stok_yazabilir': izni_var_mi(request.user, 'islem'),
        'detay_url_adi': 'katalog:urun_detay',
    }

    if stok_goster:
        context['lokasyonlar'] = list(
            StokBakiye.objects.using('metaks')
            .filter(urun_kodu=stok_kodu)
            .order_by('sku_kodu', 'lokasyon_tam_adi', 'stok_durumu_kodu')
        )
        context['stok_ozeti'] = (
            StokUrunOzet.objects.using('metaks').filter(pk=stok_kodu).first()
        )
        context['stok_kalemleri'] = list(
            StokKalemi.objects.using('metaks').filter(urun_kodu=stok_kodu, aktif_mi=True)
        )

    if hareket_goster:
        context['hareketler'] = list(
            StokHareketi.objects.using('metaks')
            .filter(stok_kodu=stok_kodu)
            .annotate(tarih=yerel_tarih())
            .select_related('kaynak_lokasyon', 'hedef_lokasyon')[:25]
        )
        for hareket in context['hareketler']:
            hareket.islem_etiketi = stok_servisi.ISLEM_TIPI_ETIKETLERI.get(
                hareket.islem_tipi, hareket.islem_tipi
            )

    if fason_goster:
        sku_idleri = StokKalemi.objects.using('metaks').filter(
            urun_kodu=stok_kodu
        ).values('stok_kalemi_id')
        context['fason_isleri'] = list(
            FasonIsEmriOzet.objects.using('metaks').filter(
                Q(kaynak_stok_kalemi_id__in=Subquery(sku_idleri))
                | Q(hedef_stok_kalemi_id__in=Subquery(sku_idleri))
            )[:25]
        )

    return render(request, 'katalog/_urun_detay.html', context)


def urun_detay(request, stok_kodu):
    """Yetkiye göre sekmeleri açılan ortak ürün detay paneli."""
    return _urun_detay(request, stok_kodu)


@izin_gerekli('goruntule')
def stok_urun_detay(request, stok_kodu):
    """Eski stok kartı adresi de aynı ortak ürün detayını döndürür."""
    return _urun_detay(request, stok_kodu, pasif_dahil=True)


# --------------------------------------------------------------------------------------
# Eski stok derin bağlantısı
#
# Yazma akışlarının tamamı migration 008'le `katalog/stok_yonetimi.py`'ye taşındı;
# burada yalnızca `/stok/islem/<kod>/` biçimindeki eski adresi canlı tutan
# yönlendirme kaldı. Kendi form/POST mantığı olan `stok_ekle`, `hizli_islem` ve
# ortak `_islem_baglami` yardımcıları 2026-08-05'te SİLİNDİ: üçü de artık hiçbir
# URL'den erişilemiyordu ve şablonlarıyla birlikte var olmayan bir forma
# (`StokEkleFormu`) ve var olmayan parçalara (`_hizli_alan.html`) bağlıydılar.
# --------------------------------------------------------------------------------------


@login_required
def stok_islem(request, stok_kodu):
    """Eski `/stok/islem/<kod>/` bağlantısını kanonik amaç-temelli ekrana taşır.

    Giriş zorunlu çünkü gidilen ekran bir yazma ekranı; anonim kullanıcıyı önce
    yönlendirip sonra oradan geri çevirmek yerine kapı burada kapanıyor.
    """
    return redirect(f"{reverse('katalog:stok_merkezi')}?kod={stok_kodu}")

