from pathlib import Path
import re
from typing import Any

import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extensions import cursor as PgCursor


BASE_DIR = Path(__file__).resolve().parents[2]

GORSEL_KLASORU = BASE_DIR / "images" / "final" / "products"
RAPOR_DOSYASI = BASE_DIR / "reports" / "excel" / "gorsel_eslesme_raporu.xlsx"

DB_NAME = "depo_sistemi"
DB_USER = "depo_admin"
DB_PASSWORD = "supergizlisifre"
DB_HOST = "localhost"
DB_PORT = 5433

DESTEKLENEN_UZANTILAR = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def temiz_metin(deger: Any) -> str | None:
    if deger is None:
        return None

    metin = str(deger).strip()

    if metin.lower() in {
        "",
        "nan",
        "none",
        "null",
        "<na>",
        "nat",
    }:
        return None

    if metin.endswith(".0") and metin[:-2].isdigit():
        metin = metin[:-2]

    return metin


def dosyadan_stok_kodu_cikar(
    dosya_adi: str,
) -> str | None:
    """
    Örnekler:

    12345.jpg       -> 12345
    12345_1.jpeg    -> 12345
    12345_2.png     -> 12345
    2108-TOKA.jpg   -> 2108-TOKA
    """

    stem = Path(dosya_adi).stem.strip()

    if not stem:
        return None

    stok_kodu = re.sub(
        r"_[0-9]+$",
        "",
        stem,
    )

    return temiz_metin(stok_kodu)


def veritabanindan_urunleri_oku() -> pd.DataFrame:
    conn: PgConnection = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )

    try:
        with conn.cursor() as cur:
            cur: PgCursor

            cur.execute(
                """
                SELECT
                    stok_kodu,
                    urun_tipi,
                    parent_stok_kodu,
                    aktif_mi
                FROM urunler
                ORDER BY stok_kodu;
                """
            )

            satirlar = cur.fetchall()

            kolonlar = [
                aciklama.name
                for aciklama in cur.description
            ]

        return pd.DataFrame(
            satirlar,
            columns=kolonlar,
        )

    finally:
        conn.close()


def gorsel_dosyalarini_oku() -> pd.DataFrame:
    kayitlar: list[dict[str, object]] = []

    if not GORSEL_KLASORU.exists():
        raise FileNotFoundError(
            f"Görsel klasörü bulunamadı: "
            f"{GORSEL_KLASORU}"
        )

    for dosya in sorted(
        GORSEL_KLASORU.iterdir(),
        key=lambda path: path.name.lower(),
    ):
        if not dosya.is_file():
            continue

        if (
            dosya.suffix.lower()
            not in DESTEKLENEN_UZANTILAR
        ):
            continue

        stok_kodu = dosyadan_stok_kodu_cikar(
            dosya.name
        )

        kayitlar.append(
            {
                "dosya_adi": dosya.name,
                "stok_kodu": stok_kodu,
                "uzanti": dosya.suffix.lower(),
                "dosya_boyutu_byte": (
                    dosya.stat().st_size
                ),
            }
        )

    return pd.DataFrame(
        kayitlar,
        columns=[
            "dosya_adi",
            "stok_kodu",
            "uzanti",
            "dosya_boyutu_byte",
        ],
    )


def stok_kodu_kumesi_olustur(
    seri: pd.Series,
) -> set[str]:
    sonuc: set[str] = set()

    for deger in seri.tolist():
        metin = temiz_metin(deger)

        if metin is not None:
            sonuc.add(metin)

    return sonuc


