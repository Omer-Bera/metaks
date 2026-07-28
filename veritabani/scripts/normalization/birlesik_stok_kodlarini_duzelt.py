from pathlib import Path
import re
from typing import Any

import pandas as pd



BASE_DIR = Path(__file__).resolve().parent

GIRIS_DOSYASI = BASE_DIR / "temiz_urunler_standart.xlsx"
CIKIS_DOSYASI = BASE_DIR / "temiz_urunler_standart_duzeltilmis.xlsx"
RAPOR_DOSYASI = BASE_DIR / "birlesik_stok_kodu_duzeltme_raporu.xlsx"

STOK_KODU_KOLONU = "ÜRÜN STOK KODU"


def stok_kodunu_temizle(deger: Any) -> str | None:
    """Excel stok kodunu güvenli biçimde metne dönüştürür."""

    if deger is None:
        return None

    try:
        if pd.isna(deger):
            return None
    except (TypeError, ValueError):
        pass

    metin = str(deger).strip()

    if metin.endswith(".0") and metin[:-2].isdigit():
        metin = metin[:-2]

    if not metin:
        return None

    return metin

    metin = str(deger).strip()

    # Excel sayıyı 810208620.0 şeklinde okuduysa düzelt.
    if metin.endswith(".0") and metin[:-2].isdigit():
        metin = metin[:-2]

    if not metin:
        return None

    return metin


def dokuz_haneli_birlesik_kodu_ayir(
    stok_kodu: str,
) -> tuple[str, str] | None:
    """
    Örnek:
        810208620 -> 810208 ve 810620
    """

    if not re.fullmatch(r"\d{9}", stok_kodu):
        return None

    ortak_on_ek = stok_kodu[:3]
    birinci_son_ek = stok_kodu[3:6]
    ikinci_son_ek = stok_kodu[6:9]

    birinci_kod = ortak_on_ek + birinci_son_ek
    ikinci_kod = ortak_on_ek + ikinci_son_ek

    if birinci_kod == ikinci_kod:
        return None

    return birinci_kod, ikinci_kod


