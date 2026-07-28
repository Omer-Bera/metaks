"""Çözülen karışık ürün varyantlarını, ana normalizasyon hattına (temiz_urunler_tekrarsiz_v2.xlsx)
ekler.

karisik_urunleri_coz.py'nin ürettiği data/interim/karisik_urunler_cozulmus.xlsx
dosyasındaki her satır bağımsız bir ANA_URUN'dur (aile anchor'ları zaten dahil
edilmedi, aralarında parent-child kurulmaz — 2026-07-28'de doğrulandı).

final_excel_hazirla.py bu scriptten sonra CIKIS_DOSYASI'nı (temiz_urunler_final.xlsx)
üretirken GIRIS_DOSYASI olarak bu scriptin çıktısını (temiz_urunler_karisik_dahil.xlsx)
kullanmalıdır.
"""

from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

TEMIZ_DOSYASI = BASE_DIR / "data" / "interim" / "temiz_urunler_tekrarsiz_v2.xlsx"
COZULMUS_DOSYASI = BASE_DIR / "data" / "interim" / "karisik_urunler_cozulmus.xlsx"
CIKIS_DOSYASI = BASE_DIR / "data" / "interim" / "temiz_urunler_karisik_dahil.xlsx"

STOK_KOLONU = "ÜRÜN STOK KODU"
KATEGORI_KOLONU = "ÜRÜN KATEGORİ GRUBU"
MM_KOLONU = "ÜRÜN DETAYI (mm)"
BOY_KOLONU = "ÜRÜN DETAYI (Boy)"


def boy_sayiya_cevir(deger: Any) -> float | None:
    if pd.isna(deger):
        return None
    s = str(deger).strip().lower().replace("boy", "").strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def main() -> None:
    temiz_df = pd.read_excel(TEMIZ_DOSYASI)
    cozulmus_df = pd.read_excel(COZULMUS_DOSYASI)

    mevcut_kodlar = set(
        temiz_df[STOK_KOLONU].dropna().astype(str).str.strip()
    )
    yeni_kodlar = set(
        cozulmus_df[STOK_KOLONU].dropna().astype(str).str.strip()
    )
    cakisan = mevcut_kodlar & yeni_kodlar
    if cakisan:
        raise ValueError(
            "Çözülen karışık kodlar mevcut temiz veriyle çakışıyor: "
            + ", ".join(sorted(cakisan))
        )
    if cozulmus_df[STOK_KOLONU].duplicated().any():
        tekrar = cozulmus_df[STOK_KOLONU][cozulmus_df[STOK_KOLONU].duplicated()]
        raise ValueError(
            "Çözülen karışık veri kendi içinde tekrar eden kod içeriyor: "
            + ", ".join(sorted(tekrar.astype(str).unique()))
        )

    yeni_satirlar = pd.DataFrame(
        {
            STOK_KOLONU: cozulmus_df[STOK_KOLONU],
            KATEGORI_KOLONU: cozulmus_df[KATEGORI_KOLONU],
            MM_KOLONU: cozulmus_df[MM_KOLONU].apply(
                lambda v: f"{v:g} mm" if pd.notna(v) else None
            ),
            BOY_KOLONU: cozulmus_df[BOY_KOLONU].apply(boy_sayiya_cevir),
            "ÜRÜN GÖRSELİ": cozulmus_df.get("ÜRÜN GÖRSELİ"),
            "ÜRÜN GRAMI": cozulmus_df.get("ÜRÜN GRAMI"),
            "ÜRÜN GÖZ SAYISI": cozulmus_df.get("ÜRÜN GÖZ SAYISI"),
            "ÜRÜN AÇIKLAMASI": cozulmus_df.get("ÜRÜN AÇIKLAMASI"),
            "ANA_STOK_KODU": None,
            "ÜRÜN TİPİ": "ANA_URUN",
            "olcu_mm": cozulmus_df[MM_KOLONU],
            "boy_ligne": cozulmus_df[BOY_KOLONU].apply(boy_sayiya_cevir),
        }
    )

    # Not: temiz_df bu aşamada "1805012" ve "2108" kodlarını hâlâ 2'şer kez
    # içerir — bunlar final_excel_hazirla.py'de özel olarak ALT_PARCA/VARYANT'a
    # bölünecek, beklenen bir durumdur. Yukarıdaki kontrol yalnızca YENİ
    # eklenen kodların hem kendi içinde hem mevcut veriyle çakışmadığını
    # doğruladı; bu yeterlidir.
    birlesik_df = pd.concat([temiz_df, yeni_satirlar], ignore_index=True)

    birlesik_df.to_excel(CIKIS_DOSYASI, index=False)

    print("✅ Karışık ürünler ana veriyle birleştirildi.")
    print(f"📁 Önceki satır sayısı: {len(temiz_df)}")
    print(f"📁 Eklenen karışık varyant: {len(yeni_satirlar)}")
    print(f"📁 Toplam: {len(birlesik_df)}")
    print(f"📄 Çıktı: {CIKIS_DOSYASI}")


if __name__ == "__main__":
    main()
