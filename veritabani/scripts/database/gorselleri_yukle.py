"""Eşleşen ürün görsellerini urun_gorselleri tablosuna yükler.

Kaynak: reports/excel/gorsel_eslesme_raporu.xlsx -> "Eslesen_Gorseller" sayfası
(scripts/images/gorsel_eslesme_raporu.py tarafından üretilir).

Dosya adlandırma kuralı (gorsel_esle_duzeltilmis_v2.py): "<stok_kodu>_<sira>.<uzanti>".
Sıra numarası dosya adından çıkarılır; sira_no == 1 olan görsel ana görsel
(ana_gorsel_mi) kabul edilir. Bu, urun_gorselleri şemasındaki
"bir ürünün yalnızca bir aktif ana görseli olabilir" kısıtıyla tutarlıdır.

Idempotent: (stok_kodu, dosya_adi) üzerinde ON CONFLICT DO UPDATE kullanır,
tekrar çalıştırmak güvenlidir.
"""

from pathlib import Path
import re
from typing import Any

import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extensions import cursor as PgCursor


BASE_DIR = Path(__file__).resolve().parents[2]
RAPOR_DOSYASI = BASE_DIR / "reports" / "excel" / "gorsel_eslesme_raporu.xlsx"

DB_NAME = "depo_sistemi"
DB_USER = "depo_admin"
DB_PASSWORD = "supergizlisifre"
DB_HOST = "localhost"
DB_PORT = 5433

SIRA_DESENI = re.compile(r"_(\d+)\.[^.]+$")


def temiz_metin(deger: Any) -> str | None:
    if deger is None:
        return None
    metin = str(deger).strip()
    if metin.lower() in {"", "nan", "none", "null", "<na>", "nat"}:
        return None
    if metin.endswith(".0") and metin[:-2].isdigit():
        metin = metin[:-2]
    return metin


def sira_no_cikar(dosya_adi: str) -> int:
    """"<stok_kodu>_<sira>.<uzanti>" değilse (ör. elle yeniden adlandırılmış
    özel görseller: "1805012-ESKI.jpeg") tek görsel varsayılır, sira=1."""
    m = SIRA_DESENI.search(dosya_adi)
    return int(m.group(1)) if m else 1


def main() -> None:
    print("🚀 Ürün görselleri veritabanına yükleniyor...")

    df = pd.read_excel(RAPOR_DOSYASI, sheet_name="Eslesen_Gorseller")
    df["stok_kodu"] = df["stok_kodu"].apply(temiz_metin)
    df["dosya_adi"] = df["dosya_adi"].apply(temiz_metin)
    df = df.dropna(subset=["stok_kodu", "dosya_adi"])
    df["sira_no"] = df["dosya_adi"].apply(sira_no_cikar)
    df["ana_gorsel_mi"] = df["sira_no"] == df.groupby("stok_kodu")["sira_no"].transform("min")

    conn: PgConnection = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )

    islenen = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur: PgCursor
                for _, row in df.iterrows():
                    cur.execute(
                        """
                        INSERT INTO urun_gorselleri (
                            stok_kodu, dosya_adi, ana_gorsel_mi, sira_no, medya_tipi
                        )
                        VALUES (%s, %s, %s, %s, 'URUN_GORSELI')
                        ON CONFLICT (stok_kodu, dosya_adi)
                        DO UPDATE SET
                            ana_gorsel_mi = EXCLUDED.ana_gorsel_mi,
                            sira_no = EXCLUDED.sira_no;
                        """,
                        (row["stok_kodu"], row["dosya_adi"], bool(row["ana_gorsel_mi"]), int(row["sira_no"])),
                    )
                    islenen += 1

                cur.execute("SELECT COUNT(*) FROM urun_gorselleri;")
                toplam = cur.fetchone()[0]

                cur.execute(
                    "SELECT COUNT(*) FROM urun_gorselleri WHERE ana_gorsel_mi = TRUE;"
                )
                ana_gorsel_sayisi = cur.fetchone()[0]

    except Exception:
        conn.rollback()
        print("❌ Yükleme sırasında hata oluştu.")
        raise
    finally:
        conn.close()

    print(f"✅ {islenen} görsel satırı işlendi.")
    print(f"✅ urun_gorselleri tablosundaki toplam satır: {toplam}")
    print(f"✅ Ana görsele sahip ürün sayısı: {ana_gorsel_sayisi}")
    print("🎉 Görsel yükleme işlemi tamamlandı.")


if __name__ == "__main__":
    main()
