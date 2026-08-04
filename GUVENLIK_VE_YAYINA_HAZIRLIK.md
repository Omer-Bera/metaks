# Güvenlik, yayın öncesi işler ve geliştirme verisi

Bu dosya, geliştirme sırasında bilinçli olarak ertelenen güvenlik işlerini ve
proje gerçek kullanıma açılmadan önce tamamlanması gereken kontrolleri izler.
Buradaki maddelerin ertelenmiş olması, servisin genel internete açılabileceği
anlamına gelmez. Geliştirme erişimi yalnızca Tailscale/Headscale ağı içindedir.

## Geliştirme dönemi veritabanı kararı

### Pi kurulum durumu (2026-08-04)

- Raspberry Pi Tailscale adı `rpi`, IPv4 adresi `100.64.0.7`.
- `depo-postgres`, `depo-gorsel-sunucu` ve `metaks-web.service` açılışta başlar.
- PostgreSQL `100.64.0.7:5433`, görseller `100.64.0.7:8083`, Django ise
  `http://100.64.0.7:8000` üzerinden tailnet'e sunulur.
- Docker Compose cihaz adresini gitignored `veritabani/.env` içindeki
  `TAILSCALE_BIND_ADDRESS` değişkeninden alır.
- Pi şu anda microSD kullanıyor. Geliştirme kopyası için kabul edildi; gerçek
  kullanım öncesinde NVMe SSD ve mümkünse UPS'e geçiş hâlâ zorunlu listededir.

Başka bir Tailscale cihazında yerel Django çalıştırılacaksa `web/.env` içinde:

```env
WEB_DB_HOST=100.64.0.7
METAKS_DB_HOST=100.64.0.7
GORSEL_SUNUCU_BASE_URL=http://100.64.0.7:8083/urun-gorselleri/
```

Portlar `5433` olarak kalır. Veritabanı parolaları Git'e yazılmaz; Pi'deki
`web/.env` dosyasından yetkili cihaza güvenli kanalla aktarılır.

Raspberry Pi 5 sürekli açık ve Tailscale ağına bağlı olduğu için geliştirme
döneminde PostgreSQL kopyasının ve ürün görsellerinin merkezi saklama/önizleme
noktasıdır.

- Pi'deki veri **üretim verisi değildir**; geliştirme anlık görüntüsüdür.
- PostgreSQL dosya dizini (`pg_data`) cihazlar arasında rsync/Syncthing ile
  kopyalanmaz. Çalışan PostgreSQL'in dosyalarını eşitlemek bozuk veya tutarsız
  kopya üretebilir.
- Aktarım `pg_dump -Fc` ile alınan iki dump üzerinden yapılır:
  `depo_sistemi` ve `metaks_web`.
- Ürün görselleri dosya olarak `rsync` ile aktarılabilir. Kaynakta silinen bir
  dosyayı Pi'den otomatik silen `--delete` seçeneği kullanılmaz.
- Aynı anda birden fazla cihazın ayrı veritabanlarında değişiklik yapıp bunları
  birleştirmesi desteklenmez. PostgreSQL dump'ları çift yönlü senkronizasyon
  aracı değildir.
- Her çalışma döneminde bir cihaz **kaynak** seçilir. O cihazdan alınan yeni
  snapshot Pi'deki eski geliştirme kopyasının yerini alır.
- Pi'deki önizleme ortamı tercihen salt-okunur kullanılır. Yazma testi gerekiyorsa
  verinin geçici olduğu ve bir sonraki geri yüklemede kaybolacağı kabul edilir.

### Önerilen akış

1. Kaynak geliştirici, mevcut
   `veritabani/scripts/maintenance/yedek_al.sh` betiğiyle iki veritabanının
   snapshot'ını ve görselleri hazırlar.
2. Dump dosyaları ve görseller Tailscale üzerinden Pi'ye aktarılır.
3. Pi'de dump'lar ayrı geliştirme veritabanlarına geri yüklenir; geri yüklemeden
   önce Pi'deki önceki dump ayrıca saklanır.
4. Diğer cihazlar önizleme için Pi'deki Django uygulamasını kullanır. Yerel bir
   kopya gerektiğinde Pi'deki en son dump indirilip yerel PostgreSQL'e geri
   yüklenir.
5. Yerelde oluşan değişiklik Pi'ye otomatik geri yazılmaz. Yeni otorite olacak
   cihaz açıkça seçilir ve yeni snapshot alınır.

