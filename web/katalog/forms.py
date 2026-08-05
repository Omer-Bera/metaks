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
from django.contrib.auth.models import Group, User

from . import stok_servisi, urun_servisi
from .models import (
    FasonIsEmriOzet,
    Hammadde,
    IsOrtagi,
    IsOrtagiRolu,
    Kategori,
    Lokasyon,
    LokasyonDetay,
)

# Girdi kutularının ortak görünümü. Şablonlarda tek tek yazmak yerine burada:
# form alanları Django tarafından basıldığı için sınıfın da Python tarafında
# verilmesi gerekiyor.
GIRDI_SINIFI = (
    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
    'focus:outline-none focus:border-slate-400 focus:ring-4 focus:ring-slate-900/5'
)
ONAY_KUTUSU_SINIFI = 'w-4 h-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20'

STOK_ROLLERI = [
    ('YOK', 'Stok yetkisi yok'),
    ('GORUNTULE', 'Stok görüntüleyici'),
    ('OPERATOR', 'Stok operatörü'),
    ('FASON', 'Fason sorumlusu'),
    ('YONETICI', 'Stok yöneticisi'),
]
STOK_ROL_GRUPLARI = {
    'GORUNTULE': 'Stok Görüntüleyicileri',
    'OPERATOR': 'Stok Operatörleri',
    'FASON': 'Fason Sorumluları',
    'YONETICI': 'Stok Yöneticileri',
}


def kullanicinin_stok_rolu(kullanici):
    grup_adlari = set(kullanici.groups.values_list('name', flat=True))
    for kod in ('YONETICI', 'FASON', 'OPERATOR', 'GORUNTULE'):
        if STOK_ROL_GRUPLARI[kod] in grup_adlari:
            return kod
    return 'YOK'


