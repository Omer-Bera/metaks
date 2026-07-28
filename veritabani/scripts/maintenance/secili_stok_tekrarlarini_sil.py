from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

GIRIS_DOSYASI = BASE_DIR / "temiz_urunler_tekrarsiz.xlsx"
CIKIS_DOSYASI = BASE_DIR / "temiz_urunler_tekrarsiz_v2.xlsx"
RAPOR_DOSYASI = BASE_DIR / "manuel_silinen_stok_tekrarlari.xlsx"

STOK_KOLONU = "ÜRÜN STOK KODU"

TEK_KAYDA_INDIRILECEK_KODLAR = {
    "2111735",
    "2117058",
    "2126746",
    "2134040",
}


def stok_kodunu_temizle(deger: object) -> str | None:
    if deger is None:
        return None

    metin = str(deger).strip()

    if metin.lower() in {"", "nan", "none", "<na>"}:
        return None

    if metin.endswith(".0") and metin[:-2].isdigit():
        return metin[:-2]

    return metin


def main() -> None:
    if not GIRIS_DOSYASI.exists():
        raise FileNotFoundError(
            f"Giriş dosyası bulunamadı: {GIRIS_DOSYASI}"
        )

    df = pd.read_excel(GIRIS_DOSYASI)

    if STOK_KOLONU not in df.columns:
        raise ValueError(
            f"'{STOK_KOLONU}' kolonu bulunamadı."
        )

    df["_stok_norm"] = df[STOK_KOLONU].apply(stok_kodunu_temizle)

    silinecek_indeksler: list[int] = []

    for stok_kodu in TEK_KAYDA_INDIRILECEK_KODLAR:
        indeksler = df.index[df["_stok_norm"] == stok_kodu].tolist()

        if len(indeksler) < 2:
            print(
                f"⚠️ {stok_kodu}: "
                f"{len(indeksler)} kayıt bulundu, işlem yapılmadı."
            )
            continue

        # İlk kaydı tut, sonraki kayıtları sil.
        silinecek_indeksler.extend(indeksler[1:])

        print(
            f"✅ {stok_kodu}: "
            f"{len(indeksler)} kayıttan 1 tanesi tutuldu, "
            f"{len(indeksler) - 1} tanesi silinecek."
        )

    silinenler = df.loc[silinecek_indeksler].copy()
    kalanlar = df.drop(index=silinecek_indeksler).copy()

    silinenler.insert(
        0,
        "orijinal_excel_satiri",
        silinenler.index + 2,
    )

    kalanlar = kalanlar.drop(columns=["_stok_norm"])
    silinenler = silinenler.drop(columns=["_stok_norm"])

    kalanlar.to_excel(CIKIS_DOSYASI, index=False)
    silinenler.to_excel(RAPOR_DOSYASI, index=False)

    kalan_stoklar = kalanlar[STOK_KOLONU].apply(stok_kodunu_temizle)

    kalan_tekrarlar = kalan_stoklar[
        kalan_stoklar.notna()
        & kalan_stoklar.duplicated(keep=False)
    ]

    print()
    print(f"✅ Silinen satır sayısı: {len(silinenler)}")
    print(f"✅ Kalan toplam satır: {len(kalanlar)}")
    print(
        "⚠️ Kalan tekrar eden farklı stok kodu: "
        f"{kalan_tekrarlar.nunique()}"
    )
    print(f"📄 Yeni dosya: {CIKIS_DOSYASI.name}")
    print(f"📄 Silinenler raporu: {RAPOR_DOSYASI.name}")


if __name__ == "__main__":
    main()