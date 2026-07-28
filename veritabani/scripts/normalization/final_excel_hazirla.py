from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

GIRIS_DOSYASI = BASE_DIR / "temiz_urunler_tekrarsiz_v2.xlsx"
CIKIS_DOSYASI = BASE_DIR / "temiz_urunler_final.xlsx"
RAPOR_DOSYASI = BASE_DIR / "final_excel_duzenleme_raporu.xlsx"


STOK_KOLONU = "ÜRÜN STOK KODU"
KATEGORI_KOLONU = "ÜRÜN KATEGORİ GRUBU"
URUN_TIPI_KOLONU = "ÜRÜN TİPİ"
PARENT_KOLONU = "ANA_STOK_KODU"
ACIKLAMA_KOLONU = "ÜRÜN AÇIKLAMASI"
GRAMAJ_KOLONU = "ÜRÜN GRAMI"

VARYANT_KOLONU = "VARYANT_ADI"
KALIP_KOLONU = "KALIP_VERSIYONU"
STOK_TAKIP_KOLONU = "STOK_TAKIP_EDILSIN_MI"
AKTIF_KOLONU = "AKTIF_MI"


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


def temiz_sayi(deger: Any) -> float | None:
    if deger is None:
        return None

    metin = str(deger).strip().replace(",", ".")

    if metin.lower() in {
        "",
        "nan",
        "none",
        "null",
        "<na>",
        "nat",
        "?",
    }:
        return None

    try:
        return float(metin)
    except (TypeError, ValueError):
        return None


def kolonlari_hazirla(df: pd.DataFrame) -> pd.DataFrame:
    zorunlu_kolonlar = {
        STOK_KOLONU,
        KATEGORI_KOLONU,
        URUN_TIPI_KOLONU,
        PARENT_KOLONU,
        ACIKLAMA_KOLONU,
        GRAMAJ_KOLONU,
    }

    eksik = zorunlu_kolonlar.difference(df.columns)

    if eksik:
        raise ValueError(
            "Excel dosyasında eksik kolonlar var: "
            + ", ".join(sorted(eksik))
        )

    yeni_kolonlar = {
        VARYANT_KOLONU: None,
        KALIP_KOLONU: None,
        STOK_TAKIP_KOLONU: True,
        AKTIF_KOLONU: True,
    }

    for kolon, varsayilan in yeni_kolonlar.items():
        if kolon not in df.columns:
            df[kolon] = varsayilan

    return df


def ana_urun_satiri_olustur(
    kaynak_satir: pd.Series,
    stok_kodu: str,
    aciklama: str,
) -> pd.Series:
    ana_satir = kaynak_satir.copy()

    ana_satir[STOK_KOLONU] = stok_kodu
    ana_satir[URUN_TIPI_KOLONU] = "ANA_URUN"
    ana_satir[PARENT_KOLONU] = None
    ana_satir[ACIKLAMA_KOLONU] = aciklama
    ana_satir[VARYANT_KOLONU] = None
    ana_satir[KALIP_KOLONU] = None
    ana_satir[STOK_TAKIP_KOLONU] = False
    ana_satir[AKTIF_KOLONU] = True

    # Ana kayıt sadece gruplama amaçlıdır.
    # Teknik değerleri çocuk kayıtlardan üretmek daha doğrudur.
    if "ÜRÜN GRAMI" in ana_satir.index:
        ana_satir["ÜRÜN GRAMI"] = None

    return ana_satir


