from pathlib import Path
import re
import shutil
from typing import Any

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

KAYNAK_KLASOR = BASE_DIR / "urun_gorselleri_stoklu_duzeltilmis"
HEDEF_KLASOR = BASE_DIR / "urun_gorselleri_stoklu_final"

ESLESME_RAPORU = (
    BASE_DIR / "birlesik_stok_kodu_duzeltme_raporu.xlsx"
)

CIKTI_RAPORU = (
    BASE_DIR / "gorsel_stok_kodu_guncelleme_raporu.xlsx"
)

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
        "<na>",
        "nat",
    }:
        return None

    if metin.endswith(".0") and metin[:-2].isdigit():
        metin = metin[:-2]

    return metin


def dogal_siralama_anahtari(path: Path) -> list[Any]:
    """
    Dosyaları şu sırayla sıralar:

    810208620.jpg
    810208620_2.jpg
    810208620_3.jpg
    """

    parcalar = re.split(r"(\d+)", path.stem)

    return [
        int(parca) if parca.isdigit() else parca.lower()
        for parca in parcalar
    ]


def stok_koduna_ait_dosyalar(
    klasor: Path,
    stok_kodu: str,
) -> list[Path]:
    """
    Şu dosyaları bulur:

    810208620.jpg
    810208620_2.jpg
    810208620_3.png
    """

    desen = re.compile(
        rf"^{re.escape(stok_kodu)}(?:_\d+)?$",
        flags=re.IGNORECASE,
    )

    dosyalar = [
        dosya
        for dosya in klasor.iterdir()
        if dosya.is_file()
        and dosya.suffix.lower() in DESTEKLENEN_UZANTILAR
        and desen.fullmatch(dosya.stem)
    ]

    return sorted(
        dosyalar,
        key=dogal_siralama_anahtari,
    )


def benzersiz_hedef_yolu(
    klasor: Path,
    stok_kodu: str,
    uzanti: str,
) -> Path:
    """
    Aynı yeni stok kodu için birden fazla görsel varsa:

    2134040.jpg
    2134040_2.jpg
    2134040_3.jpg
    """

    ilk_aday = klasor / f"{stok_kodu}{uzanti.lower()}"

    if not ilk_aday.exists():
        return ilk_aday

    sira = 2

    while True:
        aday = klasor / f"{stok_kodu}_{sira}{uzanti.lower()}"

        if not aday.exists():
            return aday

        sira += 1


def eslesmeleri_oku() -> dict[str, list[str]]:
    if not ESLESME_RAPORU.exists():
        raise FileNotFoundError(
            f"Eşleşme raporu bulunamadı: {ESLESME_RAPORU}"
        )

    rapor = pd.read_excel(
        ESLESME_RAPORU,
        sheet_name="Duzeltme_Raporu",
    )

    gerekli_kolonlar = {
        "eski_stok_kodu",
        "yeni_stok_kodu",
        "durum",
    }

    eksikler = gerekli_kolonlar.difference(rapor.columns)

    if eksikler:
        raise ValueError(
            "Raporda eksik kolonlar var: "
            + ", ".join(sorted(eksikler))
        )

    rapor["eski_stok_kodu"] = rapor[
        "eski_stok_kodu"
    ].apply(temiz_metin)

    rapor["yeni_stok_kodu"] = rapor[
        "yeni_stok_kodu"
    ].apply(temiz_metin)

    otomatik = rapor[
        rapor["durum"] == "OTOMATIK_DUZELTILDI"
    ].copy()

    eslesmeler: dict[str, list[str]] = {}

    for _, satir in otomatik.iterrows():
        eski_kod = satir["eski_stok_kodu"]
        yeni_kod = satir["yeni_stok_kodu"]

        if eski_kod is None or yeni_kod is None:
            continue

        eslesmeler.setdefault(eski_kod, []).append(
            yeni_kod
        )

    return eslesmeler