def main() -> None:
    if not GIRIS_DOSYASI.exists():
        raise FileNotFoundError(
            f"Giriş dosyası bulunamadı: {GIRIS_DOSYASI}"
        )

    df = pd.read_excel(GIRIS_DOSYASI)

    if STOK_KODU_KOLONU not in df.columns:
        raise ValueError(
            f"Excel'de '{STOK_KODU_KOLONU}' kolonu bulunamadı."
        )

    df[STOK_KODU_KOLONU] = df[STOK_KODU_KOLONU].apply(
        stok_kodunu_temizle
    )

    # Değişiklikten önce Excel'deki bütün mevcut kodlar.
    mevcut_kodlar = set(
        df[STOK_KODU_KOLONU].dropna().astype(str)
    )

    tekrar_sayilari = df[STOK_KODU_KOLONU].value_counts(dropna=True)

    rapor_satirlari: list[dict[str, object]] = []
    otomatik_duzeltilen_grup = 0
    otomatik_duzeltilen_satir = 0

    for stok_kodu, tekrar_sayisi in tekrar_sayilari.items():
        stok_kodu = str(stok_kodu)

        if tekrar_sayisi <= 1:
            continue

        satir_indeksleri = df.index[
            df[STOK_KODU_KOLONU] == stok_kodu
        ].tolist()

        ayrilmis_kodlar = dokuz_haneli_birlesik_kodu_ayir(stok_kodu)

        if tekrar_sayisi != 2:
            durum = "ATLANDI"
            neden = (
                f"Kod iki değil, {tekrar_sayisi} kez tekrarlanıyor."
            )

            for index in satir_indeksleri:
                rapor_satirlari.append(
                    {
                        "excel_satiri": index + 2,
                        "eski_stok_kodu": stok_kodu,
                        "yeni_stok_kodu": None,
                        "durum": durum,
                        "neden": neden,
                    }
                )

            continue

        if ayrilmis_kodlar is None:
            durum = "ATLANDI"
            neden = "Stok kodu tam olarak 9 rakamdan oluşmuyor."

            for index in satir_indeksleri:
                rapor_satirlari.append(
                    {
                        "excel_satiri": index + 2,
                        "eski_stok_kodu": stok_kodu,
                        "yeni_stok_kodu": None,
                        "durum": durum,
                        "neden": neden,
                    }
                )

            continue

        birinci_kod, ikinci_kod = ayrilmis_kodlar

        # Eski birleşik kod dışındaki mevcut kodlarla çakışmayı kontrol et.
        diger_mevcut_kodlar = mevcut_kodlar - {stok_kodu}

        cakisan_kodlar = [
            yeni_kod
            for yeni_kod in (birinci_kod, ikinci_kod)
            if yeni_kod in diger_mevcut_kodlar
        ]

        if cakisan_kodlar:
            durum = "ATLANDI"
            neden = (
                "Üretilecek kodlardan biri zaten Excel'de mevcut: "
                + ", ".join(cakisan_kodlar)
            )

            for index, yeni_kod in zip(
                satir_indeksleri,
                (birinci_kod, ikinci_kod),
            ):
                rapor_satirlari.append(
                    {
                        "excel_satiri": index + 2,
                        "eski_stok_kodu": stok_kodu,
                        "yeni_stok_kodu": yeni_kod,
                        "durum": durum,
                        "neden": neden,
                    }
                )

            continue

        # İlk tekrar satırına ilk altı hane,
        # ikinci tekrar satırına ilk üç + son üç hane atanır.
        yeni_kodlar = (birinci_kod, ikinci_kod)

        for index, yeni_kod in zip(satir_indeksleri, yeni_kodlar):
            df.at[index, STOK_KODU_KOLONU] = yeni_kod

            rapor_satirlari.append(
                {
                    "excel_satiri": index + 2,
                    "eski_stok_kodu": stok_kodu,
                    "yeni_stok_kodu": yeni_kod,
                    "durum": "OTOMATIK_DUZELTILDI",
                    "neden": (
                        "9 haneli birleşik kod, "
                        "3+3 ve 3+son3 kuralıyla ayrıldı."
                    ),
                }
            )

        otomatik_duzeltilen_grup += 1
        otomatik_duzeltilen_satir += 2

    rapor_df = pd.DataFrame(rapor_satirlari)

    # Düzeltmeden sonra kalan tekrarlar.
    kalan_tekrar_maskesi = (
        df[STOK_KODU_KOLONU].notna()
        & df[STOK_KODU_KOLONU].duplicated(keep=False)
    )

    kalan_tekrarlar = df.loc[kalan_tekrar_maskesi].copy()

    # Asıl veri dosyasını değiştirmeden yeni dosyaya yaz.
    df.to_excel(CIKIS_DOSYASI, index=False)

    with pd.ExcelWriter(RAPOR_DOSYASI, engine="openpyxl") as writer:
        rapor_df.to_excel(
            writer,
            sheet_name="Duzeltme_Raporu",
            index=False,
        )

        kalan_tekrarlar.to_excel(
            writer,
            sheet_name="Kalan_Tekrarlar",
            index=False,
        )

    benzersiz_sayi = df[STOK_KODU_KOLONU].nunique(dropna=True)
    kalan_fazla_tekrar = df[STOK_KODU_KOLONU].duplicated().sum()

    print("✅ İşlem tamamlandı.")
    print(
        f"✅ Otomatik düzeltilen birleşik kod grubu: "
        f"{otomatik_duzeltilen_grup}"
    )
    print(
        f"✅ Otomatik düzeltilen Excel satırı: "
        f"{otomatik_duzeltilen_satir}"
    )
    print(
        f"✅ Düzeltme sonrası benzersiz stok kodu: "
        f"{benzersiz_sayi}"
    )
    print(
        f"⚠️ Kalan ilk kayıt dışındaki tekrar sayısı: "
        f"{kalan_fazla_tekrar}"
    )
    print(f"📄 Düzeltilmiş Excel: {CIKIS_DOSYASI.name}")
    print(f"📄 Kontrol raporu: {RAPOR_DOSYASI.name}")


if __name__ == "__main__":
    main()