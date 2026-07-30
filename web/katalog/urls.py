from django.urls import path

from . import views

app_name = 'katalog'

urlpatterns = [
    path('', views.urun_listesi, name='urun_listesi'),
]
