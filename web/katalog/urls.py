from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

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

    # Django'nun hazır giriş/çıkış view'ları; sadece şablonları bu app'ten.
    # Ana ekrandaki giriş kutusu da buraya POST ediyor (hatalı denemede bu sayfa açılır).
    path(
        'giris/',
        auth_views.LoginView.as_view(template_name='katalog/giris.html'),
        name='giris',
    ),
    path('cikis/', auth_views.LogoutView.as_view(), name='cikis'),
]
