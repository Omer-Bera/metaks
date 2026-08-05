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


class LokasyonSecici(forms.Select):
    """Lokasyon `<option>`'larına `data-tip` basar.

    Tek amacı stok işlem formundaki JS'in seçenekleri iş amacına göre süzebilmesi:
    "Fasona gönder" seçiliyken hedef listesinde dahili rafların görünmesi, kullanıcıyı
    ancak formu gönderdikten SONRA `stok_islemi_kaydet()`'in reddedeceği bir seçime
    davet ediyordu. Tip bilgisi şablonda `{% for %}` ile basılamıyor çünkü seçenekleri
    Django'nun widget'ı üretiyor.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # lokasyon_id -> tip. Form `__init__`'inde seçeneklerle birlikte doldurulur.
        self.tipler = {}

    def create_option(self, name, value, *args, **kwargs):
        secenek = super().create_option(name, value, *args, **kwargs)
        # Boş seçenek ("— seçilmedi —") tipsiz kalır ve her amaçta görünür.
        secenek['attrs']['data-tip'] = self.tipler.get(str(value), '')
        return secenek


class IsOrtagiSecici(forms.Select):
    """Karşı taraf `<option>`'larına `data-roller` basar.

    `LokasyonSecici` ile aynı desen ve aynı gerekçe: satış sevkiyatında yalnız
    müşteri, satın alma kabulünde yalnız tedarikçi rollü ortak geçerli
    (migration 008) ve iadeler de aynı zorunluluğa bağlandı (migration 011).
    Rol bilgisi seçenekte durmazsa JS listeyi amaca göre süzemez, kullanıcı da
    reddi ancak POST'tan sonra görür.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # is_ortagi_id -> "MUSTERI,TEDARIKCI" gibi virgülle ayrılmış rol listesi.
        self.roller = {}

    def create_option(self, name, value, *args, **kwargs):
        secenek = super().create_option(name, value, *args, **kwargs)
        secenek['attrs']['data-roller'] = self.roller.get(str(value), '')
        return secenek