def stok_2108_duzenle(
    df: pd.DataFrame,
    rapor: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.Series]:
    mask = df["_stok_norm"] == "2108"
    indeksler = df.index[mask].tolist()

    if len(indeksler) != 2:
        raise ValueError(
            f"2108 için tam 2 satır bekleniyordu, "
            f"{len(indeksler)} satır bulundu."
        )

    pul_indeksleri = [
        indeks
        for indeks in indeksler
        if "PUL" in (
            temiz_metin(df.at[indeks, KATEGORI_KOLONU]) or ""
        ).upper()
    ]

    if len(pul_indeksleri) != 1:
        raise ValueError(
            "2108 kayıtlarında PUL kategorisindeki satır "
            "tek olarak belirlenemedi."
        )

    pul_indeksi = pul_indeksleri[0]
    toka_indeksi = next(
        indeks
        for indeks in indeksler
        if indeks != pul_indeksi
    )

    df.at[toka_indeksi, STOK_KOLONU] = "2108-TOKA"
    df.at[toka_indeksi, URUN_TIPI_KOLONU] = "ALT_PARCA"
    df.at[toka_indeksi, PARENT_KOLONU] = "2108"
    df.at[toka_indeksi, VARYANT_KOLONU] = "Üst toka"
    df.at[toka_indeksi, KALIP_KOLONU] = None
    df.at[toka_indeksi, STOK_TAKIP_KOLONU] = True
    df.at[toka_indeksi, AKTIF_KOLONU] = True
    df.at[
        toka_indeksi,
        ACIKLAMA_KOLONU,
    ] = "2108 toka takımının üst toka parçası"

    df.at[pul_indeksi, STOK_KOLONU] = "2108-PUL"
    df.at[pul_indeksi, URUN_TIPI_KOLONU] = "ALT_PARCA"
    df.at[pul_indeksi, PARENT_KOLONU] = "2108"
    df.at[pul_indeksi, VARYANT_KOLONU] = "Alt pul"
    df.at[pul_indeksi, KALIP_KOLONU] = None
    df.at[pul_indeksi, STOK_TAKIP_KOLONU] = True
    df.at[pul_indeksi, AKTIF_KOLONU] = True
    df.at[
        pul_indeksi,
        ACIKLAMA_KOLONU,
    ] = "2108 toka takımının alt pul parçası"

    ana_satir = ana_urun_satiri_olustur(
        kaynak_satir=df.loc[toka_indeksi],
        stok_kodu="2108",
        aciklama="2108 toka takımı: üst toka ve alt pul",
    )

    rapor.extend(
        [
            {
                "eski_stok_kodu": "2108",
                "yeni_stok_kodu": "2108-TOKA",
                "islem": "ALT_PARCA_OLUSTURULDU",
            },
            {
                "eski_stok_kodu": "2108",
                "yeni_stok_kodu": "2108-PUL",
                "islem": "ALT_PARCA_OLUSTURULDU",
            },
            {
                "eski_stok_kodu": None,
                "yeni_stok_kodu": "2108",
                "islem": "ANA_URUN_EKLENDI",
            },
        ]
    )

    return df, ana_satir

def stok_1805012_duzenle(
    df: pd.DataFrame,
    rapor: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.Series]:
    mask = df["_stok_norm"] == "1805012"
    indeksler = df.index[mask].tolist()

    if len(indeksler) != 2:
        raise ValueError(
            f"1805012 için tam 2 satır bekleniyordu, "
            f"{len(indeksler)} satır bulundu."
        )

    boy_degerleri = {
        indeks: temiz_sayi(df.at[indeks, "boy_ligne"])
        for indeks in indeksler
    }

    # Kullanıcının verdiği bilgi:
    # yaklaşık 2207. satırdaki, yani boy_ligne değeri boş olan kayıt yeni kalıp.
    yeni_adaylar = [
        indeks
        for indeks in indeksler
        if boy_degerleri[indeks] is None
    ]

    eski_adaylar = [
        indeks
        for indeks in indeksler
        if boy_degerleri[indeks] is not None
    ]

    if len(yeni_adaylar) != 1 or len(eski_adaylar) != 1:
        raise ValueError(
            "1805012 için yeni ve eski kalıp, "
            "boy_ligne bilgisine göre tekil olarak belirlenemedi."
        )

    yeni_indeks = yeni_adaylar[0]
    eski_indeks = eski_adaylar[0]

    df.at[yeni_indeks, STOK_KOLONU] = "1805012-YENI"
    df.at[yeni_indeks, URUN_TIPI_KOLONU] = "VARYANT"
    df.at[yeni_indeks, PARENT_KOLONU] = "1805012"
    df.at[yeni_indeks, VARYANT_KOLONU] = "Yeni kalıp"
    df.at[yeni_indeks, KALIP_KOLONU] = "YENI"
    df.at[yeni_indeks, STOK_TAKIP_KOLONU] = True
    df.at[yeni_indeks, AKTIF_KOLONU] = True
    df.at[
        yeni_indeks,
        ACIKLAMA_KOLONU,
    ] = (
        "1805012 ürününün yeni kalıpla üretilen "
        "hafifletilmiş varyantı"
    )

    df.at[eski_indeks, STOK_KOLONU] = "1805012-ESKI"
    df.at[eski_indeks, URUN_TIPI_KOLONU] = "VARYANT"
    df.at[eski_indeks, PARENT_KOLONU] = "1805012"
    df.at[eski_indeks, VARYANT_KOLONU] = "Eski kalıp"
    df.at[eski_indeks, KALIP_KOLONU] = "ESKI"
    df.at[eski_indeks, STOK_TAKIP_KOLONU] = True
    df.at[eski_indeks, AKTIF_KOLONU] = True
    df.at[
        eski_indeks,
        ACIKLAMA_KOLONU,
    ] = "1805012 ürününün eski kalıpla üretilen varyantı"

    ana_satir = ana_urun_satiri_olustur(
        kaynak_satir=df.loc[yeni_indeks],
        stok_kodu="1805012",
        aciklama=(
            "1805012 ürün modeli: eski ve yeni kalıp varyantları"
        ),
    )

    rapor.extend(
        [
            {
                "eski_stok_kodu": "1805012",
                "yeni_stok_kodu": "1805012-YENI",
                "islem": "VARYANT_OLUSTURULDU",
                "kaynak_boy_ligne": boy_degerleri[yeni_indeks],
            },
            {
                "eski_stok_kodu": "1805012",
                "yeni_stok_kodu": "1805012-ESKI",
                "islem": "VARYANT_OLUSTURULDU",
                "kaynak_boy_ligne": boy_degerleri[eski_indeks],
            },
            {
                "eski_stok_kodu": None,
                "yeni_stok_kodu": "1805012",
                "islem": "ANA_URUN_EKLENDI",
                "kaynak_boy_ligne": None,
            },
        ]
    )

    return df, ana_satir
