"""Migration 008'in SKU, stok belgesi ve fason operasyon ekranları."""

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse

from . import forms, stok_servisi
from .models import AktifUrun, FasonIsEmriOzet, Kategori, StokBakiye, StokKalemi, Urun
from .yetkiler import izin_gerekli, izni_var_mi


def _kullanici_adi(request):
    return request.user.email or request.user.get_username()


def _sku_bul(kod):
    kod = (kod or '').strip()
    if not kod:
        return None
    return (
        StokKalemi.objects.using('metaks').filter(sku_kodu=kod, aktif_mi=True).first()
        or StokKalemi.objects.using('metaks').filter(sku_kodu__iexact=kod, aktif_mi=True).first()
    )


def _satir(sku, tip, miktar, kaynak, hedef, durum, parti_id=None, parti_no=None):
    return {
        'stok_kalemi_id': sku.stok_kalemi_id,
        'islem_tipi': tip,
        'miktar': miktar,
        'kaynak_lokasyon_id': kaynak,
        'hedef_lokasyon_id': hedef,
        'stok_durumu_kodu': durum,
        'parti_id': parti_id,
        'parti_no': parti_no,
    }


def _amac_iznini_denetle(request, amac):
    if amac == 'SAYIM' and not izni_var_mi(request.user, 'sayim'):
        raise PermissionDenied
    if amac == 'DUZELTME' and not izni_var_mi(request.user, 'duzeltme'):
        raise PermissionDenied
    if amac in ('FASON_SEVK', 'FASON_DONUS', 'FIRE') and not izni_var_mi(request.user, 'fason'):
        raise PermissionDenied


def _izinli_amaclar(request):
    amaclar = {kod for kod, _ in stok_servisi.ISLEM_AMACLARI}
    if not izni_var_mi(request.user, 'sayim'):
        amaclar.discard('SAYIM')
    if not izni_var_mi(request.user, 'duzeltme'):
        amaclar.discard('DUZELTME')
    if not izni_var_mi(request.user, 'fason'):
        amaclar -= {'FASON_SEVK', 'FASON_DONUS', 'FIRE'}
    return amaclar


def eski_stok_url_yonlendir(request):
    """`/stok/ekle/` ve `/stok/hizli/` sorgularını tek kanonik URL'ye taşır."""
    hedef = reverse('katalog:stok_merkezi')
    sorgu = request.GET.urlencode()
    return redirect(f'{hedef}?{sorgu}' if sorgu else hedef)


