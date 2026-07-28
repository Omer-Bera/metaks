"""Hızlı arama için veritabanı + arşiv verilerinin CSV kopyalarını üretir/günceller.

Bu script her çalıştığında CSV'leri o anki DB durumuna göre yeniden yazar
(idempotent). scripts/database/urun_ara.py bu CSV'ler üzerinde arama yapar.

Üretilen dosyalar:
  data/processed/urunler.csv              (aktif veritabanı - urunler tablosu)
  data/processed/urun_gorselleri.csv      (aktif veritabanı - urun_gorselleri)
  data/reference/arsivlenen_urunler.csv   (arşivlenen ürün satırları, birleşik)
  data/reference/arsivlenen_gorseller.csv (arşivlenen/eşleşmeyen görseller)
"""

from pathlib import Path

import pandas as pd
import psycopg2


BASE_DIR = Path(__file__).resolve().parents[2]

ARSIV_KAYNAK = BASE_DIR / "data" / "reference" / "arsivlenen_eski_urunler.xlsx"

URUNLER_CSV = BASE_DIR / "data" / "processed" / "urunler.csv"
GORSELLER_CSV = BASE_DIR / "data" / "processed" / "urun_gorselleri.csv"
ARSIV_URUNLER_CSV = BASE_DIR / "data" / "reference" / "arsivlenen_urunler.csv"
ARSIV_GORSELLER_CSV = BASE_DIR / "data" / "reference" / "arsivlenen_gorseller.csv"

DB_NAME = "depo_sistemi"
DB_USER = "depo_admin"
DB_PASSWORD = "supergizlisifre"
DB_HOST = "localhost"
DB_PORT = 5433


def db_tablolarini_guncelle() -> None:
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )
    try:
        urunler_df = pd.read_sql(
            """
            SELECT
                u.stok_kodu, k.kategori_adi, u.urun_tipi, u.parent_stok_kodu,
                u.varyant_adi, u.olcu_mm, u.boy_ligne, u.aciklama, u.aktif_mi
            FROM urunler u
            LEFT JOIN kategoriler k ON k.kategori_id = u.kategori_id
            ORDER BY u.stok_kodu;
            """,
            conn,
        )
        gorseller_df = pd.read_sql(
            """
            SELECT stok_kodu, dosya_adi, ana_gorsel_mi, sira_no
            FROM urun_gorselleri
            ORDER BY stok_kodu, sira_no;
            """,
            conn,
        )
    finally:
        conn.close()

    urunler_df.to_csv(URUNLER_CSV, index=False)
    gorseller_df.to_csv(GORSELLER_CSV, index=False)
    print(f"✅ {URUNLER_CSV.name}: {len(urunler_df)} satır")
    print(f"✅ {GORSELLER_CSV.name}: {len(gorseller_df)} satır")


def arsiv_csvlerini_guncelle() -> None:
    if not ARSIV_KAYNAK.exists():
        print(f"⚠️  Arşiv kaynağı bulunamadı, atlanıyor: {ARSIV_KAYNAK}")
        return

    karisik_df = pd.read_excel(ARSIV_KAYNAK, sheet_name="Karisik_Cozulemeyen")
    olcu_df = pd.read_excel(ARSIV_KAYNAK, sheet_name="Olcu_Karmasik")
    stoksuz_df = pd.read_excel(ARSIV_KAYNAK, sheet_name="Stoksuz")
    gorsel_df = pd.read_excel(ARSIV_KAYNAK, sheet_name="Eslesmeyen_Gorseller")

    def arama_metni_olustur(df: pd.DataFrame, kolonlar: list[str]) -> pd.Series:
        mevcut = [k for k in kolonlar if k in df.columns]
        return df[mevcut].apply(
            lambda satir: " | ".join(
                str(deger) for deger in satir if pd.notna(deger)
            ),
            axis=1,
        )

    karisik_out = pd.DataFrame(
        {
            "arama_metni": arama_metni_olustur(
                karisik_df, ["ÜRÜN STOK KODU", "token"]
            ),
            "kaynak": "karisik_cozulemeyen",
            "sebep": karisik_df.get("sebep"),
        }
    )
    olcu_out = pd.DataFrame(
        {
            "arama_metni": arama_metni_olustur(olcu_df, ["ÜRÜN STOK KODU"]),
            "kaynak": "olcu_karmasik",
            "sebep": "birden fazla ölçü/kod, hiç işlenmedi",
        }
    )
    stoksuz_out = pd.DataFrame(
        {
            "arama_metni": arama_metni_olustur(stoksuz_df, ["ÜRÜN STOK KODU"]),
            "kaynak": "stoksuz",
            "sebep": "stok kodu yok",
        }
    )

    arsiv_urunler_df = pd.concat([karisik_out, olcu_out, stoksuz_out], ignore_index=True)
    arsiv_urunler_df.to_csv(ARSIV_URUNLER_CSV, index=False)
    print(f"✅ {ARSIV_URUNLER_CSV.name}: {len(arsiv_urunler_df)} satır")

    gorsel_df.to_csv(ARSIV_GORSELLER_CSV, index=False)
    print(f"✅ {ARSIV_GORSELLER_CSV.name}: {len(gorsel_df)} satır")


def main() -> None:
    print("🚀 CSV dosyaları güncelleniyor...")
    db_tablolarini_guncelle()
    arsiv_csvlerini_guncelle()
    print("🎉 Tamamlandı.")


if __name__ == "__main__":
    main()
