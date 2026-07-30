"""Yönetim panelinin formları.

Kullanıcı formları Django'nun hazır `UserCreationForm` / `AdminPasswordChangeForm`
sınıflarından türüyor. Sebebi tekrar etmemek: parola gücü doğrulaması
(`AUTH_PASSWORD_VALIDATORS`), parola karması ve bütün hata metinlerinin Türkçesi
oradan bedavaya geliyor. Elle yazılsaydı Django'nun kendi kurallarının ikinci bir
kopyası olurdu ve sürüm yükseltmelerinde sessizce ayrışırdı — `stok_servisi.py`'nin
`stok_hareketi_kaydet()` karşısındaki duruşunun aynısı.

Kullanıcı formları SQLite `default` bağlantısında çalışıyor. Lokasyon formu
(`LokasyonEklemeFormu`) farklı: paylaşımlı METAKS Postgres'teki `lokasyonlar`
tablosuna yazıyor — bkz. o formun kendi docstring'i, cross-DB `ModelForm` kullanırken
düşülen ve burada bilerek kaçınılan bir tuzak var.
"""

from django import forms
from django.contrib.auth.forms import AdminPasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Lokasyon

# Girdi kutularının ortak görünümü. Şablonlarda tek tek yazmak yerine burada:
# form alanları Django tarafından basıldığı için sınıfın da Python tarafında
# verilmesi gerekiyor.
GIRDI_SINIFI = (
    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
    'focus:outline-none focus:border-slate-400 focus:ring-4 focus:ring-slate-900/5'
)
ONAY_KUTUSU_SINIFI = 'w-4 h-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20'


def _girdileri_bicimlendir(form):
    """Her alana ortak Tailwind sınıflarını ekler (onay kutuları ayrı sınıf alır)."""
    for alan in form.fields.values():
        if isinstance(alan.widget, forms.CheckboxInput):
            alan.widget.attrs.setdefault('class', ONAY_KUTUSU_SINIFI)
        else:
            alan.widget.attrs.setdefault('class', GIRDI_SINIFI)


class _EpostaTekilligi:
    """E-postanın başka bir hesapta kullanılmadığını doğrulayan ortak karışım.

    `auth_user.email` üzerinde veritabanı düzeyinde tekillik kısıtı YOK. Buna rağmen
    tekillik aranıyor çünkü e-posta bu sistemde kimliğin kendisi: stok hareketi
    kaydedilirken deftere yazılan değer `request.user.email or username`
    (`views.py`). İki hesap aynı e-postayı taşırsa `stok_hareketleri`'nde "bunu kim
    yaptı" sorusunun cevabı kalıcı olarak belirsizleşir — defter append-only olduğu
    için sonradan düzeltilemez.
    """

    def clean_email(self):
        eposta = self.cleaned_data['email']
        cakisan = User.objects.filter(email__iexact=eposta)
        if self.instance.pk:
            cakisan = cakisan.exclude(pk=self.instance.pk)
        if cakisan.exists():
            raise forms.ValidationError('Bu e-posta başka bir hesapta kullanılıyor.')
        return eposta