@izin_gerekli('islem')
def stok_merkezi(request):
    """Tek amaç-temelli stok ekranı; bütün kayıtlar yeni atomik DB fonksiyonundan geçer."""
    sonuc = None
    hata = None
    kod = request.GET.get('kod', '').strip()
    initial = {
        'amac': request.GET.get('amac', 'SATIN_ALMA_KABUL'),
        'sku_kodu': kod,
        'stok_durumu_kodu': 'SERBEST',
        'hedef_stok_durumu_kodu': 'SERBEST',
    }
    izinli_amaclar = _izinli_amaclar(request)
    form = forms.StokIslemFormu(
        request.POST or None, initial=initial, izinli_amaclar=izinli_amaclar
    )
    istemci_kimligi = request.POST.get('istemci_kimligi') or stok_servisi.yeni_islem_kimligi()

    if request.method == 'POST' and form.is_valid():
        veri = form.cleaned_data
        amac = veri['amac']
        _amac_iznini_denetle(request, amac)
        sku = _sku_bul(veri['sku_kodu'])
        hedef_kod = (veri.get('hedef_sku_kodu') or '').strip()
        hedef_sku = _sku_bul(hedef_kod) if hedef_kod else sku
        if sku is None:
            form.add_error('sku_kodu', 'Bu kodla aktif bir SKU bulunamadı.')
        elif amac == 'FASON_DONUS' and hedef_sku is None:
            form.add_error('hedef_sku_kodu', 'Dönüşte oluşan SKU bulunamadı.')
        else:
            miktar = veri['miktar']
            kaynak = veri.get('kaynak_lokasyon_id')
            hedef = veri.get('hedef_lokasyon_id')
            durum = veri['stok_durumu_kodu']
            hedef_durum = veri.get('hedef_stok_durumu_kodu') or durum
            parti_no = veri.get('parti_no') or None
            if amac in ('SATIN_ALMA_KABUL', 'URETIM_GIRIS', 'MUSTERI_IADE'):
                satirlar = [_satir(sku, 'GIRIS', miktar, None, hedef, durum, parti_no=parti_no)]
            elif amac in ('SATIS_SEVKI', 'TEDARIKCI_IADE'):
                satirlar = [_satir(sku, 'CIKIS', miktar, kaynak, None, durum, parti_no=parti_no)]
            elif amac in ('IC_TRANSFER', 'FASON_SEVK'):
                satirlar = [_satir(sku, 'TRANSFER', miktar, kaynak, hedef, durum, parti_no=parti_no)]
            elif amac == 'FIRE':
                satirlar = [_satir(sku, 'CIKIS', miktar, kaynak, None, durum, parti_no=parti_no)]
            elif amac == 'FASON_DONUS':
                if hedef_sku.stok_kalemi_id == sku.stok_kalemi_id and hedef_durum == durum:
                    satirlar = [_satir(sku, 'TRANSFER', miktar, kaynak, hedef, durum, parti_no=parti_no)]
                else:
                    satirlar = [
                        _satir(sku, 'CIKIS', miktar, kaynak, None, durum, parti_no=parti_no),
                        _satir(hedef_sku, 'GIRIS', miktar, None, hedef, hedef_durum, parti_no=parti_no),
                    ]
            elif amac == 'SAYIM':
                satirlar = [_satir(sku, 'SAYIM_DEVRI', miktar, None, hedef, durum, parti_no=parti_no)]
            else:  # DUZELTME
                satirlar = [_satir(sku, 'DUZELTME', miktar, kaynak, hedef, durum, parti_no=parti_no)]

            try:
                sonuc = stok_servisi.stok_islemi_kaydet(
                    istemci_kimligi=istemci_kimligi,
                    islem_nedeni=amac,
                    satirlar=satirlar,
                    yapan_kullanici=_kullanici_adi(request),
                    is_ortagi_id=veri.get('is_ortagi_id'),
                    belge_no=veri.get('belge_no', ''),
                    fason_is_emri_id=veri.get('fason_is_emri_id'),
                    duzelttigi_stok_islem_id=veri.get('duzelttigi_stok_islem_id'),
                    aciklama=veri.get('aciklama', ''),
                )
            except stok_servisi.StokIslemHatasi as istisna:
                hata = str(istisna)

            if sonuc and not sonuc['atlandi']:
                form = forms.StokIslemFormu(initial={
                    'amac': amac,
                    'kaynak_lokasyon_id': kaynak,
                    'hedef_lokasyon_id': hedef,
                    'stok_durumu_kodu': durum,
                    'hedef_stok_durumu_kodu': hedef_durum,
                    'is_ortagi_id': veri.get('is_ortagi_id'),
                    'fason_is_emri_id': veri.get('fason_is_emri_id'),
                }, izinli_amaclar=izinli_amaclar)
                istemci_kimligi = stok_servisi.yeni_islem_kimligi()

    secili_sku = _sku_bul(form['sku_kodu'].value())
    bakiyeler = []
    if secili_sku:
        bakiyeler = list(
            StokBakiye.objects.using('metaks')
            .filter(stok_kalemi_id=secili_sku.stok_kalemi_id)
            .exclude(mevcut_miktar=0)
        )
    return render(request, 'katalog/stok_merkezi.html', {
        'form': form,
        'sonuc': sonuc,
        'hata': hata,
        'istemci_kimligi': istemci_kimligi,
        'secili_sku': secili_sku,
        'bakiyeler': bakiyeler,
        'aktif_sekme': 'stok',
    })


