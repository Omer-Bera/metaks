"""Yönetim panelinin formları.

Kullanıcı formları Django'nun hazır `UserCreationForm` / `AdminPasswordChangeForm`
sınıflarından türüyor. Sebebi tekrar etmemek: parola gücü doğrulaması
(`AUTH_PASSWORD_VALIDATORS`), parola karması ve bütün hata metinlerinin Türkçesi
oradan bedavaya geliyor. Elle yazılsaydı Django'nun kendi kurallarının ikinci bir
kopyası olurdu ve sürüm yükseltmelerinde sessizce ayrışırdı — `stok_servisi.py`'nin
`stok_hareketi_kaydet()` karşısındaki duruşunun aynısı.

Kullanıcı formları SQLite `default` bağlantısında çalışıyor. Lokasyon ve ürün
formları farklı: paylaşımlı METAKS Postgres'e yazıyorlar — ikisinde de cross-DB
`ModelForm` kullanırken düşülen ve burada bilerek kaçınılan tuzaklar var, kendi
docstring'lerinde anlatılıyor. `UrunFormu` bilerek `ModelForm` DEĞİL, düz
`forms.Form` — gerekçe kendi docstring'inde.
"""

from django import forms
from django.contrib.auth.forms import AdminPasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User

from . import urun_servisi
from .models import Hammadde, Kaplama, Kategori, Lokasyon

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
    `aktif_mi = false` deseninin ve `veritabani`'nin soft-delete disiplininin aynısı.
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


# Kısıt: lokasyonlar_tip_check (veritabani migration 004). CHECK kısıtları Django'ya
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


