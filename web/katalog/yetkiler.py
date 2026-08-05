"""Stok verisini Django auth izinleriyle koruyan ortak kapılar."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse


IZINLER = {
    'goruntule': 'katalog.stok_goruntule',
    'hareket': 'katalog.hareket_goruntule',
    'islem': 'katalog.stok_islem_yap',
    'sayim': 'katalog.sayim_yap',
    'duzeltme': 'katalog.duzeltme_yap',
    'fason': 'katalog.fason_yonet',
}


def izni_var_mi(kullanici, izin):
    """Yöneticiler geçişte tam yetkilidir; diğerleri açık Django izni taşır."""
    return bool(
        kullanici.is_authenticated
        and (kullanici.is_staff or kullanici.has_perm(IZINLER[izin]))
    )


def izin_gerekli(izin):
    def dekorator(view):
        @wraps(view)
        def sarmalayici(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), reverse('katalog:giris'))
            if not izni_var_mi(request.user, izin):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return sarmalayici

    return dekorator
