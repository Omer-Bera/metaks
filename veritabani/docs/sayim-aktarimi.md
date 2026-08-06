# Depo sayımının aktarımı — çalışma notu (2026-08-06)

Kaynak: `sayım/DEPO-SAYIM-kopyası.xlsx`, **`DEPOSTOK`** sayfası. 240 MB'lık dosyanın
büyüklüğü gömülü fotoğraflardan geliyor; veri kısmı 279 satır.

Bu belge aktarım bitene kadar yaşayan bir not: alınan kararlar, bilinen kirlilikler ve
bilerek ertelenen satırlar burada. Şema/sözleşme kararları buradan
[`stok-urun-veri-sozlesmesi.md`](stok-urun-veri-sozlesmesi.md)'ye taşınır.

## Kaynağın doğrulanmış künyesi

Aşağıdaki sayılar iki bağımsız okumayla teyit edildi (openpyxl veri okuması +
`xl/drawings/drawing1.xml` çizim katmanı):

| Ölçüt | Değer |
| --- | ---: |
| Veri satırı (sayfa satırı 3–281) | 279 |
| Tekil ürün adı | 221 |
| `STOK KODU` dolu satır | 121 (değerler 1–193, 120 tekil) |
| `ÜRÜN GRUBU` boş satır | 156 |
| Farklı `KONUMU` yazımı | 52 |
| Görsel anchor'ı / görselli satır / tekil görsel dosyası | 297 / 230 / 208 |

