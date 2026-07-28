from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extensions import cursor as PgCursor


BASE_DIR = Path(__file__).resolve().parent
EXCEL_DOSYASI = BASE_DIR / "temiz_urunler_final.xlsx"

DB_NAME = "depo_sistemi"
DB_USER = "depo_admin"
DB_PASSWORD = "supergizlisifre"
DB_HOST = "localhost"
DB_PORT = 5433


def temiz_metin(value: Any) -> str | None:
    if value is None:
        return None

    metin = str(value).strip()

    if metin.lower() in {
        "",
        "?",
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


def temiz_sayi(value: Any) -> float | None:
    metin = temiz_metin(value)

    if metin is None:
        return None

    metin = metin.replace(",", ".")

    try:
        return float(metin)
    except (TypeError, ValueError):
        return None


def temiz_tamsayi(
    value: Any,
    varsayilan: int = 0,
) -> int:
    sayi = temiz_sayi(value)

    if sayi is None:
        return varsayilan

    return int(sayi)


def temiz_boolean(
    value: Any,
    varsayilan: bool,
) -> bool:
    if isinstance(value, bool):
        return value

    metin = temiz_metin(value)

    if metin is None:
        return varsayilan

    dogru_degerler = {
        "true",
        "1",
        "evet",
        "e",
        "yes",
        "y",
    }

    yanlis_degerler = {
        "false",
        "0",
        "hayır",
        "hayir",
        "h",
        "no",
        "n",
    }

    normal = metin.lower()

    if normal in dogru_degerler:
        return True

    if normal in yanlis_degerler:
        return False

    return varsayilan


def gerekli_kolonlari_kontrol_et(
    df: pd.DataFrame,
) -> None:
    gerekli_kolonlar = {
        "ÜRÜN STOK KODU",
        "ÜRÜN KATEGORİ GRUBU",
        "ÜRÜN TİPİ",
        "ANA_STOK_KODU",
        "ÜRÜN AÇIKLAMASI",
    }

    eksik_kolonlar = gerekli_kolonlar.difference(
        df.columns
    )

    if eksik_kolonlar:
        raise ValueError(
            "Excel dosyasında gerekli kolonlar bulunamadı: "
            + ", ".join(sorted(eksik_kolonlar))
        )


def urun_tiplerini_kontrol_et(
    df: pd.DataFrame,
) -> None:
    izin_verilen_tipler = {
        "ANA_URUN",
        "ALT_PARCA",
        "VARYANT",
    }

    tipler = {
        tip
        for tip in df["ÜRÜN TİPİ"]
        .apply(temiz_metin)
        .dropna()
        .tolist()
    }

    gecersiz_tipler = tipler.difference(
        izin_verilen_tipler
    )

    if gecersiz_tipler:
        raise ValueError(
            "Geçersiz ürün tipleri bulundu: "
            + ", ".join(sorted(gecersiz_tipler))
        )


def parent_iliskilerini_kontrol_et(
    df: pd.DataFrame,
) -> None:
    stok_kodlari = {
        kod
        for kod in df["ÜRÜN STOK KODU"]
        .apply(temiz_metin)
        .dropna()
        .tolist()
    }

    eksik_parentlar: list[str] = []

    for _, row in df.iterrows():
        urun_tipi = (
            temiz_metin(row.get("ÜRÜN TİPİ"))
            or "ANA_URUN"
        )

        parent = temiz_metin(
            row.get("ANA_STOK_KODU")
        )

        if urun_tipi in {"ALT_PARCA", "VARYANT"}:
            if parent is None:
                stok_kodu = temiz_metin(
                    row.get("ÜRÜN STOK KODU")
                )

                eksik_parentlar.append(
                    f"{stok_kodu}: parent boş"
                )

            elif parent not in stok_kodlari:
                stok_kodu = temiz_metin(
                    row.get("ÜRÜN STOK KODU")
                )

                eksik_parentlar.append(
                    f"{stok_kodu}: parent bulunamadı ({parent})"
                )

    if eksik_parentlar:
        raise ValueError(
            "Parent ilişkilerinde hata var:\n"
            + "\n".join(eksik_parentlar)
        )


def benzersiz_stok_kodlarini_kontrol_et(
    df: pd.DataFrame,
) -> None:
    stoklar = df["ÜRÜN STOK KODU"].apply(
        temiz_metin
    )

    tekrarlar = stoklar[
        stoklar.notna()
        & stoklar.duplicated(keep=False)
    ]

    if not tekrarlar.empty:
        kodlar = sorted(tekrarlar.unique().tolist())

        raise ValueError(
            "Excel dosyasında tekrar eden stok kodları var: "
            + ", ".join(kodlar)
        )


def kategorileri_yukle(
    cur: PgCursor,
    df: pd.DataFrame,
) -> dict[str, int]:
    kategoriler = (
        df["ÜRÜN KATEGORİ GRUBU"]
        .apply(temiz_metin)
        .dropna()
        .unique()
        .tolist()
    )

    for kategori_adi in kategoriler:
        cur.execute(
            """
            INSERT INTO kategoriler (
                kategori_adi
            )
            VALUES (%s)
            ON CONFLICT (kategori_adi)
            DO UPDATE SET
                aktif_mi = TRUE;
            """,
            (kategori_adi,),
        )

    cur.execute(
        """
        SELECT
            kategori_adi,
            kategori_id
        FROM kategoriler;
        """
    )

    return dict(cur.fetchall())


def urunleri_yukle(
    cur: PgCursor,
    dataframe: pd.DataFrame,
    kategori_haritasi: dict[str, int],
) -> tuple[int, int]:
    islenen = 0
    atlanan = 0

    for _, row in dataframe.iterrows():
        stok_kodu = temiz_metin(
            row.get("ÜRÜN STOK KODU")
        )

        if stok_kodu is None:
            atlanan += 1
            continue

        kategori_adi = temiz_metin(
            row.get("ÜRÜN KATEGORİ GRUBU")
        )

        kategori_id = (
            kategori_haritasi.get(kategori_adi)
            if kategori_adi is not None
            else None
        )

        parent_stok_kodu = temiz_metin(
            row.get("ANA_STOK_KODU")
        )

        urun_tipi = (
            temiz_metin(row.get("ÜRÜN TİPİ"))
            or "ANA_URUN"
        )

        varyant_adi = temiz_metin(
            row.get("VARYANT_ADI")
        )

        kalip_versiyonu = temiz_metin(
            row.get("KALIP_VERSIYONU")
        )

        aciklama = temiz_metin(
            row.get("ÜRÜN AÇIKLAMASI")
        )

        olcu_mm = temiz_sayi(
            row.get("olcu_mm")
        )

        boy_ligne = temiz_sayi(
            row.get("boy_ligne")
        )

        gramaj_gr = temiz_sayi(
            row.get("ÜRÜN GRAMI")
        )

        boya_mine = temiz_metin(
            row.get("BOYA_MİNE")
        )

        montaj_durumu = temiz_metin(
            row.get("MONTAJ_DURUMU")
        )

        kritik_stok_esigi = temiz_tamsayi(
            row.get("KRİTİK_STOK_EŞİĞİ"),
            varsayilan=0,
        )

        stok_takip_edilsin_mi = temiz_boolean(
            row.get("STOK_TAKIP_EDILSIN_MI"),
            varsayilan=True,
        )

        aktif_mi = temiz_boolean(
            row.get("AKTIF_MI"),
            varsayilan=True,
        )

        cur.execute(
            """
            INSERT INTO urunler (
                stok_kodu,
                kategori_id,
                parent_stok_kodu,
                urun_tipi,
                varyant_adi,
                kalip_versiyonu,
                olcu_mm,
                boy_ligne,
                boya_mine,
                gramaj_gr,
                montaj_durumu,
                aciklama,
                kritik_stok_esigi,
                stok_takip_edilsin_mi,
                aktif_mi,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (stok_kodu)
            DO UPDATE SET
                kategori_id =
                    EXCLUDED.kategori_id,
                parent_stok_kodu =
                    EXCLUDED.parent_stok_kodu,
                urun_tipi =
                    EXCLUDED.urun_tipi,
                varyant_adi =
                    EXCLUDED.varyant_adi,
                kalip_versiyonu =
                    EXCLUDED.kalip_versiyonu,
                olcu_mm =
                    EXCLUDED.olcu_mm,
                boy_ligne =
                    EXCLUDED.boy_ligne,
                boya_mine =
                    EXCLUDED.boya_mine,
                gramaj_gr =
                    EXCLUDED.gramaj_gr,
                montaj_durumu =
                    EXCLUDED.montaj_durumu,
                aciklama =
                    EXCLUDED.aciklama,
                kritik_stok_esigi =
                    EXCLUDED.kritik_stok_esigi,
                stok_takip_edilsin_mi =
                    EXCLUDED.stok_takip_edilsin_mi,
                aktif_mi =
                    EXCLUDED.aktif_mi,
                updated_at =
                    CURRENT_TIMESTAMP;
            """,
            (
                stok_kodu,
                kategori_id,
                parent_stok_kodu,
                urun_tipi,
                varyant_adi,
                kalip_versiyonu,
                olcu_mm,
                boy_ligne,
                boya_mine,
                gramaj_gr,
                montaj_durumu,
                aciklama,
                kritik_stok_esigi,
                stok_takip_edilsin_mi,
                aktif_mi,
            ),
        )

        islenen += 1

    return islenen, atlanan


def main() -> None:
    print(
        "🚀 Final ürün verileri "
        "veritabanına yükleniyor..."
    )

    if not EXCEL_DOSYASI.exists():
        raise FileNotFoundError(
            f"Excel dosyası bulunamadı: "
            f"{EXCEL_DOSYASI}"
        )

    df = pd.read_excel(EXCEL_DOSYASI)

    gerekli_kolonlari_kontrol_et(df)
    urun_tiplerini_kontrol_et(df)
    benzersiz_stok_kodlarini_kontrol_et(df)
    parent_iliskilerini_kontrol_et(df)

    conn: PgConnection = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    TRUNCATE TABLE
                        urun_gorselleri,
                        stok_hareketleri,
                        urunler,
                        kategoriler
                    RESTART IDENTITY CASCADE;
                    """
                )

                kategori_haritasi = kategorileri_yukle(
                    cur,
                    df,
                )

                print(
                    f"✅ {len(kategori_haritasi)} kategori "
                    "veritabanına yüklendi."
                )

                ana_urunler = df[
                    df["ÜRÜN TİPİ"].apply(
                        temiz_metin
                    ) == "ANA_URUN"
                ].copy()

                bagimli_urunler = df[
                    df["ÜRÜN TİPİ"]
                    .apply(temiz_metin)
                    .isin(
                        [
                            "ALT_PARCA",
                            "VARYANT",
                        ]
                    )
                ].copy()

                ana_islenen, ana_atlanan = (
                    urunleri_yukle(
                        cur,
                        ana_urunler,
                        kategori_haritasi,
                    )
                )

                bagimli_islenen, bagimli_atlanan = (
                    urunleri_yukle(
                        cur,
                        bagimli_urunler,
                        kategori_haritasi,
                    )
                )

                toplam_islenen = (
                    ana_islenen
                    + bagimli_islenen
                )

                toplam_atlanan = (
                    ana_atlanan
                    + bagimli_atlanan
                )

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM urunler;
                    """
                )

                sonuc = cur.fetchone()

                if sonuc is None:
                    raise RuntimeError(
                        "Ürün sayısı sorgusundan "
                        "sonuç alınamadı."
                    )

                benzersiz_urun_sayisi = sonuc[0]

                cur.execute(
                    """
                    SELECT
                        urun_tipi,
                        COUNT(*)
                    FROM urunler
                    GROUP BY urun_tipi
                    ORDER BY urun_tipi;
                    """
                )

                tip_sayilari = cur.fetchall()

                print(
                    f"✅ {ana_islenen} ana ürün işlendi."
                )

                print(
                    f"✅ {bagimli_islenen} alt parça/"
                    "varyant işlendi."
                )

                print(
                    f"✅ Toplam {toplam_islenen} "
                    "Excel satırı işlendi."
                )

                print(
                    "✅ Veritabanındaki benzersiz "
                    f"ürün sayısı: "
                    f"{benzersiz_urun_sayisi}"
                )

                if toplam_atlanan:
                    print(
                        "⚠️ Stok kodu boş olan "
                        f"{toplam_atlanan} satır atlandı."
                    )

                print("📊 Ürün tipi dağılımı:")

                for urun_tipi, adet in tip_sayilari:
                    print(
                        f"   {urun_tipi}: {adet}"
                    )

    except Exception:
        conn.rollback()

        print(
            "❌ Yükleme sırasında hata oluştu."
        )

        raise

    finally:
        conn.close()

    print(
        "🎉 Final ürün yükleme işlemi "
        "başarıyla tamamlandı."
    )


if __name__ == "__main__":
    main()