Bu aşamada Pi, gerçek bir yedeğin yerini tek başına tutmaz. Pi'deki veritabanı
kopyası ile en az bir tarih damgalı dump ayrı şeylerdir; önemli veriler ayrıca
başka bir fiziksel diskte saklanmalıdır. Pi için microSD yerine NVMe SSD ve
mümkünse UPS kullanılmalıdır.

## Yayın öncesi zorunlu güvenlik listesi

### Kritik — gerçek kullanıcı/veri öncesi

- [ ] `veritabani/docker-compose.yml` içindeki sabit PostgreSQL parolasını kaldır;
  gitignored `.env` veya Docker secret kullan.
- [ ] Depoda geçmişte görünen tüm PostgreSQL parolalarını değiştir. Yalnızca
  dosyadan kaldırmak yeterli değildir.
- [ ] Geliştirme varsayılanı olan Django `SECRET_KEY` değerini kaldır; üretimde
  uzun ve rastgele bir sır zorunlu olsun.
- [ ] Üretimde `DJANGO_DEBUG=false` yap ve ayar eksikliğinde uygulamanın güvenli
  şekilde açılmamasını sağla.
- [ ] `DJANGO_ALLOWED_HOSTS` değerini yalnızca gerçek Tailscale/DNS adlarıyla
  sınırla; joker (`*`) kullanma.
- [ ] Django geliştirme sunucusu yerine Gunicorn/Uvicorn benzeri bir uygulama
  sunucusu ve ters proxy kullan.
- [ ] Kimlik bilgileri taşındığı için HTTPS kur. Tailscale Serve veya ters proxy
  TLS kullanılabilir; HTTPS sonrası `CSRF_TRUSTED_ORIGINS`, güvenli çerezler ve
  proxy başlıklarını doğrula.
- [ ] PostgreSQL `5433`, görsel sunucusu `8083` ve web portunu genel internete
  açma; modem port yönlendirmesi yapma. Servisleri yalnız Tailscale arayüzüne
  bağla veya host güvenlik duvarıyla sınırla.
- [ ] Tailscale ACL/grant kurallarıyla yalnız yetkili cihaz ve kullanıcıların
  Pi'ye erişmesini sağla; gerekmeyen cihazların PostgreSQL'e doğrudan erişimini
  kapat.

### Yetki ve uygulama güvenliği

- [ ] Katalog ve stok ekranlarının anonim erişime açık kalıp kalmayacağına karar
  ver; gerçek şirket verisi varsa giriş zorunluluğunu değerlendir.
- [ ] Depo personeli, yönetici ve fason kullanıcı rollerini ayır. Şu anda giriş
  yapan kullanıcıların stok işlemi yetkileri yeterince ince ayrılmıyor.
- [ ] Uygulamanın ortak `depo_admin` yerine en az yetkili veritabanı rolleriyle
  bağlanmasını sağla; okuma ve kontrollü fonksiyon çağrısı izinlerini ayır.
- [ ] Yönetici hesaplarında güçlü parola ve mümkünse Tailscale kimlik
  sağlayıcısında MFA zorunlu olsun.
- [ ] Oturum, CSRF, dosya yükleme, içerik türü/boyut sınırları ve güvenlik
  başlıklarını üretim ayarlarıyla test et.
- [ ] Django `manage.py check --deploy` çıktısını temizle.

### Yedekleme ve işletim

- [ ] `depo_sistemi`, `metaks_web` ve ürün görselleri için otomatik günlük yedek
  zamanlaması kur.
- [ ] En az bir yedeği Pi'den farklı fiziksel cihazda ve tercihen şifreli tut.
- [ ] Saklama süresi belirle; günlük/haftalık/aylık kopyaları yalnızca son 14
  güne bağlı kalmadan planla.
- [ ] Geri yüklemeyi boş bir ortamda düzenli test et. Alınmış fakat geri
  yüklenmesi denenmemiş dump doğrulanmış yedek sayılmaz.
- [ ] PostgreSQL, Django ve ters proxy loglarını; disk doluluğunu, servis
  sağlığını ve yedek başarısızlıklarını izle.
- [ ] Pi için NVMe sağlık kontrolü, UPS kapanma prosedürü ve işletim sistemi
  güvenlik güncellemelerini planla.

## Yayına çıkış kapısı

Gerçek şirket verisi veya gerçek kullanıcı hesapları sisteme alınmadan önce bu
dosyadaki kritik maddeler tamamlanmalı; ardından ayrı bir yayın kontrolünde en az
şunlar doğrulanmalıdır:

```text
DEBUG kapalı
HTTPS açık
varsayılan/sabit sır yok
portlar yalnız tailnet'te
ACL en az yetkiyle sınırlı
otomatik yedek başarılı
geri yükleme testi başarılı
manage.py check --deploy temiz
```