@izin_gerekli('islem')
def stok_kodu_onerileri(request):
    arama = request.GET.get('sku_kodu', '').strip()
    kayitlar = []
    if arama:
        kayitlar = list(
            StokKalemi.objects.using('metaks')
            .filter(Q(sku_kodu__icontains=arama) | Q(urun_kodu__icontains=arama), aktif_mi=True)
            .order_by('sku_kodu')[:10]
        )
        urun_kodlari = {k.urun_kodu for k in kayitlar}
        urunler = {
            u.stok_kodu: u for u in Urun.objects.using('metaks').filter(stok_kodu__in=urun_kodlari)
        }
        kategoriler = dict(
            Kategori.objects.using('metaks').filter(
                kategori_id__in={u.kategori_id for u in urunler.values() if u.kategori_id}
            ).values_list('kategori_id', 'kategori_adi')
        )
        gorseller = dict(
            AktifUrun.objects.using('metaks').filter(stok_kodu__in=urun_kodlari)
            .values_list('stok_kodu', 'ana_gorsel_dosya_adi')
        )
        for kayit in kayitlar:
            urun = urunler.get(kayit.urun_kodu)
            kayit.kategori_adi = kategoriler.get(urun.kategori_id) if urun else None
            dosya = gorseller.get(kayit.urun_kodu)
            kayit.gorsel_url = settings.GORSEL_SUNUCU_BASE_URL + dosya if dosya else None
    return render(request, 'katalog/_stok_kodu_onerileri.html', {'kayitlar': kayitlar})


@izin_gerekli('islem')
def stok_kalemi_yeni(request):
    form = forms.StokKalemiFormu(request.POST or None, initial={
        'urun_kodu': request.GET.get('urun_kodu', ''),
    })
    if request.method == 'POST' and form.is_valid():
        try:
            sonuc = stok_servisi.stok_kalemi_kaydet(
                **form.cleaned_data, yapan_kullanici=_kullanici_adi(request)
            )
        except stok_servisi.StokIslemHatasi as istisna:
            form.add_error(None, str(istisna))
        else:
            messages.success(request, f"{sonuc['sku_kodu']}: {sonuc['mesaj']}")
            return redirect(f"{reverse('katalog:stok_merkezi')}?kod={sonuc['sku_kodu']}")
    return render(request, 'katalog/stok_kalemi_formu.html', {'form': form})


@izin_gerekli('fason')
def fason_isleri(request):
    durum = request.GET.get('durum', 'ACIK')
    emirler = FasonIsEmriOzet.objects.using('metaks')
    if durum in ('ACIK', 'TAMAMLANDI', 'IPTAL'):
        emirler = emirler.filter(durum=durum)
    return render(request, 'katalog/fason_isleri.html', {
        'emirler': list(emirler), 'durum': durum, 'aktif_sekme': 'stok',
    })


@izin_gerekli('fason')
def fason_is_emri_yeni(request):
    form = forms.FasonIsEmriFormu(request.POST or None)
    istemci_kimligi = request.POST.get('istemci_kimligi') or stok_servisi.yeni_islem_kimligi()
    if request.method == 'POST' and form.is_valid():
        kaynak = _sku_bul(form.cleaned_data['kaynak_sku_kodu'])
        hedef = _sku_bul(form.cleaned_data['hedef_sku_kodu'])
        if not kaynak:
            form.add_error('kaynak_sku_kodu', 'Gönderilecek SKU bulunamadı.')
        if not hedef:
            form.add_error('hedef_sku_kodu', 'Dönecek SKU bulunamadı.')
        if kaynak and hedef:
            veri = form.cleaned_data.copy()
            veri.pop('kaynak_sku_kodu')
            veri.pop('hedef_sku_kodu')
            try:
                sonuc = stok_servisi.fason_is_emri_kaydet(
                    istemci_kimligi=istemci_kimligi,
                    kaynak_stok_kalemi_id=kaynak.stok_kalemi_id,
                    hedef_stok_kalemi_id=hedef.stok_kalemi_id,
                    yapan_kullanici=_kullanici_adi(request),
                    **veri,
                )
            except stok_servisi.StokIslemHatasi as istisna:
                form.add_error(None, str(istisna))
            else:
                messages.success(request, f"{sonuc['emir_no']}: {sonuc['mesaj']}")
                return redirect('katalog:fason_isleri')
    return render(request, 'katalog/fason_is_emri_formu.html', {
        'form': form, 'istemci_kimligi': istemci_kimligi,
    })


@izin_gerekli('fason')
def is_ortagi_yeni(request):
    form = forms.IsOrtagiFormu(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            sonuc = stok_servisi.is_ortagi_kaydet(
                **form.cleaned_data, yapan_kullanici=_kullanici_adi(request)
            )
        except stok_servisi.StokIslemHatasi as istisna:
            form.add_error(None, str(istisna))
        else:
            messages.success(request, sonuc['mesaj'])
            return redirect('katalog:fason_is_emri_yeni')
    return render(request, 'katalog/is_ortagi_formu.html', {'form': form})