class UrunFormu(forms.Form):
    """Ürün ekleme VE düzenleme — `/urun/ekle/` ve `/urun/<kod>/duzenle/` aynı
    formu kullanıyor (`katalog/urun_yonetimi.py`); fark stok_kodu'nun
    düzenlemede salt-okunur olması ve initial verinin `models.Urun`'dan gelmesi.

    Bilerek `ModelForm` DEĞİL, düz `forms.Form`: yazmanın tek kapısı
    `urun_servisi.urun_kaydet()` (bir fonksiyon çağrısı, `Model.save()` değil) ve
    kategori oluşturma ayrı bir adım (`urun_servisi.kategori_id_cozumle`).
    `ModelForm`'un otomatik `full_clean()`/`validate_unique()` makinesi burada
    hiç devreye girmiyor — `LokasyonEklemeFormu`'nda ölçülüp bulunan cross-DB
    tuzağını (bkz. o formun docstring'i) baştan gereksiz kılıyor.

    ÖNEMLİ — GUNCELLE modu KISMİ değil: `urun_kaydet()` her çağrıda TÜM alanları
    yeniden yazıyor, boş bırakılan alan NULL'a döner (tek istisna görsel). Bu
    yüzden düzenleme view'ı formu HER ZAMAN ürünün güncel tüm alanlarıyla
    `initial=` doldurmak ZORUNDA — bkz. `urun_servisi.urun_kaydet` docstring'i.
    """

    # ---- Temel ----
    stok_kodu = forms.CharField(
        label='Stok kodu', max_length=100,
        help_text='Fiziksel üründeki/kataloğdaki kod. Kaydedildikten sonra değiştirilemez.',
    )

    kategori = forms.ModelChoiceField(
        label='Kategori', queryset=Kategori.objects.none(), required=False,
        empty_label='— seçilmedi —',
    )
    yeni_kategori_adi = forms.CharField(
        label='Ya da yeni kategori', max_length=100, required=False,
        help_text='Doldurulursa yukarıdaki seçim yok sayılır. Aynı isimde (büyük/küçük '
                   'harf fark etmez) kategori zaten varsa yenisi açılmaz, o kullanılır.',
    )

    urun_tipi = forms.ChoiceField(
        label='Ürün tipi', choices=urun_servisi.URUN_TIPLERI, initial='ANA_URUN',
    )
    parent_stok_kodu = forms.CharField(
        label='Ana ürünün stok kodu', max_length=100, required=False,
        help_text='Alt parça/varyant seçildiyse zorunlu. Kodu bilmiyorsanız önce '
                   'katalogda arayıp bulun, sonra buraya yazın.',
    )
    varyant_adi = forms.CharField(label='Varyant adı', max_length=100, required=False)

    olcu_mm = forms.DecimalField(
        label='Ölçü (mm)', max_digits=6, decimal_places=2, required=False,
    )

    ana_gorsel = forms.ImageField(
        label='Ana görsel', required=False,
        help_text='jpg, jpeg ya da png. Boş bırakılırsa (eklemede) ürün görsel '
                   'eklenene kadar taslak kalır — hata değil, sonra tamamlanabilir; '
                   '(düzenlemede) mevcut görsel olduğu gibi kalır.',
    )

    # ---- Detay (katlanır bölüm) ----
    hammadde = forms.ModelChoiceField(
        label='Hammadde', queryset=Hammadde.objects.none(), required=False,
        empty_label='— seçilmedi —',
    )
    kaplama = forms.ModelChoiceField(
        label='Kaplama', queryset=Kaplama.objects.none(), required=False,
        empty_label='— seçilmedi —',
    )
    boy_ligne = forms.DecimalField(
        label='Boy (ligne)', max_digits=6, decimal_places=2, required=False,
    )
    boya_mine = forms.CharField(label='Boya/mine', max_length=100, required=False)
    gramaj_gr = forms.DecimalField(
        label='Gramaj (gr)', max_digits=10, decimal_places=3, required=False,
    )
    montaj_durumu = forms.CharField(label='Montaj durumu', max_length=50, required=False)
    kalip_versiyonu = forms.CharField(label='Kalıp versiyonu', max_length=100, required=False)
    aciklama = forms.CharField(
        label='Açıklama', required=False, widget=forms.Textarea(attrs={'rows': 3}),
    )
    kritik_stok_esigi = forms.IntegerField(label='Kritik stok eşiği', min_value=0, initial=0)
    stok_takip_edilsin_mi = forms.BooleanField(
        label='Stok takibi yapılsın', required=False, initial=True,
        help_text='Kapatılırsa bu ürün stok sayımına dahil edilmez.',
    )

    def __init__(self, *args, stok_kodu_kilitli=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Formun tanımlandığı anda Kategori/Hammadde/Kaplama sorgulanamaz (import
        # sırasında henüz DB bağlantısı yok, üstelik using('metaks') gerekiyor) —
        # queryset'ler burada, her form örneği kurulurken atanıyor.
        self.fields['kategori'].queryset = Kategori.objects.using('metaks').filter(aktif_mi=True)
        self.fields['hammadde'].queryset = Hammadde.objects.using('metaks').filter(aktif_mi=True)
        self.fields['kaplama'].queryset = Kaplama.objects.using('metaks').filter(aktif_mi=True)
        if stok_kodu_kilitli:
            # Düzenlemede stok_kodu değiştirilemez: urun_kaydet() GUNCELLE modunda
            # onu kimlik olarak kullanıyor, değiştirmiyor (veritabani migration 005,
            # "KAPSAM DIŞI: stok_kodu değiştirme").
            self.fields['stok_kodu'].disabled = True
            self.fields['stok_kodu'].help_text = 'Düzenlemede değiştirilemez.'
        _girdileri_bicimlendir(self)

    def clean(self):
        veri = super().clean()

        kategori = veri.get('kategori')
        yeni_kategori_adi = (veri.get('yeni_kategori_adi') or '').strip()
        if kategori and yeni_kategori_adi:
            self.add_error(
                'yeni_kategori_adi',
                'Var olan bir kategori seçtiniz; yeni kategori adını boş bırakın.',
            )
        veri['yeni_kategori_adi'] = yeni_kategori_adi or None

        # Bu kontrol Python tarafında, DB'ye hiç gitmeden — sadece iki alanın
        # birlikte tutarlılığı, bir referans doğrulaması değil. Ana ürünün
        # GERÇEKTEN var olup olmadığını (ve DB'nin kendi Türkçe mesajını)
        # urun_kaydet() zaten kontrol ediyor, burada tekrarlanmıyor.
        urun_tipi = veri.get('urun_tipi')
        parent = (veri.get('parent_stok_kodu') or '').strip()
        if urun_tipi == 'ANA_URUN':
            # JS bu alanları gizliyor ama TEMİZLEMİYOR: kullanıcı önce VARYANT seçip
            # üst ürün yazsa, sonra fikrini değiştirip ANA_URUN'a dönse, gizli kalan
            # eski değer yine de POST edilir. urun_kaydet() bunu reddetmiyor bile
            # (kısıt sadece VARYANT/ALT_PARCA'da üst ürünü zorunlu kılıyor, ANA_URUN'da
            # yasaklamıyor) — yani bu temizlik yapılmazsa "ana ürün" görünen ama aslında
            # bir üst ürüne bağlı tutarsız bir satır sessizce kaydedilebilirdi.
            parent = ''
            veri['varyant_adi'] = ''
        elif urun_tipi and not parent:
            etiket = dict(urun_servisi.URUN_TIPLERI).get(urun_tipi, urun_tipi)
            self.add_error(
                'parent_stok_kodu',
                f'{etiket} tipindeki bir ürün ana ürüne bağlanmalıdır.',
            )
        veri['parent_stok_kodu'] = parent or None

        return veri


class ParolaBelirlemeFormu(AdminPasswordChangeForm):
    """Yöneticinin başka bir kullanıcının parolasını belirlemesi.

    `AdminPasswordChangeForm` bilerek seçildi: eski parolayı sormaz (yönetici zaten
    bilmiyor) ama `AUTH_PASSWORD_VALIDATORS`'ı uygular.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _girdileri_bicimlendir(self)
