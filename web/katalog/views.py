from django.shortcuts import render

from .models import AktifUrun


def urun_listesi(request):
    """Katalog galerisinin ilk iskeleti: arama + kart ızgarası.

    v_aktif_urunler'ı 'metaks' bağlantısı üzerinden okur (bkz. settings.py,
    models.py). Bu view, gelecekteki gerçek galeri özelliklerinin (kategori
    filtresi, sıralama, sayfalama) üzerine kurulacağı başlangıç noktasıdır -
    şu an sadece arama_metni üzerinden serbest metin arama yapıyor.
    """
    arama = request.GET.get('q', '').strip()

    urunler = AktifUrun.objects.using('metaks').all()
    if arama:
        urunler = urunler.filter(arama_metni__icontains=arama.lower())
    urunler = urunler[:60]

    context = {'urunler': urunler, 'arama': arama}

    if request.headers.get('HX-Request'):
        return render(request, 'katalog/_urun_grid.html', context)
    return render(request, 'katalog/urun_listesi.html', context)
