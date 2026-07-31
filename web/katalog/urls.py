from django.contrib.auth import views as auth_views
from django.urls import path

from . import lokasyon_yonetimi, urun_yonetimi, views, yonetim

app_name = 'katalog'

# stok_kodu harf/alt çizgi/tire içerebiliyor ("654_032", "1805012-YENI"),
# <str:> bunların hepsini karşılıyor.
urlpatterns = [
    path('', views.ana_ekran, name='ana_ekran'),

    path('katalog/', views.urun_listesi, name='urun_listesi'),
    path('katalog/urun/<str:stok_kodu>/', views.urun_detay, name='urun_detay'),

    path('stok/', views.stok_listesi, name='stok_listesi'),
    path('stok/urun/<str:stok_kodu>/', views.stok_urun_detay, name='stok_urun_detay'),
    path('stok/islem/<str:stok_kodu>/', views.stok_islem, name='stok_islem'),
    path('stok/hareketler/', views.hareket_gecmisi, name='hareket_gecmisi'),

    # Hızlı giriş: depo sahası ekranı. Tek URL, üç iş — kod çözme (GET), canlı öneri
    # (GET ?ara=1) ve hareket kaydı (POST). Üçü de aynı #islem-alani'nı tazelediği
    # için ayrı uç noktalara bölmek gereksiz olurdu.
    path('stok/hizli/', views.hizli_islem, name='hizli_islem'),

    # Django'nun hazır giriş/çıkış view'ları; sadece şablonları bu app'ten.
    # Kök URL giriş yapılmamışken buraya yönlendiriyor (bkz. views.ana_ekran).
    # redirect_authenticated_user: giriş yapmış biri /giris/'e gelirse panele döner,
    # boş bir form görmez.
    path(
        'giris/',
        auth_views.LoginView.as_view(
            template_name='katalog/giris.html',
            redirect_authenticated_user=True,
        ),
        name='giris',
    ),
    path('misafir/', views.misafir_devam, name='misafir'),
    path('cikis/', auth_views.LogoutView.as_view(), name='cikis'),

    # Ürün ekleme/düzenleme — yönetim paneli DEĞİL: is_staff değil, giriş yapmış
    # herkes kullanabiliyor (bkz. urun_yonetimi.py).
    path('urun/ekle/', urun_yonetimi.urun_ekle, name='urun_ekle'),
    path('urun/<str:stok_kodu>/duzenle/', urun_yonetimi.urun_duzenle, name='urun_duzenle'),

    # Yönetim paneli — hepsi is_staff kapısının arkasında (bkz. yonetim.py).
    path('yonetim/', yonetim.panel, name='yonetim'),
    path('yonetim/kullanicilar/', yonetim.kullanicilar, name='yonetim_kullanicilar'),
    path('yonetim/kullanicilar/yeni/', yonetim.kullanici_ekle, name='yonetim_kullanici_ekle'),
    path(
        'yonetim/kullanicilar/<int:pk>/',
        yonetim.kullanici_duzenle,
        name='yonetim_kullanici_duzenle',
    ),
    path(
        'yonetim/kullanicilar/<int:pk>/parola/',
        yonetim.kullanici_parola,
        name='yonetim_kullanici_parola',
    ),

    path('yonetim/lokasyonlar/', lokasyon_yonetimi.lokasyonlar, name='yonetim_lokasyonlar'),
    path(
        'yonetim/lokasyonlar/yeni/',
        lokasyon_yonetimi.lokasyon_ekle,
        name='yonetim_lokasyon_ekle',
    ),
    path(
        'yonetim/lokasyonlar/<int:pk>/pasife-al/',
        lokasyon_yonetimi.lokasyon_pasife_al,
        name='yonetim_lokasyon_pasife_al',
    ),
    path(
        'yonetim/lokasyonlar/<int:pk>/sil/',
        lokasyon_yonetimi.lokasyon_sil,
        name='yonetim_lokasyon_sil',
    ),
]
