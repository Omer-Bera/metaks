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
from .models import Lokasyon, LokasyonDetay, StokHareketi
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

# Silmeyi reddeden üç FK (ikisi defterden, biri hiyerarşiden; hepsi ON DELETE
# RESTRICT). Buton zaten yalnızca silinebilir satırlarda basılıyor, ama liste
# basıldıktan sonra araya bir hareket girerse gelinecek yer burası.
_DEFTERDE_VAR = ('Bu lokasyon silinemez: hareket geçmişinde kayıtları var. '
                 'Geçmişi korumak için pasife alabilirsiniz.')
_SILME_KISIT_MESAJLARI = {
    'stok_hareketleri_kaynak_lokasyon_id_fkey': _DEFTERDE_VAR,
    'stok_hareketleri_hedef_lokasyon_id_fkey': _DEFTERDE_VAR,
    'lokasyonlar_ust_lokasyon_fkey':
        'Bu lokasyon silinemez: altında raf var. Önce rafları silin.',
}


def _kisit_mesaji(hata, mesajlar=_KISIT_MESAJLARI,
                  varsayilan='Bu lokasyon kaydedilemedi: veritabanı bir kısıtı reddetti.'):
    diag = getattr(getattr(hata, '__cause__', None), 'diag', None)
    isim = getattr(diag, 'constraint_name', None)
    return mesajlar.get(isim, varsayilan)


def _silinebilir_kimlikler(kayitlar, raflar_sozlugu):
    """Hangi satırlar gerçekten silinebilir — iki `ON DELETE RESTRICT`'in izin verdiği.

    Karar veritabanının kendisinde; burada yalnızca ÖNCEDEN hesaplanıyor, çünkü
    silinemeyecek bir satırda "Sil" butonu göstermek kullanıcıya tıklattıktan
    sonra hata vermek olurdu. Defterdeki kullanım tek DISTINCT sorgusuyla (alan
    başına bir tane) toplanıyor, lokasyon başına sorgu değil.
    """
    kullanilan = set()
    for alan in ('kaynak_lokasyon_id', 'hedef_lokasyon_id'):
        kullanilan.update(
            StokHareketi.objects.using('metaks')
            .exclude(**{alan: None})
            .values_list(alan, flat=True)
            .distinct()
        )
    return {
        kayit.lokasyon_id
        for kayit in kayitlar
        if kayit.lokasyon_id not in kullanilan
        and not raflar_sozlugu.get(kayit.lokasyon_id)
    }


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

    silinebilir = _silinebilir_kimlikler(kayitlar, raflar_sozlugu)
    for kayit in kayitlar:
        kayit.silinebilir_mi = kayit.lokasyon_id in silinebilir

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
    """`aktif_mi = false` — kullanılmış bir lokasyonun tek çıkış yolu.

    `stok_hareketleri`'nden gelen FK `ON DELETE RESTRICT`: defterde kaydı olan
    lokasyon silinemez, silinmemeli de (geçmiş sahipsiz kalırdı). Pasif satır
    yeni işlemde seçilemez ama hareket geçmişinde "pasif" etiketiyle durur.
    Hiç kullanılmamış satırlar için `lokasyon_sil`'e bakın.
    """
    lokasyon = get_object_or_404(Lokasyon.objects.using('metaks'), pk=pk)
    lokasyon.aktif_mi = False
    lokasyon.save(using='metaks', update_fields=['aktif_mi'])
    messages.success(request, f'"{lokasyon.lokasyon_adi}" pasife alındı.')
    return redirect('katalog:yonetim_lokasyonlar')


@yonetici_gerekli
@require_POST
def lokasyon_sil(request, pk):
    """Yanlışlıkla açılmış satırı listeden tamamen kaldırır — pasife almanın yerine DEĞİL.

    Pasife alma "artık buraya iş yapılmıyor" demek ve geçmişi korumak için var;
    bu ise onun çözemediği tek durum için: gerçekte var olmayan, hiç kullanılmamış
    bir lokasyon listede kalıcı olarak duruyor. Pasife alınsa bile listede
    görünmeye devam ederdi.

    Django cascade denemiyor — ilgili FK'ların hepsi modelde `DO_NOTHING`, yani
    tek atılan sorgu DELETE ve son sözü veritabanının `RESTRICT`'i söylüyor.
    """
    lokasyon = get_object_or_404(Lokasyon.objects.using('metaks'), pk=pk)
    ad = lokasyon.lokasyon_adi
    try:
        lokasyon.delete(using='metaks')
    except IntegrityError as hata:
        messages.error(request, _kisit_mesaji(
            hata, _SILME_KISIT_MESAJLARI,
            'Bu lokasyon silinemedi: veritabanı bir kısıtı reddetti.',
        ))
    else:
        messages.success(request, f'"{ad}" silindi.')
    return redirect('katalog:yonetim_lokasyonlar')
