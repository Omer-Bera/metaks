from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

GIRIS_DOSYASI = BASE_DIR / "temiz_urunler_standart_duzeltilmis.xlsx"
CIKIS_DOSYASI = BASE_DIR / "temiz_urunler_tekrarsiz.xlsx"
RAPOR_DOSYASI = BASE_DIR / "silinen_ayni_urun_tekrarlari.xlsx"

STOK_KOLONU = "ÜRÜN STOK KODU"
KATEGORI_KOLONU = "ÜRÜN KATEGORİ GRUBU"
OLCU_KOLONU = "olcu_mm"
BOY_KOLONU = "boy_ligne"


def temiz_metin(deger: Any) -> str | None:
    if deger is None:
        return None

    metin = str(deger).strip()

    if metin.lower() in {"", "nan", "none", "<na>", "nat"}:
        return None

    if metin.endswith(".0") and metin[:-2].isdigit():
        metin = metin[:-2]

    return metin


def temiz_sayi(deger: Any) -> float | None:
    if deger is None:
        return None

    metin = str(deger).strip().replace(",", ".")

    if metin.lower() in {"", "nan", "none", "<na>", "nat", "?"}:
        return None

    try:
        return round(float(metin), 4)
    except (TypeError, ValueError):
        return None


def main() -> None:
    if not GIRIS_DOSYASI.exists():
        raise FileNotFoundError(
            f"Giriş dosyası bulunamadı: {GIRIS_DOSYASI}"
        )

    df = pd.read_excel(GIRIS_DOSYASI)

    gerekli_kolonlar = {
        STOK_KOLONU,
        KATEGORI_KOLONU,
        OLCU_KOLONU,
        BOY_KOLONU,
    }

    eksik_kolonlar = gerekli_kolonlar.difference(df.columns)

    if eksik_kolonlar:
        raise ValueError(
            "Eksik kolonlar: " + ", ".join(sorted(eksik_kolonlar))
        )

    # Karşılaştırma için geçici, normalize edilmiş kolonlar.
    df["_stok_norm"] = df[STOK_KOLONU].apply(temiz_metin)
    df["_kategori_norm"] = (
        df[KATEGORI_KOLONU]
        .apply(temiz_metin)
        .str.upper()
    )
    df["_olcu_norm"] = df[OLCU_KOLONU].apply(temiz_sayi)
    df["_boy_norm"] = df[BOY_KOLONU].apply(temiz_sayi)

    karsilastirma_kolonlari = [
        "_stok_norm",
        "_kategori_norm",
        "_olcu_norm",
        "_boy_norm",
    ]

    # Aynı ürün grubundaki ilk satırı tutar, sonrakileri mükerrer sayar.
    tekrar_maskesi = df.duplicated(
        subset=karsilastirma_kolonlari,
        keep="first",
    )

    silinenler = df.loc[tekrar_maskesi].copy()
    kalanlar = df.loc[~tekrar_maskesi].copy()

    # Rapor için Excel satır numarasını ekle.
    silinenler.insert(
        0,
        "orijinal_excel_satiri",
        silinenler.index + 2,
    )

    # Geçici kolonları temizle.
    gecici_kolonlar = [
        "_stok_norm",
        "_kategori_norm",
        "_olcu_norm",
        "_boy_norm",
    ]

    kalanlar = kalanlar.drop(columns=gecici_kolonlar)
    silinenler = silinenler.drop(columns=gecici_kolonlar)

    kalanlar.to_excel(CIKIS_DOSYASI, index=False)
    silinenler.to_excel(RAPOR_DOSYASI, index=False)

    stok_serisi = kalanlar[STOK_KOLONU].apply(temiz_metin)

    kalan_tekrarlar = kalanlar[
        stok_serisi.notna()
        & stok_serisi.duplicated(keep=False)
    ].copy()

    print("✅ Aynı ürün tekrarlarını ayıklama tamamlandı.")
    print(f"✅ Başlangıç satır sayısı: {len(df)}")
    print(f"🗑️ Silinen gerçek mükerrer satır: {len(silinenler)}")
    print(f"✅ Kalan satır sayısı: {len(kalanlar)}")
    print(
        "✅ Kalan benzersiz stok kodu: "
        f"{stok_serisi.nunique(dropna=True)}"
    )
    print(
        "⚠️ İncelenecek kalan tekrar satırı: "
        f"{len(kalan_tekrarlar)}"
    )
    print(f"📄 Yeni veri dosyası: {CIKIS_DOSYASI.name}")
    print(f"📄 Silinenler raporu: {RAPOR_DOSYASI.name}")


if __name__ == "__main__":
    main()