def stok_rolunu_kaydet(kullanici, rol):
    stok_gruplari = Group.objects.filter(name__in=STOK_ROL_GRUPLARI.values())
    kullanici.groups.remove(*stok_gruplari)
    grup_adi = STOK_ROL_GRUPLARI.get(rol)
    if grup_adi:
        kullanici.groups.add(Group.objects.get(name=grup_adi))


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
    stok_rolu = forms.ChoiceField(
        label='Stok rolü', choices=STOK_ROLLERI,
        help_text='Sayım, düzeltme ve fason yetkileri role göre ayrı verilir.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'stok_rolu', 'is_staff')
        labels = {'username': 'Kullanıcı adı', 'is_staff': 'Yönetici'}
        help_texts = {
            'username': 'Giriş için kullanılacak ad. Harf, rakam ve @ . + - _ karakterleri.',
            'is_staff': 'Yönetim paneline erişebilir: kullanıcı ve lokasyon yönetimi.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _girdileri_bicimlendir(self)

    def save(self, commit=True):
        kullanici = super().save(commit=commit)
        if commit:
            stok_rolunu_kaydet(kullanici, self.cleaned_data['stok_rolu'])
        return kullanici


class KullaniciDuzenlemeFormu(_EpostaTekilligi, forms.ModelForm):
    """Var olan kullanıcı: e-posta, yönetici bayrağı, aktiflik.

    Kullanıcı adı bilerek düzenlenemez: `stok_hareketleri.yapan_kullanici` e-postası
    olmayan hesaplarda kullanıcı adını saklıyor ve defter append-only. Adı
    değiştirmek geçmiş kayıtları sahipsiz bırakırdı.

    Silme de yok, yalnızca pasife alma — aynı sebep. `lokasyonlar`'daki
    `aktif_mi = false` deseninin ve `veritabani`'nin soft-delete disiplininin aynısı.
    """

    email = forms.EmailField(label='E-posta', required=True)
    stok_rolu = forms.ChoiceField(
        label='Stok rolü', choices=STOK_ROLLERI,
        help_text='Görüntüleme, işlem, sayım, düzeltme ve fason izinlerini belirler.',
    )

    class Meta:
        model = User
        fields = ('email', 'stok_rolu', 'is_staff', 'is_active')
        labels = {'is_staff': 'Yönetici', 'is_active': 'Hesap aktif'}
        help_texts = {
            'is_staff': 'Yönetim paneline erişebilir: kullanıcı ve lokasyon yönetimi.',
            'is_active': 'Kapatılırsa giriş yapamaz. Geçmiş hareketleri yerinde kalır.',
        }

    def __init__(self, *args, duzenleyen=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.duzenleyen = duzenleyen
        if self.instance.pk:
            self.initial['stok_rolu'] = kullanicinin_stok_rolu(self.instance)
        _girdileri_bicimlendir(self)

    def save(self, commit=True):
        kullanici = super().save(commit=commit)
        if commit:
            stok_rolunu_kaydet(kullanici, self.cleaned_data['stok_rolu'])
        return kullanici

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
    is_ortagi_id = forms.TypedChoiceField(
        label='Bağlı fasoncu', coerce=int, choices=(), required=False, empty_value=None,
        help_text='Yalnız FASON tipinde zorunludur.',
    )

    class Meta:
        model = Lokasyon
        fields = ('lokasyon_adi', 'tip', 'ust_lokasyon', 'kod', 'is_ortagi_id')
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
        fasoncu_idleri = IsOrtagiRolu.objects.using('metaks').filter(rol='FASONCU').values_list(
            'is_ortagi_id', flat=True
        )
        self.fields['is_ortagi_id'].choices = [('', '— seçilmedi —')] + list(
            IsOrtagi.objects.using('metaks').filter(
                aktif_mi=True, is_ortagi_id__in=fasoncu_idleri
            ).values_list('is_ortagi_id', 'unvan')
        )
        _girdileri_bicimlendir(self)

    def clean(self):
        veri = super().clean()
        if veri.get('tip') == 'FASON' and not veri.get('is_ortagi_id'):
            self.add_error('is_ortagi_id', 'Fason lokasyonu bir fasoncuya bağlanmalıdır.')
        if veri.get('tip') != 'FASON':
            veri['is_ortagi_id'] = None
        return veri


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
    #
    # Kaplama, boya/mine ve montaj durumu ürün ana verisinden ÇIKARILDI: aynı ürün
    # farklı ticari varyantlarda stoklanabilir. Migration 008 sonrasında bunların
    # kontrollü kimliği `stok_kalemleri` (SKU), giriş noktası `/stok/islem/`dir.
    #
    # `urunler` tablosundaki kaplama_id/boya_mine/montaj_durumu kolonları
    # DÜŞÜRÜLMEDİ ama artık yazılmıyor — üçü de 2.974 satırın hepsinde zaten
    # NULL'dı (ölçüldü), yani kaldırmak hiçbir veri kaybetmedi.
    hammadde = forms.ModelChoiceField(
        label='Hammadde', queryset=Hammadde.objects.none(), required=False,
        empty_label='— seçilmedi —',
    )
    boy_ligne = forms.DecimalField(
        label='Boy (ligne)', max_digits=6, decimal_places=2, required=False,
    )
    gramaj_gr = forms.DecimalField(
        label='Gramaj (gr)', max_digits=10, decimal_places=3, required=False,
    )
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
        # Formun tanımlandığı anda Kategori/Hammadde sorgulanamaz (import
        # sırasında henüz DB bağlantısı yok, üstelik using('metaks') gerekiyor) —
        # queryset'ler burada, her form örneği kurulurken atanıyor.
        self.fields['kategori'].queryset = Kategori.objects.using('metaks').filter(aktif_mi=True)
        self.fields['hammadde'].queryset = Hammadde.objects.using('metaks').filter(aktif_mi=True)
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


class StokIslemFormu(forms.Form):
    """Tek stok merkezi: kullanıcı teknik hareketi değil iş amacını seçer."""

    amac = forms.ChoiceField(label='Ne yapıyorsunuz?', choices=stok_servisi.ISLEM_AMACLARI)
    sku_kodu = forms.CharField(label='Ürün veya SKU kodu', max_length=100)
    hedef_sku_kodu = forms.CharField(
        label='Dönüşte oluşan SKU', max_length=100, required=False,
        help_text='Fason dönüşünde ürün değişiyorsa doldurun; aynı kalıyorsa boş bırakın.',
    )
    miktar = forms.IntegerField(label='Miktar', min_value=0)
    kaynak_lokasyon_id = forms.TypedChoiceField(
        label='Kaynak lokasyon', coerce=int, choices=(), required=False, empty_value=None,
    )
    hedef_lokasyon_id = forms.TypedChoiceField(
        label='Hedef lokasyon', coerce=int, choices=(), required=False, empty_value=None,
    )
    stok_durumu_kodu = forms.ChoiceField(
        label='Kaynak / normal stok durumu', choices=stok_servisi.STOK_DURUMLARI,
    )
    hedef_stok_durumu_kodu = forms.ChoiceField(
        label='Dönüşte hedef stok durumu', choices=stok_servisi.STOK_DURUMLARI,
        required=False,
    )
    is_ortagi_id = forms.TypedChoiceField(
        label='Müşteri / tedarikçi', coerce=int, choices=(), required=False, empty_value=None,
    )
    fason_is_emri_id = forms.TypedChoiceField(
        label='Fason iş emri', coerce=int, choices=(), required=False, empty_value=None,
    )
    belge_no = forms.CharField(label='Belge / referans no', max_length=100, required=False)
    parti_no = forms.CharField(
        label='Parti / lot no', max_length=100, required=False,
        help_text='İzlenmesi gereken kabul ve üretim partilerinde doldurun.',
    )
    duzelttigi_stok_islem_id = forms.IntegerField(
        label='Tersine çevrilen işlem no', min_value=1, required=False,
        help_text='Düzeltmede zorunludur; hareket geçmişindeki belge numarasını girin.',
    )
    aciklama = forms.CharField(
        label='Açıklama', required=False, widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, izinli_amaclar=None, **kwargs):
        super().__init__(*args, **kwargs)
        if izinli_amaclar is not None:
            self.fields['amac'].choices = [
                secenek for secenek in stok_servisi.ISLEM_AMACLARI
                if secenek[0] in izinli_amaclar
            ]
        lokasyonlar = list(
            LokasyonDetay.objects.using('metaks').filter(aktif_mi=True, yaprak_mi=True)
        )
        lokasyon_secenekleri = [
            (l.lokasyon_id, f'{l.tam_ad} ({l.tip})') for l in lokasyonlar
        ]
        bos = [('', '— seçilmedi —')]
        self.fields['kaynak_lokasyon_id'].choices = bos + lokasyon_secenekleri
        self.fields['hedef_lokasyon_id'].choices = bos + lokasyon_secenekleri
        roller = {}
        for ortak_id, rol in IsOrtagiRolu.objects.using('metaks').values_list(
            'is_ortagi_id', 'rol'
        ):
            roller.setdefault(ortak_id, []).append(rol)
        self.fields['is_ortagi_id'].choices = bos + [
            (o.is_ortagi_id, f"{o.unvan} ({', '.join(roller.get(o.is_ortagi_id, []))})")
            for o in IsOrtagi.objects.using('metaks').filter(aktif_mi=True)
        ]
        self.fields['fason_is_emri_id'].choices = bos + [
            (
                e.fason_is_emri_id,
                f'{e.emir_no} · {e.fasoncu_adi} · {e.kaynak_sku_kodu} → {e.hedef_sku_kodu}',
            )
            for e in FasonIsEmriOzet.objects.using('metaks').filter(durum='ACIK')
        ]
        _girdileri_bicimlendir(self)

    def clean(self):
        veri = super().clean()
        amac = veri.get('amac')
        miktar = veri.get('miktar')
        if amac != 'SAYIM' and miktar is not None and miktar <= 0:
            self.add_error('miktar', 'Miktar sıfırdan büyük olmalıdır.')
        if amac in ('SATIN_ALMA_KABUL', 'URETIM_GIRIS') and not veri.get('hedef_lokasyon_id'):
            self.add_error('hedef_lokasyon_id', 'Bu işlem için hedef lokasyon zorunludur.')
        if amac == 'SATIS_SEVKI' and not veri.get('kaynak_lokasyon_id'):
            self.add_error('kaynak_lokasyon_id', 'Satış sevki için kaynak lokasyon zorunludur.')
        if amac == 'IC_TRANSFER':
            if not veri.get('kaynak_lokasyon_id'):
                self.add_error('kaynak_lokasyon_id', 'Transfer için kaynak zorunludur.')
            if not veri.get('hedef_lokasyon_id'):
                self.add_error('hedef_lokasyon_id', 'Transfer için hedef zorunludur.')
        if amac == 'SAYIM' and not veri.get('hedef_lokasyon_id'):
            self.add_error('hedef_lokasyon_id', 'Sayımın yapıldığı lokasyon zorunludur.')
        if amac in ('SATIN_ALMA_KABUL', 'SATIS_SEVKI') and not veri.get('is_ortagi_id'):
            self.add_error('is_ortagi_id', 'Müşteri / tedarikçi seçimi zorunludur.')
        if amac in ('FASON_SEVK', 'FASON_DONUS', 'FIRE') and not veri.get('fason_is_emri_id'):
            self.add_error('fason_is_emri_id', 'Fason iş emri zorunludur.')
        if amac in ('FASON_SEVK', 'FASON_DONUS'):
            if not veri.get('kaynak_lokasyon_id'):
                self.add_error('kaynak_lokasyon_id', 'Fason hareketinde kaynak zorunludur.')
            if not veri.get('hedef_lokasyon_id'):
                self.add_error('hedef_lokasyon_id', 'Fason hareketinde hedef zorunludur.')
        if amac == 'FIRE' and not veri.get('kaynak_lokasyon_id'):
            self.add_error('kaynak_lokasyon_id', 'Firenin bulunduğu fason lokasyonu zorunludur.')
        if amac == 'DUZELTME':
            if not veri.get('duzelttigi_stok_islem_id'):
                self.add_error('duzelttigi_stok_islem_id', 'Düzeltilen işlem numarası zorunludur.')
            if not (veri.get('aciklama') or '').strip():
                self.add_error('aciklama', 'Düzeltme gerekçesi zorunludur.')
            if not veri.get('kaynak_lokasyon_id') and not veri.get('hedef_lokasyon_id'):
                self.add_error('kaynak_lokasyon_id', 'Kaynak veya hedef lokasyondan biri zorunludur.')
        return veri


class StokKalemiFormu(forms.Form):
    urun_kodu = forms.CharField(label='Ürün kodu', max_length=100)
    kaplama_id = forms.TypedChoiceField(
        label='Kaplama', coerce=int, choices=(), required=False, empty_value=None,
    )
    boya_renk = forms.CharField(label='Boya rengi', max_length=100, required=False)
    mine_renk = forms.CharField(label='Mine rengi', max_length=100, required=False)
    montaj_durumu = forms.ChoiceField(
        label='Montaj hali', choices=stok_servisi.MONTAJ_DURUMLARI,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kaplama_id'].choices = [
            ('', '— kaplama yok/belirsiz —'), *stok_servisi.kaplama_secenekleri()
        ]
        _girdileri_bicimlendir(self)


class FasonIsEmriFormu(forms.Form):
    is_ortagi_id = forms.TypedChoiceField(
        label='Fasoncu', coerce=int, choices=(), empty_value=None,
    )
    fason_lokasyon_id = forms.TypedChoiceField(
        label='Fason lokasyonu', coerce=int, choices=(), empty_value=None,
    )
    kaynak_sku_kodu = forms.CharField(label='Gönderilecek SKU', max_length=100)
    hedef_sku_kodu = forms.CharField(label='Dönecek SKU', max_length=100)
    islem_turu = forms.ChoiceField(
        label='İşlem', choices=[
            ('KAPLAMA', 'Kaplama'), ('MINE', 'Mine'), ('BOYA', 'Boya'),
            ('MONTAJ', 'Montaj'), ('DIGER', 'Diğer'),
        ],
    )
    kaplama_cesidi = forms.ChoiceField(
        label='Kaplama yöntemi', required=False,
        choices=[('', '— uygulanmıyor/belirsiz —'), *stok_servisi.KAPLAMA_CESITLERI],
    )
    planlanan_miktar = forms.IntegerField(label='Planlanan miktar', min_value=1)
    beklenen_donus_tarihi = forms.DateField(
        label='Beklenen dönüş', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
    )
    aciklama = forms.CharField(
        label='Açıklama', required=False, widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fasoncu_idleri = IsOrtagiRolu.objects.using('metaks').filter(rol='FASONCU').values_list(
            'is_ortagi_id', flat=True
        )
        self.fields['is_ortagi_id'].choices = list(
            IsOrtagi.objects.using('metaks').filter(
                aktif_mi=True, is_ortagi_id__in=fasoncu_idleri
            ).values_list('is_ortagi_id', 'unvan')
        )
        self.fields['fason_lokasyon_id'].choices = [
            (l.lokasyon_id, l.tam_ad)
            for l in LokasyonDetay.objects.using('metaks').filter(
                aktif_mi=True, yaprak_mi=True, tip='FASON'
            )
        ]
        _girdileri_bicimlendir(self)


class IsOrtagiFormu(forms.Form):
    kod = forms.CharField(label='Kısa kod', max_length=50)
    unvan = forms.CharField(label='Unvan', max_length=255)
    roller = forms.MultipleChoiceField(
        label='Roller',
        choices=[
            ('MUSTERI', 'Müşteri'), ('TEDARIKCI', 'Tedarikçi'), ('FASONCU', 'Fasoncu'),
        ],
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _girdileri_bicimlendir(self)
