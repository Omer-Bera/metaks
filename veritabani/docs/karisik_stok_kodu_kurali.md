# Karışık Stok Kodu Ailesi Kuralı

Bu kural 2026-07-28'de kullanıcı hafızasından + `data/interim/karisik_urunler.xlsx`
üzerinde ampirik doğrulama ile çıkarıldı. `scripts/normalization/karisik_urunleri_coz.py`
bu kuralı uygular.

## Yapı

Karışık (çoklu kod) hücrenin ilk kodu (`/` işaretinden önceki kısım) **gerçek bir ürün
değil, sadece gruplama/aile anahtarıdır**. Sonraki her kod ayrı, bağımsız satılabilir bir
üründür ve şu biçimdedir:

```
[1 haneli kategori hanesi][ölçü (mm, ondalıklı olabilir)]
```

Örnek: `108/109;112;617;620;015;017;023`

- `108` → aile anahtarı, DB'ye girmez.
- `109` → hane `1`, ölçü `09` → RİVET, 9 mm
- `112` → hane `1`, ölçü `12` → RİVET, 12 mm
- `617` → hane `6`, ölçü `17` → ÇAKMA DÜĞME, 17 mm
- `620` → hane `6`, ölçü `20` → ÇAKMA DÜĞME, 20 mm
- `015` → hane `0`, ölçü `15` → ALTTAN DİKME DÜĞME, 15 mm
- `017` → hane `0`, ölçü `17` → ALTTAN DİKME DÜĞME, 17 mm
- `023` → hane `0`, ölçü `23` → ALTTAN DİKME DÜĞME, 23 mm

Aynı tasarımın (aynı ön yüz kalıbı) farklı kategorilere düşmesinin sebebi, ürünün
kumaşa/deriye bağlandığı **arka parça/kalıp kısmının** değişmesi — örn. aynı görünüm
alttan dikme, üstten dikme, rivet veya çıtçıt olarak üretilebiliyor.

Aile numaraları (100, 101, 102, ...) sıralı artıyor; 999'u geçince 4 haneye çıkıyor
(örn. 1786). Bu yüzden kod uzunlukları satırdan satıra değişebiliyor.

## Hane → Kategori Haritası (ampirik olarak doğrulandı)

`data/interim/karisik_urunler.xlsx` içindeki 857 satırda, 857 satırın kendi mm
listeleriyle tek-adaylı (kesin) eşleşen ~1037 varyanttan çıkarılan dağılım:

| Hane | Kategori | Örnek sayısı | Güven |
|---|---|---|---|
| 0 | TOKA / ALTTAN DİKME DÜĞME (ikisi de bu hanede) | 285 | Yüksek |
| 1 | RİVET (çivili rivet) | 51 | Yüksek |
| 2 | RİVET | 369 | Yüksek |
| 3 | — | 1 | Çok düşük, örneklem yetersiz |
| 4 | **SABİT DÜĞME** (veri 4 örnekte karışık gösterdi; kullanıcı hafızasına güvenilerek sabitlendi) | 4 | Düşük — elle doğrulanmalı |
| 5 | — (hiç görülmedi) | 0 | — |
| 6 | ÇAKMA DÜĞME (oynar düğme) | 206 | Yüksek |
| 7 | ÇIT ÇIT | 20 | Yüksek |
| 8 | SALLANTI | 39 | Yüksek — kullanıcı "bağucu/stoper"i farklı bir kategori olarak hatırlıyor; bu veri setinde bağucu/stoper hiç gözlemlenmedi (belki hiç karışık satıra düşmemiş, belki farklı bir hane kullanıyor) |
| 9 | ÜSTTEN DİKME DÜĞME | 47 | Yüksek |

Hane 3 ve 5 için neredeyse hiç örnek yok — "kullanılmıyor" varsayımı destekleniyor.
Ondalıklı kodlar (`210.5`, `212,5`) "ara boy" ölçüleridir (örn. `210.5` → 2 hanesi
kategori, `10.5` mm ölçü).

## Bilinen sınırlamalar / elle bakılması gerekenler

Script çalıştığında `reports/excel/karisik_urun_cozme_raporu.xlsx` üretir; en son
çalıştırmada **1143/1358 (%84.2)** varyant otomatik çözüldü, **215** kayıt
`Elle_Bakilmasi_Gereken` sayfasına düştü. Sebepleri:

- **`AILE_MM_LISTESINDE_YOK`**: kodun çözülen ölçüsü, satırın kendi mm listesinde hiç
  yok. Genelde orijinal Excel'e eksik/tutarsız girilmiş satırlar.
- **`BELIRSIZ_N_ADAY`**: hane→kategori haritasıyla daraltıldıktan sonra hâlâ birden
  fazla aday kalan kodlar.
- **`TOKEN_COZULEMEDI`**: kod deseni tutmuyor (serbest metin notları gibi
  `"KUŞGÖZÜ 5 OLMALI"`, ya da tek harfli kodlar gibi `"D"`).
- **`AxB mm` (iki boyutlu) kodlar** (örn. `07x08 mm`, `916_207,5*12`) bu kurala hiç
  girmiyor — tamamen farklı bir alt-şema, ayrı ele alınmalı.
- `T`, `BT`, `E`, `-E` sonekleri: anlamı henüz netleşmedi (kullanıcı da hatırlamıyor).
  Script bu sonekleri ayırıp `SONEK` kolonuna kaydediyor ama anlamlarını yorumlamıyor.

## Çıktılar

- `data/interim/karisik_urunler_cozulmus.xlsx`: otomatik çözülen varyantlar (taslak,
  henüz `final_excel_hazirla.py` akışına eklenmedi).
- `reports/excel/karisik_urun_cozme_raporu.xlsx`: özet + otomatik çözülenler +
  elle bakılması gerekenler.
