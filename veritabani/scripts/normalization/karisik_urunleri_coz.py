"""Karışık (çoklu stok kodlu) satırları ayrı ürünlere ayırır.

Kural (2026-07-28'de doğrulandı, bkz. docs/karisik_stok_kodu_kurali.md):
Aile hücresindeki ilk kod (ör. "108/109;112;617;620;015;017;023" içindeki "108")
sadece gruplama anahtarıdır, gerçek bir ürün değildir. Sonraki her kod
[1 haneli kategori][ölçü] biçimindedir; ölçü, aynı ailenin kategori
alt-gruplarından birinin ÜRÜN DETAYI (mm) listesinde birebir bulunmalıdır.
Eşleşme bulunan alt-grubun kategori adı, aynı indeksteki Boy değeri ve diğer
alanları (açıklama, gramaj, göz sayısı, görsel) yeni satıra aktarılır.

Belirsiz (birden fazla alt-grupla eşleşen) veya hiç eşleşmeyen kodlar
(ör. "AxB mm" iki boyutlu ölçüler, "-E"/"T"/"BT" sonekli kodlar, orijinal
Excel'de eksik/tutarsız girilmiş satırlar) otomatik işlenmez; RAPOR_DOSYASI
içindeki "Elle_Bakilmasi_Gereken" sayfasına düşer.
"""

from pathlib import Path
import re
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

GIRIS_DOSYASI = BASE_DIR / "data" / "interim" / "karisik_urunler.xlsx"
CIKIS_DOSYASI = BASE_DIR / "data" / "interim" / "karisik_urunler_cozulmus.xlsx"
RAPOR_DOSYASI = BASE_DIR / "reports" / "excel" / "karisik_urun_cozme_raporu.xlsx"

STOK_KOLONU = "ÜRÜN STOK KODU"
KATEGORI_KOLONU = "ÜRÜN KATEGORİ GRUBU"
MM_KOLONU = "ÜRÜN DETAYI (mm)"
BOY_KOLONU = "ÜRÜN DETAYI (Boy)"

DEVIRALINACAK_KOLONLAR = [
    "ÜRÜN GÖRSELİ",
    "ÜRÜN GRAMI",
    "ÜRÜN GÖZ SAYISI",
    "ÜRÜN AÇIKLAMASI",
]

TOKEN_AYRAC_DESENI = re.compile(r"[/;\n]")
SONEK_DESENI = re.compile(r"[a-zA-ZçğıöşüÇĞİÖŞÜ\-]+$")
TOKEN_DESENI = re.compile(r"^(\d)(\d+(?:[.,]\d+)?)")

# Kullanıcı ile 2026-07-28'de doğrulanan, örneklem çok küçük olduğu için
# veriden çıkan baskın kategoriye güvenilmeyip hafızaya göre sabitlenen haneler.
HANE_KATEGORI_ZORLA = {
    4: "SABİT DÜĞME",
}


def token_ayikla(hucre: Any) -> list[str]:
    if pd.isna(hucre):
        return []
    s = str(hucre)
    parts = TOKEN_AYRAC_DESENI.split(s)
    return [p.strip() for p in parts if p.strip()]


def olcu_listesi_ayikla(hucre: Any) -> list[float | None]:
    """Sırayı korur (Boy listesiyle indeks eşlemesi için)."""
    if pd.isna(hucre):
        return []
    s = str(hucre).replace("\n", " ")
    parts = s.split("/")
    sonuc: list[float | None] = []
    for p in parts:
        p = p.strip().lower().replace("mm", "").replace(" ", "")
        p = SONEK_DESENI.sub("", p)
        p = p.replace(",", ".")
        try:
            sonuc.append(float(p))
        except ValueError:
            sonuc.append(None)
    return sonuc


def boy_listesi_ayikla(hucre: Any) -> list[str | None]:
    if pd.isna(hucre):
        return []
    s = str(hucre).replace("\n", " ")
    parts = s.split("/")
    return [p.strip() or None for p in parts]


def token_coz(token: str) -> tuple[int, float, str] | None:
    """Dönüş: (kategori_hanesi, olcu, sonek). Eşleşmezse None."""
    temiz = token.strip()
    sonek_m = SONEK_DESENI.search(temiz)
    sonek = sonek_m.group(0) if sonek_m and not temiz[:1].isalpha() else ""
    govde = temiz[: len(temiz) - len(sonek)] if sonek else temiz
    govde = govde.replace(",", ".")
    m = TOKEN_DESENI.match(govde)
    if not m:
        return None
    kategori_hanesi = int(m.group(1))
    try:
        olcu = float(m.group(2))
    except ValueError:
        return None
    return kategori_hanesi, olcu, sonek