def main() -> None:
    print(
        "🔎 Görsel ve ürün eşleştirmesi "
        "kontrol ediliyor..."
    )

    urunler = veritabanindan_urunleri_oku()
    gorseller = gorsel_dosyalarini_oku()

    urun_stoklari = stok_kodu_kumesi_olustur(
        urunler["stok_kodu"]
    )

    gorsel_stoklari = stok_kodu_kumesi_olustur(
        gorseller["stok_kodu"]
    )

    gorseller["veritabaninda_var_mi"] = (
        gorseller["stok_kodu"].apply(
            lambda deger: (
                temiz_metin(deger)
                in urun_stoklari
            )
        )
    )

    urunler["gorsel_var_mi"] = (
        urunler["stok_kodu"].apply(
            lambda deger: (
                temiz_metin(deger)
                in gorsel_stoklari
            )
        )
    )

    eslesmeyen_gorseller = gorseller.loc[
        ~gorseller["veritabaninda_var_mi"]
    ].copy()

    gorselsiz_urunler = urunler.loc[
        ~urunler["gorsel_var_mi"]
    ].copy()

    eslesen_gorseller = gorseller.loc[
        gorseller["veritabaninda_var_mi"]
    ].copy()

    gorsel_sayilari = (
        eslesen_gorseller
        .groupby(
            "stok_kodu",
            dropna=False,
        )
        .size()
        .reset_index(
            name="gorsel_sayisi"
        )
    )

    birden_fazla_gorseli_olanlar = (
        gorsel_sayilari.loc[
            gorsel_sayilari["gorsel_sayisi"] > 1
        ].copy()
    )

    ozet = pd.DataFrame(
        [
            {
                "kontrol": (
                    "Veritabanındaki toplam ürün"
                ),
                "adet": len(urunler),
            },
            {
                "kontrol": (
                    "Klasördeki toplam görsel"
                ),
                "adet": len(gorseller),
            },
            {
                "kontrol": "Eşleşen görsel",
                "adet": len(eslesen_gorseller),
            },
            {
                "kontrol": "Eşleşmeyen görsel",
                "adet": len(eslesmeyen_gorseller),
            },
            {
                "kontrol": "Görseli olmayan ürün",
                "adet": len(gorselsiz_urunler),
            },
            {
                "kontrol": (
                    "Birden fazla görseli olan ürün"
                ),
                "adet": len(
                    birden_fazla_gorseli_olanlar
                ),
            },
        ]
    )

    with pd.ExcelWriter(
        RAPOR_DOSYASI,
        engine="openpyxl",
    ) as writer:
        ozet.to_excel(
            writer,
            sheet_name="Ozet",
            index=False,
        )

        eslesmeyen_gorseller.to_excel(
            writer,
            sheet_name="Eslesmeyen_Gorseller",
            index=False,
        )

        gorselsiz_urunler.to_excel(
            writer,
            sheet_name="Gorselsiz_Urunler",
            index=False,
        )

        eslesen_gorseller.to_excel(
            writer,
            sheet_name="Eslesen_Gorseller",
            index=False,
        )

        birden_fazla_gorseli_olanlar.to_excel(
            writer,
            sheet_name="Coklu_Gorseller",
            index=False,
        )

        gorseller.to_excel(
            writer,
            sheet_name="Tum_Gorseller",
            index=False,
        )

    print("✅ Görsel eşleşme raporu oluşturuldu.")
    print(f"📄 Rapor: {RAPOR_DOSYASI.name}")
    print(
        f"📦 Veritabanındaki ürün: "
        f"{len(urunler)}"
    )
    print(
        f"🖼️ Klasördeki görsel: "
        f"{len(gorseller)}"
    )
    print(
        f"✅ Eşleşen görsel: "
        f"{len(eslesen_gorseller)}"
    )
    print(
        f"⚠️ Eşleşmeyen görsel: "
        f"{len(eslesmeyen_gorseller)}"
    )
    print(
        f"⚠️ Görseli olmayan ürün: "
        f"{len(gorselsiz_urunler)}"
    )
    print(
        "🗂️ Birden fazla görseli olan ürün: "
        f"{len(birden_fazla_gorseli_olanlar)}"
    )


if __name__ == "__main__":
    main()