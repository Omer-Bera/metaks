"""PostgreSQL'deki güncel tabloları (urunler, urun_gorselleri, kategoriler)
tek bir Excel dosyasına aktarır — DB'nin o anki halinin canlı bir görüntüsü.

Diğer tablolar (hammaddeler, kaplamalar, lokasyonlar, stok_hareketleri)
henüz hiçbir script tarafından doldurulmadığı için dahil edilmez.
"""

from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection


BASE_DIR = Path(__file__).resolve().parents[2]
CIKIS_DOSYASI = BASE_DIR / "reports" / "excel" / "veritabani_guncel_durum.xlsx"

DB_NAME = "depo_sistemi"
DB_USER = "depo_admin"
DB_PASSWORD = "supergizlisifre"
DB_HOST = "localhost"
DB_PORT = 5433


def main() -> None:
    conn: PgConnection = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )

    try:
        urunler_df = pd.read_sql(
            """
            SELECT
                u.stok_kodu, k.kategori_adi, u.urun_tipi, u.parent_stok_kodu,
                u.varyant_adi, u.kalip_versiyonu, u.olcu_mm, u.boy_ligne,
                u.boya_mine, u.gramaj_gr, u.montaj_durumu, u.aciklama,
                u.kritik_stok_esigi, u.stok_takip_edilsin_mi, u.aktif_mi,
                u.created_at, u.updated_at
            FROM urunler u
            LEFT JOIN kategoriler k ON k.kategori_id = u.kategori_id
            ORDER BY u.stok_kodu;
            """,
            conn,
        )

        gorseller_df = pd.read_sql(
            """
            SELECT gorsel_id, stok_kodu, dosya_adi, ana_gorsel_mi, sira_no,
                   medya_tipi, aciklama, aktif_mi, olusturma_tarihi
            FROM urun_gorselleri
            ORDER BY stok_kodu, sira_no;
            """,
            conn,
        )

        kategoriler_df = pd.read_sql(
            """
            SELECT k.kategori_id, k.kategori_adi, k.aktif_mi,
                   COUNT(u.stok_kodu) AS urun_sayisi
            FROM kategoriler k
            LEFT JOIN urunler u ON u.kategori_id = k.kategori_id
            GROUP BY k.kategori_id, k.kategori_adi, k.aktif_mi
            ORDER BY urun_sayisi DESC;
            """,
            conn,
        )

        ozet_df = pd.DataFrame(
            [
                {"tablo": "urunler", "satir_sayisi": len(urunler_df)},
                {"tablo": "urun_gorselleri", "satir_sayisi": len(gorseller_df)},
                {"tablo": "kategoriler", "satir_sayisi": len(kategoriler_df)},
                {
                    "tablo": "urunler (görseli olan)",
                    "satir_sayisi": urunler_df["stok_kodu"]
                    .isin(gorseller_df["stok_kodu"])
                    .sum(),
                },
                {
                    "tablo": "urunler (görseli olmayan)",
                    "satir_sayisi": (
                        ~urunler_df["stok_kodu"].isin(gorseller_df["stok_kodu"])
                    ).sum(),
                },
            ]
        )
    finally:
        conn.close()

    with pd.ExcelWriter(CIKIS_DOSYASI, engine="openpyxl") as writer:
        ozet_df.to_excel(writer, sheet_name="Ozet", index=False)
        urunler_df.to_excel(writer, sheet_name="Urunler", index=False)
        gorseller_df.to_excel(writer, sheet_name="Urun_Gorselleri", index=False)
        kategoriler_df.to_excel(writer, sheet_name="Kategoriler", index=False)

    print("✅ Veritabanı güncel durumu dışa aktarıldı.")
    print(ozet_df.to_string(index=False))
    print(f"📄 Dosya: {CIKIS_DOSYASI}")


if __name__ == "__main__":
    main()
