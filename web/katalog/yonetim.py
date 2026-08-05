"""Yönetim paneli (`/yonetim/`) — kullanıcı yönetimi.

Neden `views.py`'de değil: buradaki her şey SQLite `default` bağlantısındaki Django
auth tablolarıyla çalışıyor, `views.py` ise baştan sona `metaks` Postgres'ini okuyor.
İki farklı veri kaynağı, iki farklı sorumluluk. Tek istisna `panel()`: kartlardaki
özet sayılar için `metaks`'e de tek bir sayım sorgusu atıyor — lokasyon yönetiminin
kendisi (ekleme/pasife alma) `lokasyon_yonetimi.py`'de.

Neden Django'nun hazır `/admin/`'i yetmiyor: yapabiliyor, ama ekip için uygun değil —
izin matrisi, log kayıtları ve İngilizce/çeviri karışımı terimler günlük işte gürültü.
`/admin/` kaçış yolu olarak açık kalıyor.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    STOK_ROLLERI,
    KullaniciDuzenlemeFormu,
    KullaniciEklemeFormu,
    ParolaBelirlemeFormu,
    kullanicinin_stok_rolu,
)
from .models import LokasyonDetay, StokHareketi


def yonetici_gerekli(view):
    """`is_staff` kapısı.

    `login_required`'dan farkı, giriş yapmış ama yetkisiz kullanıcıyı giriş ekranına
    geri göndermemesi: zaten giriş yapmış birine boş bir giriş formu göstermek
    "parolamı mı yanlış girdim?" izlenimi verir. Doğru cevap 403.

    `is_staff` bilinçli olarak seçildi (yeni bir rol tablosu değil): Django'da hazır,
    şema değişikliği istemiyor ve yapılacaklar listesindeki 2b maddesi zaten "en
    azından yönetici mi ayrımının yeri hazırlansın" diyor. Gerçek rol/izin ayrımı
    (fason kullanıcı, salt-okunur personel) buradan büyütülecek.
    """

    @wraps(view)
    def sarmalayici(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse('katalog:giris'))
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return sarmalayici


@yonetici_gerekli
def panel(request):
    """Yönetim ana sayfası: kartlar + her birinin bugünkü sayısı."""
    return render(
        request,
        'katalog/yonetim.html',
        {
            'kullanici_sayisi': User.objects.filter(is_active=True).count(),
            'yonetici_sayisi': User.objects.filter(is_active=True, is_staff=True).count(),
            'lokasyon_sayisi': LokasyonDetay.objects.using('metaks')
            .filter(aktif_mi=True, yaprak_mi=True)
            .count(),
        },
    )


@yonetici_gerekli
def kullanicilar(request):
    """Kullanıcı listesi.

    `hareket_sayisi`: bu hesabın deftere yazdığı satır sayısı — pasife almadan önce
    "bu kimdi, bir şey yapmış mı" sorusunun cevabı. `stok_hareketleri` PAYLAŞIMLI
    Postgres'te, kullanıcılar SQLite'ta; iki bağlantı arasında JOIN yapılamayacağı
    için tek bir GROUP BY sorgusuyla sayılar toplanıp Python'da eşleştiriliyor
    (kullanıcı başına sorgu değil — N+1 yok).
    """
    kayitlar = list(User.objects.order_by('-is_active', 'username'))

    sayimlar = dict(
        StokHareketi.objects.using('metaks')
        .order_by()  # Meta.ordering GROUP BY'a sızmasın
        .values_list('yapan_kullanici')
        .annotate(adet=Count('hareket_id'))
    )
    for kayit in kayitlar:
        # views.py deftere `email or username` yazıyor; ikisini de aramak zorundayız,
        # çünkü hesabın e-postası sonradan eklenmiş olabilir ve eski satırlar
        # kullanıcı adıyla kalmıştır.
        kayit.hareket_sayisi = sayimlar.get(kayit.email, 0) + sayimlar.get(
            kayit.get_username(), 0
        )
        rol = kullanicinin_stok_rolu(kayit)
        kayit.stok_rolu_etiketi = dict(STOK_ROLLERI)[rol]

    return render(
        request,
        'katalog/yonetim_kullanicilar.html',
        {
            'kullanicilar': kayitlar,
            'aktif_sayisi': sum(1 for k in kayitlar if k.is_active),
        },
    )


@yonetici_gerekli
def kullanici_ekle(request):
    form = KullaniciEklemeFormu(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        yeni = form.save()
        messages.success(
            request,
            f'"{yeni.get_username()}" oluşturuldu.'
            + (' Yönetici yetkisi verildi.' if yeni.is_staff else ''),
        )
        return redirect('katalog:yonetim_kullanicilar')

    return render(
        request,
        'katalog/yonetim_kullanici_formu.html',
        {'form': form, 'baslik': 'Yeni kullanıcı', 'kaydet_etiketi': 'Kullanıcıyı oluştur'},
    )


@yonetici_gerekli
def kullanici_duzenle(request, pk):
    kullanici = get_object_or_404(User, pk=pk)
    form = KullaniciDuzenlemeFormu(
        request.POST or None, instance=kullanici, duzenleyen=request.user
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'"{kullanici.get_username()}" güncellendi.')
        return redirect('katalog:yonetim_kullanicilar')

    return render(
        request,
        'katalog/yonetim_kullanici_formu.html',
        {
            'form': form,
            'kullanici': kullanici,
            'baslik': kullanici.get_username(),
            'kaydet_etiketi': 'Değişiklikleri kaydet',
        },
    )


@yonetici_gerekli
def kullanici_parola(request, pk):
    """Yöneticinin başka bir hesabın parolasını belirlemesi (kendisininki dahil)."""
    kullanici = get_object_or_404(User, pk=pk)
    form = ParolaBelirlemeFormu(kullanici, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if kullanici.pk == request.user.pk:
            # Parola değişince session auth hash'i de değişir ve kullanıcı bir sonraki
            # istekte sessizce dışarı atılır. update_session_auth_hash oturumu yeni
            # hash'le tazeleyip bunu önlüyor — Django'nun bu iş için önerdiği yol.
            update_session_auth_hash(request, kullanici)
            messages.success(request, 'Parolanız değiştirildi. Oturumunuz açık kaldı.')
        else:
            messages.success(
                request, f'"{kullanici.get_username()}" parolası değiştirildi.'
            )
        return redirect('katalog:yonetim_kullanicilar')

    return render(
        request,
        'katalog/yonetim_kullanici_formu.html',
        {
            'form': form,
            'kullanici': kullanici,
            'baslik': f'{kullanici.get_username()} · parola',
            'kaydet_etiketi': 'Parolayı değiştir',
            'parola_ekrani': True,
        },
    )