class KullaniciEklemeFormu(_EpostaTekilligi, UserCreationForm):
    """Yeni kullanıcı: kullanıcı adı, e-posta, yönetici bayrağı ve parola."""

    # E-posta ZORUNLU (Django'da varsayılan olarak değil). Yukarıdaki gerekçenin
    # devamı: e-postası olmayan kullanıcının yaptığı her hareket deftere kullanıcı
    # adıyla düşer, e-postası olanınki e-postayla — aynı sütunda iki farklı kimlik
    # biçimi karışır ve hareket geçmişindeki "Yapan" filtresi ikiye bölünür.
    email = forms.EmailField(label='E-posta', required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'is_staff')
        labels = {'username': 'Kullanıcı adı', 'is_staff': 'Yönetici'}
        help_texts = {
            'username': 'Giriş için kullanılacak ad. Harf, rakam ve @ . + - _ karakterleri.',
            'is_staff': 'Yönetim paneline erişebilir: kullanıcı ve lokasyon yönetimi.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _girdileri_bicimlendir(self)


class KullaniciDuzenlemeFormu(_EpostaTekilligi, forms.ModelForm):
    """Var olan kullanıcı: e-posta, yönetici bayrağı, aktiflik.

    Kullanıcı adı bilerek düzenlenemez: `stok_hareketleri.yapan_kullanici` e-postası
    olmayan hesaplarda kullanıcı adını saklıyor ve defter append-only. Adı
    değiştirmek geçmiş kayıtları sahipsiz bırakırdı.

    Silme de yok, yalnızca pasife alma — aynı sebep. `lokasyonlar`'daki
    `aktif_mi = false` deseninin ve `metaks_DB`'nin soft-delete disiplininin aynısı.
    """

    email = forms.EmailField(label='E-posta', required=True)

    class Meta:
        model = User
        fields = ('email', 'is_staff', 'is_active')
        labels = {'is_staff': 'Yönetici', 'is_active': 'Hesap aktif'}
        help_texts = {
            'is_staff': 'Yönetim paneline erişebilir: kullanıcı ve lokasyon yönetimi.',
            'is_active': 'Kapatılırsa giriş yapamaz. Geçmiş hareketleri yerinde kalır.',
        }

    def __init__(self, *args, duzenleyen=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.duzenleyen = duzenleyen
        _girdileri_bicimlendir(self)

    def clean(self):
        """Yöneticinin kendini sistemden kilitlemesini engeller.

        Gerçek senaryo: yönetim paneline girebilen tek kişi kendi yetkisini kaldırır
        (ya da hesabını kapatır) ve geri açacak kimse kalmaz — tek çıkış yolu komut
        satırından `createsuperuser` olurdu.

        Ayrıca bir "sistemde son aktif yönetici kalmasın" kontrolü YOK, çünkü bu
        formda ulaşılamaz: düzenleme ekranına girebilmek için aktif yönetici olmak
        şart (`yonetim.yonetici_gerekli`; Django pasife alınan kullanıcının
        oturumunu bir sonraki istekte zaten düşürüyor). Dolayısıyla başkası
        düzenlenirken sistemde her zaman en az bir aktif yönetici — düzenleyenin
        kendisi — vardır; kendisi düzenlenirken de aşağıdaki iki kural devreye
        giriyor. Hiçbir girdinin tetikleyemeyeceği bir kontrol, koruma değil ölü
        koddur ve testle de doğrulanamaz.
        """
        veri = super().clean()

        if self.duzenleyen is not None and self.duzenleyen.pk == self.instance.pk:
            if not veri.get('is_active'):
                self.add_error('is_active', 'Kendi hesabınızı pasife alamazsınız.')
            if not veri.get('is_staff'):
                self.add_error('is_staff', 'Kendi yönetici yetkinizi kaldıramazsınız.')
        return veri


# Kısıt: lokasyonlar_tip_check (metaks_DB migration 004). CHECK kısıtları Django'ya
# yansımıyor — tek otorite veritabanı, ama açılır listenin kendi seçenekleri gerekiyor;
# ikisi ayrışırsa kullanıcı formda seçip gönderdikten SONRA veritabanı hatası görür.
LOKASYON_TIPLERI = [
    ('DAHILI', 'Dahili'),
    ('FASON', 'Fason'),
    ('NUMUNE', 'Numune'),
]
_TIP_ETIKETLERI = dict(LOKASYON_TIPLERI)


class _UstLokasyonAlani(forms.ModelChoiceField):
    """'Üst lokasyon' seçeneklerini yalnızca adla değil tipiyle birlikte gösterir."""

    def label_from_instance(self, obj):
        return f'{obj.lokasyon_adi} ({_TIP_ETIKETLERI.get(obj.tip, obj.tip)})'


class LokasyonEklemeFormu(forms.ModelForm):
    """Yeni lokasyon: depo/dolap kökü ya da bir kökün altında raf.

    Appsmith'in `LokasyonEkle` sorgusunun (yalnızca ad+tip yazan) yerini alıyor —
    bkz. YAPILACAKLAR.md madde 0 ve 2c.

    ⚠️ `ust_lokasyon` bir FOREIGN KEY ve modelin varsayılan yöneticisi
    (`Lokasyon.objects`) `using('metaks')` OLMADAN 'default' (SQLite) bağlantısına
    gider — proje henüz `DATABASE_ROUTERS` eklemedi. Django'nun ModelForm'u FK
    alanları için açılır liste seçeneklerini OTOMATİK olarak `Model._default_manager`
    üzerinden kurar; elle `queryset` verilmezse form SADECE OLUŞTURULURKEN bile
    (render'a hiç gerek kalmadan) "no such table: lokasyonlar" hatasıyla çöker — bu
    ölçülerek doğrulandı. `__init__`'teki queryset ataması bu yüzden opsiyonel bir
    iyileştirme değil, formun çalışması için ZORUNLU.

    Aynı sebeple `Lokasyon.kod`'a modelde `unique=True` KONULMADI (bkz. models.py) —
    tekillik ihlali burada önceden sorgulanmıyor, gerçek INSERT'in `IntegrityError`'ı
    `lokasyon_yonetimi.py`'de yakalanıp Türkçeleştiriliyor.
    """

    tip = forms.ChoiceField(choices=LOKASYON_TIPLERI, label='Tip')

    class Meta:
        model = Lokasyon
        fields = ('lokasyon_adi', 'tip', 'ust_lokasyon', 'kod')
        field_classes = {'ust_lokasyon': _UstLokasyonAlani}
        labels = {
            'lokasyon_adi': 'Ad',
            'ust_lokasyon': 'Üst lokasyon',
            'kod': 'Kısa kod',
        }
        help_texts = {
            'ust_lokasyon': 'Boş bırakılırsa bu bir kök (depo/dolap) olur; seçilirse '
                             'seçilenin altında bir raf olur. Derinlik en fazla 2 '
                             'seviye — bir rafın altına ikinci bir raf açılamaz.',
            'kod': 'İsteğe bağlı kısa adres, ör. "N1" ya da "N1-R3". Boş bırakılabilir.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Yalnızca KÖK ve AKTİF lokasyonlar üst seçilebilir: derinlik 2'de sabit
        # (bir rafın altına raf açılamaz — veritabanı zaten reddeder, ama seçeneği
        # hiç göstermemek daha iyi) ve pasif bir dolabın altına yeni raf açmak
        # kafa karıştırıcı olurdu.
        self.fields['ust_lokasyon'].queryset = Lokasyon.objects.using('metaks').filter(
            ust_lokasyon__isnull=True, aktif_mi=True
        )
        self.fields['ust_lokasyon'].required = False
        self.fields['kod'].required = False
        _girdileri_bicimlendir(self)


class ParolaBelirlemeFormu(AdminPasswordChangeForm):
    """Yöneticinin başka bir kullanıcının parolasını belirlemesi.

    `AdminPasswordChangeForm` bilerek seçildi: eski parolayı sormaz (yönetici zaten
    bilmiyor) ama `AUTH_PASSWORD_VALIDATORS`'ı uygular.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _girdileri_bicimlendir(self)
