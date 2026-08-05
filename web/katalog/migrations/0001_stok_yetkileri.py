from django.db import migrations


IZINLER = [
    ('stok_goruntule', 'Stok miktarı ve lokasyonlarını görebilir'),
    ('hareket_goruntule', 'Stok hareket geçmişini görebilir'),
    ('stok_islem_yap', 'Stok girişi, çıkışı ve transferi yapabilir'),
    ('sayim_yap', 'Stok sayımı yapabilir'),
    ('duzeltme_yap', 'Stok düzeltmesi ve ters kayıt yapabilir'),
    ('fason_yonet', 'Fason iş emri ve hareketlerini yönetebilir'),
]


def yetkileri_olustur(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    content_type, _ = ContentType.objects.get_or_create(
        app_label='katalog', model='stok_yetkisi'
    )
    izin_nesneleri = []
    for kod, ad in IZINLER:
        izin, _ = Permission.objects.get_or_create(
            content_type=content_type, codename=kod, defaults={'name': ad}
        )
        if izin.name != ad:
            izin.name = ad
            izin.save(update_fields=['name'])
        izin_nesneleri.append(izin)

    yonetici, _ = Group.objects.get_or_create(name='Stok Yöneticileri')
    yonetici.permissions.set(izin_nesneleri)
    goruntuleyici, _ = Group.objects.get_or_create(name='Stok Görüntüleyicileri')
    goruntuleyici.permissions.set(izin_nesneleri[:2])
    operator, _ = Group.objects.get_or_create(name='Stok Operatörleri')
    operator.permissions.set(izin_nesneleri[:4])
    fason, _ = Group.objects.get_or_create(name='Fason Sorumluları')
    fason.permissions.set([izin_nesneleri[i] for i in (0, 1, 2, 5)])

    for kullanici in User.objects.filter(is_staff=True):
        yonetici.user_set.add(kullanici)


def yetkileri_kaldir(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    Group.objects.filter(name__in=[
        'Stok Yöneticileri', 'Stok Görüntüleyicileri',
        'Stok Operatörleri', 'Fason Sorumluları',
    ]).delete()
    Permission.objects.filter(
        content_type__app_label='katalog',
        content_type__model='stok_yetkisi',
        codename__in=[kod for kod, _ in IZINLER],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(yetkileri_olustur, yetkileri_kaldir),
    ]
