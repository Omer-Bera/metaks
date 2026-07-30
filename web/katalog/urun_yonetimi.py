"""Ürün ekleme/düzenleme (`/urun/ekle/`, `/urun/<stok_kodu>/duzenle/`).

`@login_required` — yönetici şart DEĞİL, giriş yapmış herkes ekleyip
düzenleyebilir. Kullanıcı ve lokasyon yönetiminden (`is_staff`) bilerek farklı;
stok işlemiyle aynı kapı. Karar 2026-07-31 (YAPILACAKLAR.md madde 3).

İş kuralları burada TEKRARLANMIYOR: bu view yalnızca formu okuyup
`urun_servisi.urun_kaydet()`'i çağırıyor, dönen Türkçe mesajı taşıyor —
`views.py::stok_islem`'in `stok_servisi` karşısındaki duruşunun aynısı.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from . import urun_servisi
from .forms import UrunFormu
from .models import Urun


def _form_initial(urun):
    """`models.Urun` satırından `UrunFormu`'nun beklediği initial sözlüğü.

    `ModelChoiceField`'lara doğrudan id verilebilir (Django pk ile eşleştirir),
    kategori/hammadde/kaplama için ayrı bir sorguya gerek yok.
    """
    return {
        'stok_kodu': urun.stok_kodu,
        'kategori': urun.kategori_id,
        'urun_tipi': urun.urun_tipi,
        'parent_stok_kodu': urun.parent_stok_kodu or '',
        'varyant_adi': urun.varyant_adi or '',
        'olcu_mm': urun.olcu_mm,
        'hammadde': urun.hammadde_id,
        'kaplama': urun.kaplama_id,
        'boy_ligne': urun.boy_ligne,
        'boya_mine': urun.boya_mine or '',
        'gramaj_gr': urun.gramaj_gr,
        'montaj_durumu': urun.montaj_durumu or '',
        'kalip_versiyonu': urun.kalip_versiyonu or '',
        'aciklama': urun.aciklama or '',
        'kritik_stok_esigi': urun.kritik_stok_esigi,
        'stok_takip_edilsin_mi': urun.stok_takip_edilsin_mi,
    }


def _kaydet(request, form, *, mod):
    """Form geçerliyse `urun_kaydet()`'i çağırır.

    Başarılıysa yönlendirme response'u döner. Hata varsa `form`'a hata eklenip
    `None` döner — çağıran view formu (girilen değerlerle) yeniden render eder.
    """
    stok_kodu = form.cleaned_data['stok_kodu']

    kategori_id = None
    if form.cleaned_data.get('yeni_kategori_adi'):
        kategori_id = urun_servisi.kategori_id_cozumle(form.cleaned_data['yeni_kategori_adi'])
    elif form.cleaned_data.get('kategori'):
        kategori_id = form.cleaned_data['kategori'].kategori_id

    hammadde = form.cleaned_data.get('hammadde')
    kaplama = form.cleaned_data.get('kaplama')

    # Sıra: önce dosya, sonra DB. urun_kaydet() reddederse az önce yazılan
    # dosya geri alınır (aşağıdaki except); ters sırada çökme olsaydı var
    # olmayan bir dosyayı gösteren kırık ürün kalırdı.
    yuklenen = form.cleaned_data.get('ana_gorsel')
    gorsel_dosya_adi = None
    if yuklenen:
        try:
            gorsel_dosya_adi = urun_servisi.sonraki_gorsel_dosya_adi(stok_kodu, yuklenen)
        except urun_servisi.UrunIslemHatasi as istisna:
            form.add_error('ana_gorsel', str(istisna))
            return None
        urun_servisi.gorsel_yaz(gorsel_dosya_adi, yuklenen)

    try:
        sonuc = urun_servisi.urun_kaydet(
            mod=mod,
            stok_kodu=stok_kodu,
            yapan_kullanici=request.user.email or request.user.get_username(),
            kategori_id=kategori_id,
            hammadde_id=hammadde.hammadde_id if hammadde else None,
            kaplama_id=kaplama.kaplama_id if kaplama else None,
            urun_tipi=form.cleaned_data['urun_tipi'],
            parent_stok_kodu=form.cleaned_data.get('parent_stok_kodu'),
            varyant_adi=form.cleaned_data.get('varyant_adi') or None,
            kalip_versiyonu=form.cleaned_data.get('kalip_versiyonu') or None,
            olcu_mm=form.cleaned_data.get('olcu_mm'),
            boy_ligne=form.cleaned_data.get('boy_ligne'),
            boya_mine=form.cleaned_data.get('boya_mine') or None,
            gramaj_gr=form.cleaned_data.get('gramaj_gr'),
            montaj_durumu=form.cleaned_data.get('montaj_durumu') or None,
            aciklama=form.cleaned_data.get('aciklama') or None,
            kritik_stok_esigi=form.cleaned_data['kritik_stok_esigi'],
            stok_takip_edilsin_mi=form.cleaned_data['stok_takip_edilsin_mi'],
            ana_gorsel_dosya_adi=gorsel_dosya_adi,
        )
    except urun_servisi.UrunIslemHatasi as istisna:
        if gorsel_dosya_adi:
            urun_servisi.gorsel_sil(gorsel_dosya_adi)
        form.add_error(None, str(istisna))
        return None

    messages.success(request, sonuc['mesaj'])
    # Katalog/stok listesine değil düzenleme sayfasına dönülüyor: taslak (PASİF,
    # görselsiz) bir ürün v_aktif_urunler'da hiç görünmez, listeye dönmek "nereye
    # kayboldu?" izlenimi verirdi. Düzenleme sayfası AKTİF/PASİF fark etmeksizin
    # her zaman var.
    return redirect('katalog:urun_duzenle', stok_kodu=sonuc['stok_kodu'])


@login_required
def urun_ekle(request):
    # Boş arama sonucundan gelen "bu kodla ürün ekle" bağlantısı stok kodunu
    # önceden doldurur (bkz. liste sayfalarındaki _govde.html).
    on_dolu_kod = request.GET.get('stok_kodu', '').strip()
    form = UrunFormu(
        request.POST or None, request.FILES or None,
        initial={'stok_kodu': on_dolu_kod} if on_dolu_kod else None,
    )
    if request.method == 'POST' and form.is_valid():
        yanit = _kaydet(request, form, mod='EKLE')
        if yanit is not None:
            return yanit

    return render(
        request,
        'katalog/urun_formu.html',
        {'form': form, 'mod': 'EKLE', 'baslik': 'Yeni ürün'},
    )


@login_required
def urun_duzenle(request, stok_kodu):
    # models.Urun (ham urunler), AktifUrun (view) DEĞİL: taslak/PASİF bir ürünü
    # düzenleyebilmek (ör. eksik görseli ekleyip AKTİF'e geçirmek) tam olarak bu
    # ekranın var oluş sebeplerinden biri, v_aktif_urunler o satırı hiç göstermez.
    urun = get_object_or_404(Urun.objects.using('metaks'), pk=stok_kodu)

    if request.method == 'POST':
        # stok_kodu formda disabled=True (bkz. UrunFormu) — Django disabled
        # alanlarda gönderilen veriyi YOK SAYAR, initial'ı kullanır. Bu yüzden
        # initial burada da (GET'teki kadar) doğru verilmek ZORUNDA; unutulursa
        # cleaned_data['stok_kodu'] None'a düşer.
        form = UrunFormu(
            request.POST, request.FILES,
            initial={'stok_kodu': stok_kodu}, stok_kodu_kilitli=True,
        )
    else:
        form = UrunFormu(initial=_form_initial(urun), stok_kodu_kilitli=True)

    if request.method == 'POST' and form.is_valid():
        yanit = _kaydet(request, form, mod='GUNCELLE')
        if yanit is not None:
            return yanit

    mevcut_gorsel = urun_servisi.mevcut_ana_gorsel(stok_kodu)
    return render(
        request,
        'katalog/urun_formu.html',
        {
            'form': form,
            'mod': 'GUNCELLE',
            'baslik': stok_kodu,
            'urun': urun,
            'mevcut_gorsel_url': (
                settings.GORSEL_SUNUCU_BASE_URL + mevcut_gorsel if mevcut_gorsel else None
            ),
        },
    )
