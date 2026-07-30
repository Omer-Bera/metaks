"""Lokasyon yönetimi (`/yonetim/lokasyonlar/`) — Appsmith'i kapatmanın ön koşulu.

Appsmith'in `LokasyonYonetimi` sayfasının Django karşılığı (bkz. YAPILACAKLAR.md
madde 0 ve 2c). O sayfanın `LokasyonEkle` sorgusu yalnızca `(lokasyon_adi, tip)`
yazıyordu — metaks_DB migration 004'ten (dolap→raf hiyerarşisi) sonra oradan artık
ne bir numune lokasyonu ne de bir raf açılabiliyor. Bu modül onun yerini alıyor.

`stok_hareketleri`/`urunler`'in aksine **yeni bir veritabanı fonksiyonu yok**:
migration 004 lokasyon kurallarının tamamını bildirimsel yazdı (`tip` CHECK'i,
`kok_mu`/`ust_kok_mu` üretilmiş kolonlarla bileşik FK, iki tekillik kısıtı) — kapı
zaten kısıtların kendisi, Django doğrudan INSERT/UPDATE yapabiliyor.
"""

from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import LokasyonEklemeFormu
from .models import Lokasyon, LokasyonDetay
from .yonetim import yonetici_gerekli

# Postgres kısıt adı -> kullanıcıya gösterilecek Türkçe mesaj. Kısıt ihlali formda
# ÖNCEDEN sorgulanmıyor (bkz. forms.py::LokasyonEklemeFormu docstring — bu modelde
# unique=True kullanmak yanlış bağlantıya sorgu atardı); gerçek INSERT'in
# IntegrityError'ı burada yakalanıp çevriliyor.
_KISIT_MESAJLARI = {
    'uq_lokasyonlar_kod': 'Bu kod başka bir lokasyonda kullanılıyor.',
    'uq_lokasyonlar_ust_ad_tip': 'Bu ad ve tipte bir lokasyon zaten var '
                                  '(aynı üst lokasyonun altında ya da kökte).',
}


def _kisit_mesaji(hata):
    diag = getattr(getattr(hata, '__cause__', None), 'diag', None)
    isim = getattr(diag, 'constraint_name', None)
    return _KISIT_MESAJLARI.get(
        isim, 'Bu lokasyon kaydedilemedi: veritabanı bir kısıtı reddetti.'
    )


@yonetici_gerekli
def lokasyonlar(request):
    """Hiyerarşik liste: her kök (depo/dolap), hemen altında kendi rafları.

    `agac`, view'da Python tarafında kurulan `[(kök, [raf, raf, ...]), ...]`
    listesi — şablonda değişken anahtarla sözlük araması yapılamadığı için
    (Django şablon dili desteklemiyor) gruplama burada yapılıyor.
    """
    kayitlar = list(LokasyonDetay.objects.using('metaks').all())

    raflar_sozlugu = {}
    for kayit in kayitlar:
        if kayit.ust_lokasyon_id is not None:
            raflar_sozlugu.setdefault(kayit.ust_lokasyon_id, []).append(kayit)
    for raflar in raflar_sozlugu.values():
        raflar.sort(key=lambda r: r.lokasyon_adi)

    kokler = sorted(
        (k for k in kayitlar if k.ust_lokasyon_id is None),
        key=lambda k: (k.tip, k.lokasyon_adi),
    )
    agac = [(kok, raflar_sozlugu.get(kok.lokasyon_id, [])) for kok in kokler]

    return render(
        request,
        'katalog/yonetim_lokasyonlar.html',
        {
            'agac': agac,
            'aktif_sayisi': sum(1 for k in kayitlar if k.aktif_mi and k.yaprak_mi),
        },
    )


@yonetici_gerekli
def lokasyon_ekle(request):
    form = LokasyonEklemeFormu(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        lokasyon = form.save(commit=False)
        try:
            lokasyon.save(using='metaks')
        except IntegrityError as hata:
            form.add_error(None, _kisit_mesaji(hata))
        else:
            messages.success(request, f'"{lokasyon.lokasyon_adi}" eklendi.')
            return redirect('katalog:yonetim_lokasyonlar')

    return render(request, 'katalog/yonetim_lokasyon_formu.html', {'form': form})


@yonetici_gerekli
@require_POST
def lokasyon_pasife_al(request, pk):
    """Silme yok, yalnızca `aktif_mi = false` — Appsmith'in `LokasyonSil`'i de bu.

    `stok_hareketleri`'nden gelen FK `ON DELETE RESTRICT`, geçmiş silinmemeli.
    """
    lokasyon = get_object_or_404(Lokasyon.objects.using('metaks'), pk=pk)
    lokasyon.aktif_mi = False
    lokasyon.save(using='metaks', update_fields=['aktif_mi'])
    messages.success(request, f'"{lokasyon.lokasyon_adi}" pasife alındı.')
    return redirect('katalog:yonetim_lokasyonlar')
