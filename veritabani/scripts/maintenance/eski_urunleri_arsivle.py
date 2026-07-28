"""Standartlaştırılamayan / eşleştirilemeyen eski ürünleri ve görselleri arşivler.

2026-07-28: Karışık stok kodu çözme çalışmasından sonra kalan uzun kuyruk
(çözülemeyen kod varyantları, hiç işlenmemiş "ölçü karmaşık" satırlar,
stoksuz satırlar, eşleşmeyen görseller) muhtemelen çok eski / düşük ciro
ürünlere ait. Bunların peşinden koşmak yerine bilinçli olarak arşivliyoruz;
hiçbir şey silinmiyor, sadece net bir şekilde ayrılıyor. Aktif sistem
(veritabanı + images/final, images/working) yalnızca standartlaştırılmış
2.974 ürünle ilgili veriyi içerir.

Bu script veritabanına DOKUNMAZ (bu satırlar zaten hiç yüklenmemişti).
"""

from pathlib import Path
import shutil

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

KARISIK_RAPORU = BASE_DIR / "reports" / "excel" / "karisik_urun_cozme_raporu.xlsx"
OLCU_DUZENLENECEK = BASE_DIR / "data" / "interim" / "temiz_urunler_olcu_duzenlenecek.xlsx"
STOKSUZ = BASE_DIR / "data" / "interim" / "temiz_urunler_stoksuz.xlsx"
GORSEL_RAPORU = BASE_DIR / "reports" / "excel" / "gorsel_eslesme_raporu.xlsx"

CIKIS_DOSYASI = BASE_DIR / "data" / "reference" / "arsivlenen_eski_urunler.xlsx"

GORSEL_KAYNAK_KLASORLERI = [
    BASE_DIR / "images" / "final" / "products",
    BASE_DIR / "images" / "working" / "products",
]
GORSEL_ARSIV_KLASORU = BASE_DIR / "images" / "arsiv" / "products"


def main() -> None:
    karisik_df = pd.read_excel(KARISIK_RAPORU, sheet_name="Elle_Bakilmasi_Gereken")
    olcu_df = pd.read_excel(OLCU_DUZENLENECEK)
    stoksuz_df = pd.read_excel(STOKSUZ)
    gorsel_df = pd.read_excel(GORSEL_RAPORU, sheet_name="Eslesmeyen_Gorseller")

    ozet = pd.DataFrame(
        [
            {"kategori": "Karışık kod - çözülemeyen varyant", "adet": len(karisik_df)},
            {"kategori": "Ölçü karmaşık (hiç işlenmemiş)", "adet": len(olcu_df)},
            {"kategori": "Stok kodu yok", "adet": len(stoksuz_df)},
            {"kategori": "Eşleşmeyen görsel dosyası", "adet": len(gorsel_df)},
        ]
    )

    CIKIS_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(CIKIS_DOSYASI, engine="openpyxl") as writer:
        ozet.to_excel(writer, sheet_name="Ozet", index=False)
        karisik_df.to_excel(writer, sheet_name="Karisik_Cozulemeyen", index=False)
        olcu_df.to_excel(writer, sheet_name="Olcu_Karmasik", index=False)
        stoksuz_df.to_excel(writer, sheet_name="Stoksuz", index=False)
        gorsel_df.to_excel(writer, sheet_name="Eslesmeyen_Gorseller", index=False)

    print(f"📄 Arşiv listesi yazıldı: {CIKIS_DOSYASI}")
    print(ozet.to_string(index=False))

    # --- Görselleri taşı ---
    GORSEL_ARSIV_KLASORU.mkdir(parents=True, exist_ok=True)
    tasinan_dosya_adlari = set(gorsel_df["dosya_adi"].dropna().astype(str))

    toplam_tasinan = 0
    for klasor in GORSEL_KAYNAK_KLASORLERI:
        if not klasor.exists():
            continue
        for dosya_adi in tasinan_dosya_adlari:
            kaynak = klasor / dosya_adi
            if kaynak.exists() and kaynak.is_file():
                hedef = GORSEL_ARSIV_KLASORU / dosya_adi
                shutil.move(str(kaynak), str(hedef))
                toplam_tasinan += 1

    print(f"\n🖼️ Taşınan görsel dosyası sayısı: {toplam_tasinan}")
    print(f"📁 Arşiv klasörü: {GORSEL_ARSIV_KLASORU}")


if __name__ == "__main__":
    main()