**Excel'deki `STOK KODU` bir ürün kodu değildir.** Sayım sırasında verilmiş sıra
numarasıdır; 158 satırda hiç yok, aynı ürün birden çok numara almış (satır 3–7'nin
beşi de aynı PARİS KANCA'dır). Veritabanına **asla** bu numarayla girilmez.

## Alınan kararlar

1. **Miktar tartımdan türetilmiştir, sayılmamıştır.** 279 satırın 278'inde
   `MİKTAR = TONAJ × 1000 ÷ GRAMAJ`; 179 satır kesirli çıkıyor. `stok_hareketleri.miktar`
   INTEGER olduğu için **yuvarlanmış değerle** ilerliyoruz. Her hareketin açıklamasına
   tonaj, gramaj ve adedin bunlardan hesaplandığı notu düşülür, ör:
   `SAYIM 2026-08 — 29,55 kg / 3,76 gr → 7.859 adet (tartımdan hesaplandı)`.
2. **"HAM" iki alana birden çevrilir**: `kaplama_id IS NULL` ve montaj hali
   `DEMONTE` (tek parça üründe `MONTE`). Gerekçe sözleşmede.
3. **Hammadde**: `hammaddeler` tablosunda karşılığı olmayan ve birden çok metal
   içeren satırlar `KARIŞIK` olarak açılır, proje sonunda tek tek düzeltilir.
   Kapsam: `DEMİR + ZAMAK` (9 satır), `PİRİNÇ + ZAMAK` (4). `BAKIR` (2) ve
   `PASLANMAZ` (1) tek hammaddedir; bunlar `KARIŞIK` değil kendi satırlarıyla açılır.
4. **Raf adları normalize edilir**: `Metaks` altında `<dolap>-<raf>` biçiminde yaprak
   lokasyon (mevcut `21-1` kaydıyla aynı biçim). `KAPLAMA DEPO` ayrı bir `DAHILI`
   yaprak lokasyondur. Ayrıntı aşağıda.

## Raf normalizasyonu

52 farklı yazım, `METAKS\s*-?\s*(\d+)\s*(?:-\s*(\d+))?` kalıbıyla **41 gerçek rafa**
iniyor. `METAKS-10-1`, `METAKS -10-1`, `METAKS - 10-1`, `METAKS 10-1` hepsi `10-1`.

```
9      10-1 10-2 11-1 11-2 11-3 11-4 11-5
12-1 12-2 12-3 12-4 12-5   13-1 13-3 13-4 13-5
14-1 14-2 14-3   15-1 15-2   18-1
19-1 19-2 19-3 19-5   20-1 20-2 20-3 20-4 20-5
21-1 21-2 21-3 21-4   22-1 22-2 22-3 22-4
+ KAPLAMA DEPO
```

`21-1` zaten var (lokasyon_id 44). Kalan 39 raf + `KAPLAMA DEPO` açılacak.
`METAKS - 9` tek satırda geçiyor ve raf numarası yok — dolap 9'un hangi rafı olduğu
sorulmalı.

## Bekletilen satırlar — veritabanına şimdilik yazılmayacak

Konumu belirsiz olduğu için ilk turda dışarıda kalanlar:

| Sayfa satırı | Ürün | Konum | Miktar |
| ---: | --- | --- | ---: |
| 154 | NO:24 DÜZ KUŞ GÖZÜ | `19050` (konum değil, sayı) | 15.000 |
| 241 | 54 SİSTEM LOGOLU DİŞİ | boş | 23.729 |
| 247 | NO : 30 PUL | boş | 3.985 |
| 248 | 15 mm OVAL KAPSÜL | boş | 1.000 |

## Tek hücrede birden çok raf yazan 14 satır

Bunlarda toplam miktar biliniyor, raflara dağılımı bilinmiyor:

| Satır | Ürün | Raflar | Miktar |
| ---: | --- | --- | ---: |
| 146 | NO : 28 KUŞ GÖZÜ | 11-2, 11-3, 12-4 | 88.000 |
| 150 | NO : 5 KUŞ GÖZÜ | 12-3, 21-3 | 235.000 |
| 176 | 10 mm ALTTAN DİKME ÇANAK | 20-2, 21-2 | 426.000 |
| 223 | 50 BOY KUPA | 21-4, 19-5 | 15.686 |
| 227 | 20 BOY KUPA | 22-4, 20-4, 19-5, 20-5 | 225.667 |
| 230 | 18 BOY KUPA | 22-4, 21-4 | 303.814 |
| 231 | 28 BOY KUPA | 21-4, 20-4, 19-5, 20-5 | 102.864 |
| 245 | 16 BOY KUPA | 22-4, 21-4 | 260.588 |
| 250 | 17 mm 54 SİSTEM KAPAK | 12-5, 18-1 | 450.000 |
| 253 | 15 mm 54 SİSTEM DİŞİ LOGOLU | 11-1, 12-1, 13-1 | 2.610.169 |
| 255 | 54 SİSTEM ERKEK (MEME) | 13-1, 20-1 | 2.560.870 |
| 264 | ALFA ÇIT ÇIT BACAK | 13-4, 13-5, 19-1 | 212.598 |
| 269 | ALFA DİŞİ PARÇA ÇIT ÇIT | 14-1, 19-3 | 250.000 |
| 273 | 10 mm 54 ERKEK | 15-1, 18-1 | 466.667 |

Karar: toplam **ilk rafa** yazılır, açıklamaya bütün raflar not düşülür, satır
"raf dağılımı doğrulanacak" işaretiyle kalır. Doğru dağılım öğrenilince defter
`IC_TRANSFER` ile düzeltilir — hareket satırı UPDATE edilemediği için tek yol budur.

## Görseller

Fotoğraflar hücreye sabitlenmemiş, **yüzüyor**. Bir görselin `from` satırı ile
gerçekte durduğu satır çoğu zaman aynı değil: 297 anchor'ın `from`'u yalnız 230 satıra
düşüyor, 57 satırda 2–4 anchor üst üste biniyor. Görselsiz görünen 49 satırın
**34'ü** aslında bir üstteki satırın anchor'ının dikey aralığı içinde — yani görseli
var, sadece bir satır yukarı bağlanmış.

Doğru eşleme kuralı: anchor'ı `from` satırına değil, **dikey orta noktasının düştüğü
satıra** yazmak (bütün satırlar 75 pt, çeviri düz hesap).

Bu düzeltmeden sonra gerçekten görselsiz kalan 15 satır — hepsi 54 sistem / çıt çıt
dökme parçaları:

| Satır | Ürün | Miktar |
| ---: | --- | ---: |
| 250 | 17 mm 54 SİSTEM KAPAK | 450.000 |
| 251 | 15 mm 54 SİSTEM KAPAK | 381.000 |
| 252 | 15 mm 54 SİSTEM PARA TİPİ KAPAK | 298.000 |
| 253 | 15 mm 54 SİSTEM DİŞİ LOGOLU | 2.610.169 |
| 254 | 15 mm 54 SİSTEM DİŞİ LOGOSUZ | 220.000 |
| 255 | 54 SİSTEM ERKEK (MEME) | 2.560.870 |
| 268 | 10 mm 54 KAPAK | 450.000 |
| 269 | ALFA DİŞİ PARÇA ÇIT ÇIT | 250.000 |
| 270 | ALFA ERKEK PARÇA | 225.000 |
| 271 | 10 MM 54 DİŞİ LOGOLU | 367.500 |
| 272 | 10 mm 54 BACAK | 550.000 |
| 273 | 10 mm 54 ERKEK | 466.667 |
| 274 | 54 PARÇA ERKEK ÇIT ÇIT | 231.304 |
| 275 | NO : 4 KISA KAPAK | 603.000 |
| 281 | 15 MM 54 SİSTEM BACAK | 2.300.000 |

Ayrıca 38 görsel dosyası birden çok satırda kullanılmış (biri 16 satırda) — aynı
ürünün farklı kutuları olduğu için beklenen durum, ama "1 satır = 1 dosya" varsayan
bir isimlendirme bunu bozar.

## Kaplama eşlemesi

**Karar (2026-08-06): `FREE NİKEL`, `FREE SARI`, `MAT FREE` birer kaplama adıdır**,
`nikelsiz_mi` diye bir nitelik açılmaz. Gerekçe: nikel insan sağlığına zararlı olduğu
için bugün **bütün yeni kaplamalar zaten nikelsiz üretiliyor** — yani "nikelsiz"
ayırt edici bir nitelik değil, neredeyse her satırda aynı değeri alırdı. Kimliğe
girmesi gereken şey, çalışanın raf başında söylediği kaplama adı.

Lak bundan bağımsız kalır: aynı ürünün hem laklısı hem laksızı olabilir, bu yüzden
010'un `lak_mi` ikilisi doğru yerdedir ve kaplama adına gömülmez.

`ÜRÜN AÇIKLAMA` kolonunun 16 değeri şöyle çevrilir:

| Excel değeri | Satır | Kaplama | `lak_mi` | Not |
| --- | ---: | --- | --- | --- |
| `HAM` | 209 | `NULL` | FALSE | + montaj `DEMONTE`/`MONTE` |
| `FREE NİKEL LAKLI` | 18 | FREE NİKEL | TRUE | yeni kaplama |
| `FREE SARI LAKLI` | 17 | FREE SARI | TRUE | yeni kaplama |
| `FREE NİKEL` | 10 | FREE NİKEL | FALSE | yeni kaplama |
| `SARI LAK` | 9 | SARI | TRUE | mevcut |
| `BAKIR` | 3 | BAKIR | FALSE | mevcut |
| `MAT FREE` | 2 | MAT FREE | FALSE | yeni kaplama |
| `ANTİK SARI` | 2 | ANTİK SARI | FALSE | mevcut |
| `OKSİT` | 2 | OKSİT | FALSE | mevcut |
| `SARI` | 2 | SARI | FALSE | mevcut (biri sonda boşluklu) |
| `MAT FREE NİKEL` | 1 | MAT FREE | FALSE | **varsayım**: `MAT FREE`'nin uzun yazımı |
| `SİYAH FREE` | 1 | SİYAH FREE | FALSE | **varsayım**: ayrı kaplama |
| `SİYAH OKSİT` | 1 | SİYAH OKSİT | FALSE | **varsayım**: `OKSİT`'ten ayrı |
| `KALAY` | 1 | KALAY | FALSE | mevcut |
| `FREE NİKEL` + `FREE SARI` | 1 | — | — | tek hücrede iki kaplama, bekletiliyor |
| `HAM` + `SARI` + `FREE NIKEL` | 1 | — | — | tek hücrede üç kaplama, bekletiliyor |

Migration 012 beş yeni kaplama satırı açar: `FREE NİKEL`, `FREE SARI`, `MAT FREE`,
`SİYAH FREE`, `SİYAH OKSİT`. Son ikisi tek satırlık kullanımdır; yukarıdaki üç varsayım
yanlışsa migration yazılmadan önce düzeltilir.

Vernik ve işçilik sayımda hiç geçmiyor. `stok_kalemi_kaydet()` üçünü de zorunlu
istediği için varsayılan duruş: **`vernik_mi = FALSE`, `iscilik_mi = FALSE`**;
istisnalar onay ekranında tek tek işaretlenir.

## Açık kararlar

- Yukarıdaki üç kaplama varsayımı (`MAT FREE NİKEL`, `SİYAH FREE`, `SİYAH OKSİT`).
- **`METAKS - 9`** hangi raf?
- Katalogda gramaj yalnız 1.433/2.973 üründe dolu; eşleştirmenin ikinci ayağı ölçü
  (`olcu_mm`, 2.973/2.973 dolu) olmak zorunda.