class FasonIsEmriSecici(forms.Select):
    """İş emri `<option>`'larına fason lokasyonunu ve hedef SKU'yu basar.

    Bu üçünün uyumunu `stok_islemi_kaydet()` zaten zorunlu tutuyor: fason sevkin
    hedefi, dönüşün kaynağı ve firenin kaynağı iş emrindeki fason lokasyonu olmak
    ZORUNDA, dönüşte oluşan SKU da iş emrindeki hedef SKU. Kullanıcının bunları elle
    seçmesi, yanlış seçildiğinde POST'tan sonra reddedilen bir kayıt demekti;
    öznitelikler seçimi otomatik doldurup kilitlemek için.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # fason_is_emri_id -> {'lokasyon': '10', 'hedef_sku': '1001013-V02'}
        self.emirler = {}

    def create_option(self, name, value, *args, **kwargs):
        secenek = super().create_option(name, value, *args, **kwargs)
        emir = self.emirler.get(str(value))
        if emir:
            secenek['attrs']['data-fason-lokasyon'] = emir['lokasyon']
            secenek['attrs']['data-hedef-sku'] = emir['hedef_sku']
        return secenek


# Lokasyon açılır listelerinin görünüm gruplaması. Şemada TEK bir `tip` kolonu var
# (`DAHILI` / `FASON` / `NUMUNE`) ve bu kod DEĞİŞMİYOR; müşteri ve tedarikçi de
# lokasyon değil, `is_ortaklari` satırı. Buradaki tek şey etiket: fason atölyesi
# fiziksel olarak tesis dışında olduğu için ayrı grupta ve açıkça "Dış atölye"
# diye yazıyor, dahili raflarla numune rafları da kendi gruplarında.
LOKASYON_GRUP_ETIKETLERI = [
    ('DAHILI', 'Dahili'),
    ('NUMUNE', 'Numune'),
    ('FASON', 'Dış atölye (fason)'),
]


def lokasyonlari_grupla(lokasyonlar):
    """LokasyonDetay listesini `[(grup_etiketi, [lokasyon, ...]), ...]`e böler.

    Boş grup DÖNMEZ. Bu bugün teorik bir incelik değil: canlı veritabanında henüz
    hiç `NUMUNE` lokasyonu yok (bkz. YAPILACAKLAR madde 4), yani "Numune" grubu
    gerçekten boş kalıyor. Tip destekleniyor, eksik olan yalnız veri.

    Nesneleri döndürüyor (id/ad çifti değil) çünkü hareket geçmişi filtresi
    seçeneğin `aktif_mi`'sini de basıyor ("(pasif)" eki).
    """
    gruplar = []
    for tip, etiket in LOKASYON_GRUP_ETIKETLERI:
        uyanlar = [l for l in lokasyonlar if l.tip == tip]
        if uyanlar:
            gruplar.append((etiket, uyanlar))
    return gruplar


def lokasyon_gruplu_secenekler(lokasyonlar):
    """`lokasyonlari_grupla`'nın form `choices` biçimi: `<optgroup>`'lu seçenekler."""
    return [
        (etiket, [(l.lokasyon_id, l.tam_ad) for l in uyanlar])
        for etiket, uyanlar in lokasyonlari_grupla(lokasyonlar)
    ]


class StokIslemFormu(forms.Form):
    """Tek stok merkezi: kullanıcı teknik hareketi değil iş amacını seçer."""

    amac = forms.ChoiceField(label='Ne yapıyorsunuz?', choices=stok_servisi.ISLEM_AMACLARI)
    sku_kodu = forms.CharField(label='Ürün veya SKU kodu', max_length=100)
    # Elle yazılan alan olmaktan ÇIKTI: iş emri seçilince kutu o emrin hedef
    # SKU'suyla dolup salt-okunur oluyor. `stok_islemi_kaydet()` fason dönüşünün
    # çıktısını zaten iş emrindeki hedef SKU ile karşılaştırıp reddediyordu; elle
    # yazma yalnızca o reddi POST'a kadar erteliyordu.
    hedef_sku_kodu = forms.CharField(
        label='Dönüşte oluşan SKU', max_length=100, required=False,
        help_text='İş emri seçilince otomatik dolar; iş emrindeki dönecek SKU’dur.',
    )
    miktar = forms.IntegerField(label='Miktar', min_value=0)
    # Fason dönüşünde fasoncunun bildirdiği fire, sağlam miktarla AYNI formda
    # giriliyor. Ayrı bir "Fason fire kaydı" ekranı hâlâ var ve tamamı fire olan
    # teslimatın yeri orası; buradaki alan ikisi birlikte geldiğinde personeli aynı
    # iş emri/lokasyon/parti seçimlerini iki kez doldurmaktan kurtarıyor.
    fire_miktari = forms.IntegerField(
        label='Fire miktarı', min_value=0, required=False,
        help_text='Fasoncu fire bildirdiyse doldurun; sağlam dönen miktarın dışındadır. '
                   'Boş bırakılırsa yalnız dönüş kaydedilir.',
    )
    kaynak_lokasyon_id = forms.TypedChoiceField(
        label='Kaynak lokasyon', coerce=int, choices=(), required=False, empty_value=None,
        widget=LokasyonSecici,
    )
    hedef_lokasyon_id = forms.TypedChoiceField(
        label='Hedef lokasyon', coerce=int, choices=(), required=False, empty_value=None,
        widget=LokasyonSecici,
    )
    # Etiketten "Kaynak / normal" ibaresi kalktı: alan artık gelişmiş bölümde değil
    # formun görünür kısmında, üç düğmeli bir segment olarak basılıyor ve yanında
    # başka bir durum alanı yok (dönüş durumu gelişmişte kaldı).
    stok_durumu_kodu = forms.ChoiceField(
        label='Stok durumu', choices=stok_servisi.STOK_DURUMLARI,
        initial='SERBEST',
    )
    hedef_stok_durumu_kodu = forms.ChoiceField(
        label='Dönüşte hedef stok durumu', choices=stok_servisi.STOK_DURUMLARI,
        required=False, initial='SERBEST',
    )
    is_ortagi_id = forms.TypedChoiceField(
        label='Müşteri / tedarikçi', coerce=int, choices=(), required=False, empty_value=None,
        widget=IsOrtagiSecici,
    )
    fason_is_emri_id = forms.TypedChoiceField(
        label='Fason iş emri', coerce=int, choices=(), required=False, empty_value=None,
        widget=FasonIsEmriSecici,
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
        lokasyon_tipleri = {str(l.lokasyon_id): l.tip for l in lokasyonlar}
        bos = [('', '— seçilmedi —')]
        for ad in ('kaynak_lokasyon_id', 'hedef_lokasyon_id'):
            # Gruplu seçenekler: tip artık her satırın sonunda parantez içinde değil,
            # `<optgroup>` başlığında. Boş grup basılmıyor (bkz.
            # `lokasyon_gruplu_secenekler`).
            self.fields[ad].choices = bos + lokasyon_gruplu_secenekler(lokasyonlar)
            # Süzme yalnızca sunum: hangi lokasyonun hangi amaçta geçerli olduğunun
            # otoritesi `stok_islemi_kaydet()`. Burada kopyalanan tek şey tip etiketi.
            self.fields[ad].widget.tipler = lokasyon_tipleri
        roller = {}
        for ortak_id, rol in IsOrtagiRolu.objects.using('metaks').values_list(
            'is_ortagi_id', 'rol'
        ):
            roller.setdefault(ortak_id, []).append(rol)
        self.fields['is_ortagi_id'].choices = bos + [
            (o.is_ortagi_id, f"{o.unvan} ({', '.join(roller.get(o.is_ortagi_id, []))})")
            for o in IsOrtagi.objects.using('metaks').filter(aktif_mi=True)
        ]
        self.fields['is_ortagi_id'].widget.roller = {
            str(ortak_id): ','.join(rol_listesi) for ortak_id, rol_listesi in roller.items()
        }
        emirler = list(FasonIsEmriOzet.objects.using('metaks').filter(durum='ACIK'))
        self.fields['fason_is_emri_id'].choices = bos + [
            (
                e.fason_is_emri_id,
                f'{e.emir_no} · {e.fasoncu_adi} · {e.kaynak_sku_kodu} → {e.hedef_sku_kodu}',
            )
            for e in emirler
        ]
        self.fields['fason_is_emri_id'].widget.emirler = {
            str(e.fason_is_emri_id): {
                'lokasyon': str(e.fason_lokasyon_id),
                'hedef_sku': e.hedef_sku_kodu,
            }
            for e in emirler
        }
        _girdileri_bicimlendir(self)

    def clean(self):
        veri = super().clean()
        amac = veri.get('amac')
        miktar = veri.get('miktar')
        if amac != 'SAYIM' and miktar is not None and miktar <= 0:
            self.add_error('miktar', 'Miktar sıfırdan büyük olmalıdır.')
        if (
            amac in ('SATIN_ALMA_KABUL', 'URETIM_GIRIS', 'MUSTERI_IADE')
            and not veri.get('hedef_lokasyon_id')
        ):
            self.add_error('hedef_lokasyon_id', 'Bu işlem için hedef lokasyon zorunludur.')
        if amac in ('SATIS_SEVKI', 'TEDARIKCI_IADE') and not veri.get('kaynak_lokasyon_id'):
            self.add_error('kaynak_lokasyon_id', 'Bu işlem için kaynak lokasyon zorunludur.')
        if amac == 'IC_TRANSFER':
            if not veri.get('kaynak_lokasyon_id'):
                self.add_error('kaynak_lokasyon_id', 'Transfer için kaynak zorunludur.')
            if not veri.get('hedef_lokasyon_id'):
                self.add_error('hedef_lokasyon_id', 'Transfer için hedef zorunludur.')
        if amac == 'SAYIM' and not veri.get('hedef_lokasyon_id'):
            self.add_error('hedef_lokasyon_id', 'Sayımın yapıldığı lokasyon zorunludur.')
        # Karşı taraf zorunluluğu: migration 008 (alış/satış) ve 011 (iadeler)
        # kontrollerinin aynası. ROLÜN doğruluğunu veritabanı denetliyor; burada
        # yalnız alanın boş bırakılması yakalanıyor ki kullanıcı POST'a gitmeden
        # görsün. Tablo: stok_servisi.AMAC_KARSI_TARAF.
        if amac in stok_servisi.AMAC_KARSI_TARAF and not veri.get('is_ortagi_id'):
            etiket = stok_servisi.AMAC_KARSI_TARAF[amac]['etiket']
            self.add_error('is_ortagi_id', f'{etiket} seçimi zorunludur.')
        if amac in ('FASON_SEVK', 'FASON_DONUS', 'FIRE') and not veri.get('fason_is_emri_id'):
            self.add_error('fason_is_emri_id', 'Fason iş emri zorunludur.')
        if amac in ('FASON_SEVK', 'FASON_DONUS'):
            if not veri.get('kaynak_lokasyon_id'):
                self.add_error('kaynak_lokasyon_id', 'Fason hareketinde kaynak zorunludur.')
            if not veri.get('hedef_lokasyon_id'):
                self.add_error('hedef_lokasyon_id', 'Fason hareketinde hedef zorunludur.')
        # Fire alanı yalnız fason dönüşünde anlamlı. JS onu diğer amaçlarda gizliyor
        # ama TEMİZLEMİYOR (aynı tuzak `UrunFormu.clean`'de de var): kullanıcı önce
        # dönüş seçip fire yazsa, sonra amacı değiştirse gizli değer yine POST edilir.
        veri['fire_miktari'] = veri.get('fire_miktari') if amac == 'FASON_DONUS' else None
        if veri['fire_miktari'] and not veri.get('kaynak_lokasyon_id'):
            self.add_error('kaynak_lokasyon_id', 'Fire, malın bulunduğu fason lokasyonundan düşülür.')
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
    """Yeni SKU: hangi niteliklerin VAR olduğu önce sorulur, ayrıntı sonra.

    Migration 010 SKU kimliğini yedi niteliğe çıkardı (kaplama, boya rengi, mine
    rengi, montaj hali, lak, vernik, işçilik). Hepsini yan yana yedi açılır liste
    olarak sormak, çoğu SKU'da altısı boş bırakılan bir form üretiyordu. Onay
    kutuları yalnız KAPI: işaretlenmezse ilgili ayrıntı hiç gösterilmiyor ve
    veritabanına NULL gidiyor.

    Boya ve mine rengi ikili niteliğe İNDİRİLMEDİ (010'un kararı): kutucuk yalnız
    kapı, işaretlenince renk sorulur ve renk `renkler` tablosuna bakan kontrollü
    referans olarak kalır.
    """

    urun_kodu = forms.CharField(label='Ürün kodu', max_length=100)

    kaplama_var_mi = forms.BooleanField(
        label='Kaplama var mı?', required=False,
        help_text='İşaretlenmezse kalem kaplanmamış sayılır (kaplama boş kaydedilir).',
    )
    kaplama_id = forms.TypedChoiceField(
        label='Kaplama', coerce=int, choices=(), required=False, empty_value=None,
    )

    # ChoiceField DEĞİL, `Select` widget'lı CharField. Sebebi ölçüldü: kutucuk
    # kaldırıldığında gizli kalan eski renk yine POST ediliyor ve ChoiceField onu
    # `clean()` çalışmadan ÖNCE reddediyordu — kullanıcı göremediği bir alanda
    # "Geçerli bir seçenek seçin" hatası alıyordu. Değer zaten renk ADI ve
    # `stok_kalemi_kaydet()` tabloda olmayan rengi kendisi açıyor ("listede yok"
    # kutusunun yaptığı da bu), yani katı üyelik denetiminin koruduğu bir şey yok.
    boya_var_mi = forms.BooleanField(label='Boya var mı?', required=False)
    boya_renk = forms.CharField(
        label='Boya rengi', required=False, widget=forms.Select(choices=()),
    )
    boya_renk_yeni = forms.CharField(
        label='Listede yoksa yeni boya rengi', max_length=100, required=False,
        help_text='Doldurulursa yukarıdaki seçim yok sayılır; renk listeye eklenir.',
    )

    mine_var_mi = forms.BooleanField(label='Mine var mı?', required=False)
    mine_renk = forms.CharField(
        label='Mine rengi', required=False, widget=forms.Select(choices=()),
    )
    mine_renk_yeni = forms.CharField(
        label='Listede yoksa yeni mine rengi', max_length=100, required=False,
        help_text='Doldurulursa yukarıdaki seçim yok sayılır; renk listeye eklenir.',
    )

    lak_mi = forms.BooleanField(label='Lak var mı?', required=False)
    vernik_mi = forms.BooleanField(label='Vernik var mı?', required=False)
    iscilik_mi = forms.BooleanField(label='İşçilik var mı?', required=False)

    montaj_durumu = forms.ChoiceField(
        label='Montaj hali', choices=stok_servisi.MONTAJ_DURUMLARI, initial='DEMONTE',
    )

    # "Renk belirsiz": kutucuk işaretli ama renk bilinmiyor. Veritabanına NULL
    # gider — yani tekillik anahtarında "boyasız" SKU'dan AYRILMAZ, çünkü şemada
    # ayrı bir `boya_var_mi` kolonu yok (010 boya/mineyi bilerek ikiliye indirmedi).
    # Yardım metni bunu kullanıcıya söylüyor; sessiz bırakmak yanıltıcı olurdu.
    RENK_BELIRSIZ = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Migration 010 `kaplamalar`'daki "ham" satırını pasife aldı; bu liste zaten
        # yalnız `aktif_mi=True` okuduğu için satır kendiliğinden düşüyor.
        self.fields['kaplama_id'].choices = [
            ('', '— kaplama belirsiz —'), *stok_servisi.kaplama_secenekleri()
        ]
        renkler = stok_servisi.renk_secenekleri()
        for ad in ('boya_renk', 'mine_renk'):
            self.fields[ad].widget.choices = [
                (self.RENK_BELIRSIZ, '— renk belirsiz —'), *renkler
            ]
        _girdileri_bicimlendir(self)

    def _renk_coz(self, veri, kutucuk, secim_alani, yeni_alani):
        """Bir renk kapısını tek metne indirir; kapı kapalıysa None.

        JS gizler ama TEMİZLEMEZ (aynı tuzak `UrunFormu.clean` ve
        `StokIslemFormu.clean` içinde de var): kullanıcı önce "Boya var" deyip renk
        seçse, sonra kutucuğu kaldırsa, gizli kalan değer yine POST edilir. Burada
        temizlenmezse SKU sessizce boyalı kaydedilir ve tekillik anahtarı yanlış
        satıra düşer.
        """
        if not veri.get(kutucuk):
            veri[secim_alani] = ''
            veri[yeni_alani] = ''
            return None
        yeni = (veri.get(yeni_alani) or '').strip()
        if yeni:
            return yeni
        return (veri.get(secim_alani) or '').strip() or None

    def clean(self):
        veri = super().clean()
        veri['boya_renk_cozulen'] = self._renk_coz(
            veri, 'boya_var_mi', 'boya_renk', 'boya_renk_yeni'
        )
        veri['mine_renk_cozulen'] = self._renk_coz(
            veri, 'mine_var_mi', 'mine_renk', 'mine_renk_yeni'
        )
        if not veri.get('kaplama_var_mi'):
            veri['kaplama_id'] = None
        return veri

    def servis_parametreleri(self):
        """`stok_servisi.stok_kalemi_kaydet()`'in beklediği tam parametre kümesi.

        View `**form.cleaned_data` geçemez: formda artık servise ait olmayan kapı
        alanları (kutucuklar, "listede yok" kutuları) da var.
        """
        veri = self.cleaned_data
        return {
            'urun_kodu': veri['urun_kodu'],
            'kaplama_id': veri.get('kaplama_id'),
            'boya_renk': veri.get('boya_renk_cozulen'),
            'mine_renk': veri.get('mine_renk_cozulen'),
            'montaj_durumu': veri['montaj_durumu'],
            'lak_mi': bool(veri.get('lak_mi')),
            'vernik_mi': bool(veri.get('vernik_mi')),
            'iscilik_mi': bool(veri.get('iscilik_mi')),
        }


# Fason işlem kutucuğu -> (`fason_is_emirleri.islem_turu`, okunur ad).
# Kolon TEK değerli: tek işlem seçildiyse onun türü, birden fazlaysa 'DIGER'
# (alt tablo AÇILMADI). Lak, vernik ve işçiliğin kolonda karşılığı yok, onlar da
# 'DIGER'e düşüyor. Ayrıntı `aciklama`'ya yazılıyor, yani bilgi kaybolmuyor.
FASON_ISLEM_ESLESMESI = {
    'kaplama_yapilacak': ('KAPLAMA', 'kaplama'),
    'boya_yapilacak': ('BOYA', 'boya'),
    'mine_yapilacak': ('MINE', 'mine'),
    'montaj_yapilacak': ('MONTAJ', 'montaj'),
    'lak_yapilacak': ('DIGER', 'lak'),
    'vernik_yapilacak': ('DIGER', 'vernik'),
    'iscilik_yapilacak': ('DIGER', 'işçilik'),
}


def fason_islem_turu(secilen_alanlar):
    turler = {FASON_ISLEM_ESLESMESI[a][0] for a in secilen_alanlar}
    return turler.pop() if len(turler) == 1 else 'DIGER'


def fason_islem_ozeti(secilen_alanlar):
    """İşlem listesinin okunur özeti; iş emrinin `aciklama`'sına ekleniyor."""
    return ', '.join(FASON_ISLEM_ESLESMESI[a][1] for a in secilen_alanlar)


def fasoncu_lokasyon_haritasi():
    """{is_ortagi_id: [(lokasyon_id, tam_ad), ...]} — fasoncu başına aktif atölyeler.

    İki ayrı kaynaktan geliyor çünkü `v_lokasyonlar_detay` `is_ortagi_id` taşımıyor:
    yaprak/aktif/tip bilgisi view'dan, fasoncu bağı ham `lokasyonlar`'dan. İki toplu
    sorgu; eşleştirme Python'da (cross-DB JOIN yok, fasoncu başına sorgu yok).
    """
    ortak_bagi = dict(
        Lokasyon.objects.using('metaks')
        .filter(tip='FASON', is_ortagi_id__isnull=False)
        .values_list('lokasyon_id', 'is_ortagi_id')
    )
    harita = {}
    for l in LokasyonDetay.objects.using('metaks').filter(
        aktif_mi=True, yaprak_mi=True, tip='FASON'
    ):
        ortak_id = ortak_bagi.get(l.lokasyon_id)
        if ortak_id:
            harita.setdefault(ortak_id, []).append((l.lokasyon_id, l.tam_ad))
    return harita


def fasoncu_lokasyonlari(is_ortagi_id):
    """Bir fasoncunun aktif yaprak fason lokasyonları; yoksa boş liste."""
    if not is_ortagi_id:
        return []
    return fasoncu_lokasyon_haritasi().get(is_ortagi_id, [])


class FasonIsEmriFormu(forms.Form):
    """Fason iş emri: depocu YAPILACAK İŞİ girer, dönecek SKU'yu sistem türetir.

    Önceden "Dönecek SKU" elle yazılan bir kutuydu. Depocunun bilmesi gereken şey
    fasoncuya ne yaptıracağı; dönen malın SKU kodunu elle üretmesi hem bir kod
    ezberi hem de sessiz bir hata kaynağıydı — yanlış SKU yazıldığında iş emri
    kabul ediliyor, hata ancak fason dönüşünde ortaya çıkıyordu.

    Şimdi: kaynak SKU'nun niteliklerine seçilen işlemler delta olarak uygulanıyor,
    `stok_kalemi_kaydet()` ile bul-veya-oluştur yapılıyor ve dönen id iş emrinin
    hedef SKU'su oluyor (bkz. `stok_yonetimi.fason_is_emri_yeni`).
    """

    is_ortagi_id = forms.TypedChoiceField(
        label='Fasoncu', coerce=int, choices=(), empty_value=None,
    )
    # Normalde GİZLİ: bir fasoncunun tek atölyesi var ve o otomatik seçiliyor.
    # Şema birden fazlasına izin verdiği için alan duruyor ve o durumda görünür
    # oluyor — kod "tek lokasyon" varsayımını sessizce yapmıyor.
    fason_lokasyon_id = forms.TypedChoiceField(
        label='Fason lokasyonu (atölye)', coerce=int, choices=(), required=False,
        empty_value=None,
        help_text='Fasoncunun birden fazla atölyesi varsa seçin.',
    )
    kaynak_sku_kodu = forms.CharField(label='Gönderilecek SKU', max_length=100)

    # ---- Yapılacak işlemler (dönecek SKU bunlardan türetiliyor) ----
    kaplama_yapilacak = forms.BooleanField(label='Kaplama yapılacak', required=False)
    yeni_kaplama_id = forms.TypedChoiceField(
        label='Hangi kaplama', coerce=int, choices=(), required=False, empty_value=None,
    )
    boya_yapilacak = forms.BooleanField(label='Boya yapılacak', required=False)
    yeni_boya_renk = forms.CharField(
        label='Boya rengi', required=False, widget=forms.Select(choices=()),
    )
    mine_yapilacak = forms.BooleanField(label='Mine yapılacak', required=False)
    yeni_mine_renk = forms.CharField(
        label='Mine rengi', required=False, widget=forms.Select(choices=()),
    )
    montaj_yapilacak = forms.BooleanField(label='Montaj işlemi yapılacak', required=False)
    yeni_montaj_durumu = forms.ChoiceField(
        label='Dönüşteki montaj hali', choices=(), required=False,
    )
    lak_yapilacak = forms.BooleanField(label='Lak yapılacak', required=False)
    vernik_yapilacak = forms.BooleanField(label='Vernik yapılacak', required=False)
    iscilik_yapilacak = forms.BooleanField(label='İşçilik yapılacak', required=False)

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

    ISLEM_TURU_ESLESMESI = FASON_ISLEM_ESLESMESI

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
        self.fields['fason_lokasyon_id'].choices = [('', '— otomatik —')] + [
            (l.lokasyon_id, l.tam_ad)
            for l in LokasyonDetay.objects.using('metaks').filter(
                aktif_mi=True, yaprak_mi=True, tip='FASON'
            )
        ]
        self.fields['yeni_kaplama_id'].choices = [
            ('', '— seçilmedi —'), *stok_servisi.kaplama_secenekleri()
        ]
        renkler = stok_servisi.renk_secenekleri()
        for ad in ('yeni_boya_renk', 'yeni_mine_renk'):
            self.fields[ad].widget.choices = [('', '— renk belirsiz —'), *renkler]
        self.fields['yeni_montaj_durumu'].choices = [
            ('', '— değişmiyor —'), *stok_servisi.MONTAJ_DURUMLARI
        ]
        _girdileri_bicimlendir(self)

    def secilen_islemler(self):
        """İşaretlenen işlem kutucuklarının alan adları."""
        return [
            alan for alan in FASON_ISLEM_ESLESMESI if self.cleaned_data.get(alan)
        ]

    def islem_turu(self):
        return fason_islem_turu(self.secilen_islemler())

    def islem_ozeti(self):
        return fason_islem_ozeti(self.secilen_islemler())

    def clean(self):
        veri = super().clean()

        # Fason lokasyonu: tek atölyede otomatik, birden fazlada zorunlu, hiç
        # yoksa anlaşılır hata. "Tek lokasyon" sessizce varsayılmıyor.
        lokasyonlar = fasoncu_lokasyonlari(veri.get('is_ortagi_id'))
        self.fasoncu_lokasyonlari = lokasyonlar
        if veri.get('is_ortagi_id'):
            if not lokasyonlar:
                self.add_error(
                    'is_ortagi_id',
                    'Bu fasoncunun aktif bir atölye lokasyonu yok. Önce '
                    '/yonetim/lokasyonlar/ üzerinden fasoncuya bağlı bir FASON '
                    'lokasyonu açın.',
                )
            elif len(lokasyonlar) == 1:
                veri['fason_lokasyon_id'] = lokasyonlar[0][0]
            elif not veri.get('fason_lokasyon_id'):
                self.add_error(
                    'fason_lokasyon_id',
                    'Bu fasoncunun birden fazla atölyesi var; hangisine '
                    'gönderildiğini seçin.',
                )
            elif veri['fason_lokasyon_id'] not in {lok_id for lok_id, _ in lokasyonlar}:
                self.add_error(
                    'fason_lokasyon_id', 'Seçilen atölye bu fasoncuya bağlı değil.'
                )

        # JS gizler ama TEMİZLEMEZ (aynı tuzak diğer formlarda da var).
        if not veri.get('kaplama_yapilacak'):
            veri['yeni_kaplama_id'] = None
        if not veri.get('boya_yapilacak'):
            veri['yeni_boya_renk'] = ''
        if not veri.get('mine_yapilacak'):
            veri['yeni_mine_renk'] = ''
        if not veri.get('montaj_yapilacak'):
            veri['yeni_montaj_durumu'] = ''

        if veri.get('montaj_yapilacak') and not veri.get('yeni_montaj_durumu'):
            self.add_error(
                'yeni_montaj_durumu', 'Montaj işleminde dönüşteki hal seçilmelidir.'
            )
        if veri.get('kaplama_yapilacak') and not veri.get('yeni_kaplama_id'):
            self.add_error('yeni_kaplama_id', 'Kaplama işleminde hangi kaplama olduğu seçilmelidir.')

        # Hiçbir nitelik değişmiyorsa iş emri anlamsız: dönecek SKU kaynağın
        # aynısı olurdu ve fasoncuya "hiçbir şey yapma" denmiş olurdu.
        if not self.secilen_islemler():
            self.add_error(None, 'En az bir işlem seçilmelidir; dönecek SKU bundan türetiliyor.')
        return veri


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
