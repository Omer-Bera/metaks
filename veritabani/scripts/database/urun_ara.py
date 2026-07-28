"""Bir stok kodunun hangi dosyada/durumda olduğunu hızlıca söyler.

Çalıştırma:
    python3 scripts/database/urun_ara.py 960018

CSV'ler güncel değilse önce şunu çalıştır:
    python3 scripts/database/csv_guncelle.py

Arama kısmi (contains) eşleşme yapar; "960018" hem tam eşleşen aktif
ürünleri hem de içinde "960018" geçen arşiv kayıtlarını (ör. birleşik
kod hücreleri) bulur.
"""

from pathlib import Path
import sys

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]

URUNLER_CSV = BASE_DIR / "data" / "processed" / "urunler.csv"
GORSELLER_CSV = BASE_DIR / "data" / "processed" / "urun_gorselleri.csv"
ARSIV_URUNLER_CSV = BASE_DIR / "data" / "reference" / "arsivlenen_urunler.csv"
ARSIV_GORSELLER_CSV = BASE_DIR / "data" / "reference" / "arsivlenen_gorseller.csv"


def guvenli_oku(yol: Path) -> pd.DataFrame:
    if not yol.exists():
        print(f"⚠️  {yol.name} bulunamadı. Önce csv_guncelle.py çalıştırılmalı.")
        return pd.DataFrame()
    return pd.read_csv(yol, dtype=str)


def main() -> None:
    if len(sys.argv) < 2:
        print("Kullanım: python3 urun_ara.py <stok_kodu_veya_parcasi>")
        sys.exit(1)

    aranan = sys.argv[1].strip()
    print(f"🔎 '{aranan}' aranıyor...\n")

    urunler_df = guvenli_oku(URUNLER_CSV)
    gorseller_df = guvenli_oku(GORSELLER_CSV)
    arsiv_urunler_df = guvenli_oku(ARSIV_URUNLER_CSV)
    arsiv_gorseller_df = guvenli_oku(ARSIV_GORSELLER_CSV)

    bulundu = False

    if not urunler_df.empty:
        tam = urunler_df[urunler_df["stok_kodu"] == aranan]
        if not tam.empty:
            bulundu = True
            print("✅ AKTİF ÜRÜN (veritabanında):")
            print(tam.to_string(index=False))
            stok_kodu = tam.iloc[0]["stok_kodu"]
            gorsel = gorseller_df[gorseller_df["stok_kodu"] == stok_kodu] if not gorseller_df.empty else pd.DataFrame()
            if not gorsel.empty:
                print(f"\n🖼️ Görsel VAR ({len(gorsel)} adet):")
                print(gorsel.to_string(index=False))
            else:
                print("\n🖼️ Görsel YOK.")
            print()

        kismi = urunler_df[
            urunler_df["stok_kodu"].str.contains(aranan, case=False, na=False)
            & (urunler_df["stok_kodu"] != aranan)
        ]
        if not kismi.empty:
            bulundu = True
            print(f"🔸 Benzer/parçası eşleşen {len(kismi)} aktif ürün daha var:")
            print(kismi[["stok_kodu", "kategori_adi", "olcu_mm"]].to_string(index=False))
            print()

    if not arsiv_urunler_df.empty:
        arsiv_eslesen = arsiv_urunler_df[
            arsiv_urunler_df["arama_metni"].str.contains(aranan, case=False, na=False)
        ]
        if not arsiv_eslesen.empty:
            bulundu = True
            print(f"📦 ARŞİVDE {len(arsiv_eslesen)} kayıt bulundu (standartlaştırılamadı, DB'ye hiç girmedi):")
            print(arsiv_eslesen.to_string(index=False))
            print()

    if not arsiv_gorseller_df.empty:
        arsiv_gorsel_eslesen = arsiv_gorseller_df[
            arsiv_gorseller_df["dosya_adi"].str.contains(aranan, case=False, na=False)
        ]
        if not arsiv_gorsel_eslesen.empty:
            bulundu = True
            print(f"🖼️📦 ARŞİVLENMİŞ GÖRSELLERDE {len(arsiv_gorsel_eslesen)} dosya bulundu (images/arsiv/products/):")
            print(arsiv_gorsel_eslesen.to_string(index=False))
            print()

    if not bulundu:
        print(f"❌ '{aranan}' ne aktif veritabanında ne de arşivde bulunamadı.")


if __name__ == "__main__":
    main()