def main() -> None:
    if not GIRIS_DOSYASI.exists():
        raise FileNotFoundError(
            f"Giriş dosyası bulunamadı: {GIRIS_DOSYASI}"
        )

    df = pd.read_excel(GIRIS_DOSYASI)
    df = kolonlari_hazirla(df)

    df["_stok_norm"] = df[STOK_KOLONU].apply(temiz_metin)

    rapor: list[dict[str, Any]] = []

    df, ana_2108 = stok_2108_duzenle(df, rapor)
    df, ana_1805012 = stok_1805012_duzenle(df, rapor)

    df = pd.concat(
        [
            df,
            pd.DataFrame([ana_2108, ana_1805012]),
        ],
        ignore_index=True,
    )

    df = df.drop(columns=["_stok_norm"])

    # Nihai stok kodu temizliği.
    df[STOK_KOLONU] = df[STOK_KOLONU].apply(temiz_metin)

    tekrarlar = df[
        df[STOK_KOLONU].notna()
        & df.duplicated(
            subset=[STOK_KOLONU],
            keep=False,
        )
    ].copy()

    if not tekrarlar.empty:
        tekrar_kodlari = sorted(
            tekrarlar[STOK_KOLONU].dropna().unique().tolist()
        )

        raise ValueError(
            "Final dosyada tekrar eden stok kodları kaldı: "
            + ", ".join(tekrar_kodlari)
        )

    df.to_excel(CIKIS_DOSYASI, index=False)

    rapor_df = pd.DataFrame(rapor)

    with pd.ExcelWriter(
        RAPOR_DOSYASI,
        engine="openpyxl",
    ) as writer:
        rapor_df.to_excel(
            writer,
            sheet_name="Yapilan_Islemler",
            index=False,
        )

        df[
            df[STOK_KOLONU].isin(
                [
                    "2108",
                    "2108-TOKA",
                    "2108-PUL",
                    "1805012",
                    "1805012-ESKI",
                    "1805012-YENI",
                ]
            )
        ].to_excel(
            writer,
            sheet_name="Ozel_Urunler",
            index=False,
        )

    print("✅ Final Excel dosyası hazırlandı.")
    print(f"✅ Toplam satır: {len(df)}")
    print(
        "✅ Benzersiz stok kodu: "
        f"{df[STOK_KOLONU].nunique(dropna=True)}"
    )
    print(f"📄 Final dosya: {CIKIS_DOSYASI.name}")
    print(f"📄 Kontrol raporu: {RAPOR_DOSYASI.name}")


if __name__ == "__main__":
    main()