def main() -> None:
    if not KAYNAK_KLASOR.exists():
        raise FileNotFoundError(
            f"Kaynak görsel klasörü bulunamadı: "
            f"{KAYNAK_KLASOR}"
        )

    if HEDEF_KLASOR.exists():
        raise FileExistsError(
            f"Hedef klasör zaten var: {HEDEF_KLASOR}\n"
            "Önce klasörü kontrol edip kaldır veya "
            "scriptte farklı bir hedef adı kullan."
        )

    HEDEF_KLASOR.mkdir(parents=True)

    eslesmeler = eslesmeleri_oku()

    degisecek_eski_kodlar = set(eslesmeler)

    rapor_satirlari: list[dict[str, Any]] = []

    # Öncelikle adı değişmeyecek bütün görselleri kopyala.
    for kaynak_dosya in KAYNAK_KLASOR.iterdir():
        if not kaynak_dosya.is_file():
            continue

        if kaynak_dosya.suffix.lower() not in DESTEKLENEN_UZANTILAR:
            continue

        eski_koda_ait_mi = any(
            re.fullmatch(
                rf"{re.escape(eski_kod)}(?:_\d+)?",
                kaynak_dosya.stem,
                flags=re.IGNORECASE,
            )
            for eski_kod in degisecek_eski_kodlar
        )

        if eski_koda_ait_mi:
            continue

        hedef_dosya = HEDEF_KLASOR / kaynak_dosya.name

        shutil.copy2(
            kaynak_dosya,
            hedef_dosya,
        )

        rapor_satirlari.append(
            {
                "eski_dosya": kaynak_dosya.name,
                "yeni_dosya": hedef_dosya.name,
                "eski_stok_kodu": kaynak_dosya.stem,
                "yeni_stok_kodu": kaynak_dosya.stem,
                "durum": "DEGISTIRILMEDEN_KOPYALANDI",
                "aciklama": "",
            }
        )

    # Birleşik stok kodlu görselleri yeni kodlara dağıt.
    for eski_kod, yeni_kodlar in eslesmeler.items():
        eski_dosyalar = stok_koduna_ait_dosyalar(
            KAYNAK_KLASOR,
            eski_kod,
        )

        if len(eski_dosyalar) != len(yeni_kodlar):
            for dosya in eski_dosyalar:
                rapor_satirlari.append(
                    {
                        "eski_dosya": dosya.name,
                        "yeni_dosya": None,
                        "eski_stok_kodu": eski_kod,
                        "yeni_stok_kodu": None,
                        "durum": "ATLANDI",
                        "aciklama": (
                            f"{len(eski_dosyalar)} görsel bulundu, "
                            f"fakat {len(yeni_kodlar)} yeni stok "
                            "kodu bekleniyordu."
                        ),
                    }
                )

            print(
                f"⚠️ {eski_kod}: "
                f"{len(eski_dosyalar)} görsel, "
                f"{len(yeni_kodlar)} yeni kod bulundu. "
                "Otomatik değiştirilmedi."
            )

            continue

        for kaynak_dosya, yeni_kod in zip(
            eski_dosyalar,
            yeni_kodlar,
        ):
            hedef_dosya = benzersiz_hedef_yolu(
                HEDEF_KLASOR,
                yeni_kod,
                kaynak_dosya.suffix,
            )

            shutil.copy2(
                kaynak_dosya,
                hedef_dosya,
            )

            rapor_satirlari.append(
                {
                    "eski_dosya": kaynak_dosya.name,
                    "yeni_dosya": hedef_dosya.name,
                    "eski_stok_kodu": eski_kod,
                    "yeni_stok_kodu": yeni_kod,
                    "durum": "YENIDEN_ADLANDIRILDI",
                    "aciklama": (
                        "Birleşik stok kodu raporuna göre "
                        "yeniden adlandırıldı."
                    ),
                }
            )

            print(
                f"✅ {kaynak_dosya.name} "
                f"→ {hedef_dosya.name}"
            )

    rapor_df = pd.DataFrame(rapor_satirlari)

    rapor_df.to_excel(
        CIKTI_RAPORU,
        index=False,
    )

    kaynak_sayisi = sum(
        1
        for dosya in KAYNAK_KLASOR.iterdir()
        if dosya.is_file()
        and dosya.suffix.lower()
        in DESTEKLENEN_UZANTILAR
    )

    hedef_sayisi = sum(
        1
        for dosya in HEDEF_KLASOR.iterdir()
        if dosya.is_file()
        and dosya.suffix.lower()
        in DESTEKLENEN_UZANTILAR
    )

    yeniden_adlandirilan = sum(
        1
        for satir in rapor_satirlari
        if satir["durum"] == "YENIDEN_ADLANDIRILDI"
    )

    atlanan = sum(
        1
        for satir in rapor_satirlari
        if satir["durum"] == "ATLANDI"
    )

    print()
    print("✅ Görsel klasörü oluşturuldu.")
    print(f"📁 Kaynak görsel sayısı: {kaynak_sayisi}")
    print(f"📁 Hedef görsel sayısı: {hedef_sayisi}")
    print(
        f"✅ Yeniden adlandırılan görsel: "
        f"{yeniden_adlandirilan}"
    )
    print(f"⚠️ Atlanan görsel: {atlanan}")
    print(f"📁 Yeni klasör: {HEDEF_KLASOR.name}")
    print(f"📄 Rapor: {CIKTI_RAPORU.name}")


if __name__ == "__main__":
    main()