def main() -> None:
    if not GIRIS_DOSYASI.exists():
        raise FileNotFoundError(f"Giriş dosyası bulunamadı: {GIRIS_DOSYASI}")

    df = pd.read_excel(GIRIS_DOSYASI)

    # Aynı stok kodu hücresini paylaşan satırları aile olarak grupla.
    aileler: dict[str, list[dict[str, Any]]] = {}
    for _, row in df.iterrows():
        kod_hucresi = row[STOK_KOLONU]
        if pd.isna(kod_hucresi):
            continue
        aileler.setdefault(str(kod_hucresi), []).append(row.to_dict())

    # Her aile için: token listesi + kategori alt-grupları (mm/boy listeleriyle).
    aile_analiz: dict[str, dict[str, Any]] = {}
    tek_kodlular: list[dict[str, Any]] = []

    for kod_hucresi, alt_gruplar in aileler.items():
        tokenler = token_ayikla(kod_hucresi)
        if len(tokenler) <= 1:
            for alt in alt_gruplar:
                tek_kodlular.append({**alt, "sebep": "TEK_KOD_KARISIK_LISTEDE"})
            continue

        alt_grup_bilgisi = []
        for alt in alt_gruplar:
            alt_grup_bilgisi.append(
                {
                    "kategori": alt.get(KATEGORI_KOLONU),
                    "mm_list": olcu_listesi_ayikla(alt.get(MM_KOLONU)),
                    "boy_list": boy_listesi_ayikla(alt.get(BOY_KOLONU)),
                    "kaynak_satir": alt,
                }
            )

        aile_analiz[kod_hucresi] = {
            "aile_no": tokenler[0],
            "tokenler": tokenler[1:],
            "alt_gruplar": alt_grup_bilgisi,
        }

    def adaylari_bul(alt_gruplar: list[dict[str, Any]], olcu: float) -> list[tuple[int, int]]:
        adaylar = []
        for idx, grup in enumerate(alt_gruplar):
            for mm_idx, mm_deger in enumerate(grup["mm_list"]):
                if mm_deger is not None and abs(mm_deger - olcu) < 1e-6:
                    adaylar.append((idx, mm_idx))
        return adaylar

    # --- 1. geçiş: tek adayı olan (kesin) eşleşmeleri çöz, hane->kategori istatistiği topla ---
    hane_kategori_sayaci: dict[int, dict[str, int]] = {}
    kesin_sonuclar: dict[str, dict[str, tuple[int, int, int]]] = {}
    belirsizler: dict[str, dict[str, tuple[int, float, str, list[tuple[int, int]]]]] = {}
    cozulemeyenler: list[dict[str, Any]] = []

    for kod_hucresi, bilgi in aile_analiz.items():
        kesin_sonuclar[kod_hucresi] = {}
        belirsiz_grup: dict[str, tuple[int, float, str, list[tuple[int, int]]]] = {}
        for token in bilgi["tokenler"]:
            coz = token_coz(token)
            if coz is None:
                cozulemeyenler.append(
                    {STOK_KOLONU: kod_hucresi, "token": token, "sebep": "TOKEN_COZULEMEDI"}
                )
                continue
            kategori_hanesi, olcu, sonek = coz
            adaylar = adaylari_bul(bilgi["alt_gruplar"], olcu)
            if len(adaylar) == 0:
                cozulemeyenler.append(
                    {
                        STOK_KOLONU: kod_hucresi,
                        "token": token,
                        "kategori_hanesi": kategori_hanesi,
                        "cozulen_olcu": olcu,
                        "sebep": "AILE_MM_LISTESINDE_YOK",
                    }
                )
            elif len(adaylar) == 1:
                grup_idx, mm_idx = adaylar[0]
                kesin_sonuclar[kod_hucresi][token] = (grup_idx, mm_idx, kategori_hanesi)
                kat_adi = str(bilgi["alt_gruplar"][grup_idx]["kategori"])
                hane_kategori_sayaci.setdefault(kategori_hanesi, {})
                hane_kategori_sayaci[kategori_hanesi][kat_adi] = (
                    hane_kategori_sayaci[kategori_hanesi].get(kat_adi, 0) + 1
                )
            else:
                belirsiz_grup[token] = (kategori_hanesi, olcu, sonek, adaylar)
        if belirsiz_grup:
            belirsizler[kod_hucresi] = belirsiz_grup

    hane_baskin_kategori = {
        hane: max(sayac.items(), key=lambda kv: kv[1])[0]
        for hane, sayac in hane_kategori_sayaci.items()
    }

    print("📊 Kesin eşleşmelerden öğrenilen hane -> baskın kategori haritası:")
    for hane in sorted(hane_baskin_kategori):
        toplam = sum(hane_kategori_sayaci[hane].values())
        print(f"   {hane}: {hane_baskin_kategori[hane]} ({hane_kategori_sayaci[hane]}, toplam {toplam})")

    # --- 2. geçiş: belirsizleri, öğrenilen hane->kategori haritasıyla çözmeyi dene ---
    for kod_hucresi, belirsiz_grup in belirsizler.items():
        bilgi = aile_analiz[kod_hucresi]
        for token, (kategori_hanesi, olcu, sonek, adaylar) in belirsiz_grup.items():
            baskin_kategori = hane_baskin_kategori.get(kategori_hanesi)
            daraltilmis = [
                a
                for a in adaylar
                if str(bilgi["alt_gruplar"][a[0]]["kategori"]) == baskin_kategori
            ]
            if baskin_kategori is not None and len(daraltilmis) == 1:
                grup_idx, mm_idx = daraltilmis[0]
                kesin_sonuclar[kod_hucresi][token] = (grup_idx, mm_idx, kategori_hanesi)
            else:
                cozulemeyenler.append(
                    {
                        STOK_KOLONU: kod_hucresi,
                        "token": token,
                        "kategori_hanesi": kategori_hanesi,
                        "cozulen_olcu": olcu,
                        "aday_sayisi": len(adaylar),
                        "sebep": f"BELIRSIZ_{len(adaylar)}_ADAY",
                    }
                )

    # --- Sonuçları üret ---
    cozulen_satirlar: list[dict[str, Any]] = []
    elle_bakilacak: list[dict[str, Any]] = [*tek_kodlular, *cozulemeyenler]
    islem_raporu: list[dict[str, Any]] = []

    for kod_hucresi, token_sonuclari in kesin_sonuclar.items():
        bilgi = aile_analiz[kod_hucresi]
        for token, (grup_idx, mm_idx, kategori_hanesi) in token_sonuclari.items():
            grup = bilgi["alt_gruplar"][grup_idx]
            olcu = grup["mm_list"][mm_idx]
            boy_list = grup["boy_list"]
            boy_degeri = boy_list[mm_idx] if mm_idx < len(boy_list) else None
            kategori_adi = HANE_KATEGORI_ZORLA.get(kategori_hanesi, grup["kategori"])

            yeni_satir = {
                STOK_KOLONU: token.replace(",", "."),
                KATEGORI_KOLONU: kategori_adi,
                MM_KOLONU: olcu,
                BOY_KOLONU: boy_degeri,
                "AILE_NO": bilgi["aile_no"],
                "KAYNAK_HUCRE": kod_hucresi,
            }
            for kol in DEVIRALINACAK_KOLONLAR:
                yeni_satir[kol] = grup["kaynak_satir"].get(kol)

            cozulen_satirlar.append(yeni_satir)
            islem_raporu.append(
                {
                    "aile_no": bilgi["aile_no"],
                    "token": token,
                    "yeni_stok_kodu": yeni_satir[STOK_KOLONU],
                    "kategori": kategori_adi,
                    "olcu_mm": olcu,
                    "boy": boy_degeri,
                }
            )

    cozulen_df = pd.DataFrame(cozulen_satirlar)
    elle_df = pd.DataFrame(elle_bakilacak)
    islem_df = pd.DataFrame(islem_raporu)

    cozulen_df.to_excel(CIKIS_DOSYASI, index=False)

    with pd.ExcelWriter(RAPOR_DOSYASI, engine="openpyxl") as writer:
        ozet = pd.DataFrame(
            [
                {"kontrol": "Toplam aile (karışık hücre)", "adet": len(aileler)},
                {
                    "kontrol": "Otomatik çözülen varyant",
                    "adet": len(cozulen_df),
                },
                {
                    "kontrol": "Elle bakılması gereken",
                    "adet": len(elle_df),
                },
            ]
        )
        ozet.to_excel(writer, sheet_name="Ozet", index=False)
        islem_df.to_excel(writer, sheet_name="Otomatik_Cozulenler", index=False)
        elle_df.to_excel(writer, sheet_name="Elle_Bakilmasi_Gereken", index=False)

    toplam = len(cozulen_df) + len(elle_df)
    oran = (100 * len(cozulen_df) / toplam) if toplam else 0

    print("✅ Karışık ürün çözme işlemi tamamlandı.")
    print(f"📁 Aile sayısı: {len(aileler)}")
    print(f"✅ Otomatik çözülen varyant: {len(cozulen_df)} (%{oran:.1f})")
    print(f"⚠️  Elle bakılması gereken kayıt: {len(elle_df)}")
    print(f"📄 Çözülen veri: {CIKIS_DOSYASI}")
    print(f"📄 Rapor: {RAPOR_DOSYASI}")


if __name__ == "__main__":
    main()
