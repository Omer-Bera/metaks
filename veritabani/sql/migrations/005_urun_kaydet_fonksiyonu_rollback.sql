-- =========================================================
-- Migration 005 rollback: urun_kaydet() ve denetim izini geri al
--
-- ⚠️ Denetim izi kolonları DÜŞÜRÜLÜR; içlerindeki "kim ekledi/güncelledi"
-- bilgisi kalıcı olarak kaybolur. Geri almadan önce gerekiyorsa
-- yedekleyin:
--   CREATE TABLE _urunler_denetim_yedek AS
--     SELECT stok_kodu, olusturan_kullanici, guncelleyen_kullanici, updated_at
--     FROM urunler
--     WHERE olusturan_kullanici IS NOT NULL OR guncelleyen_kullanici IS NOT NULL;
--
-- NOT: aktif_mi varsayılanı bilerek eski (TRUE) haline döndürülüyor —
-- rollback'in görevi 005 öncesi duruma dönmek. O varsayılanın
-- katalog_durumu varsayılanıyla çeliştiğini ve varsayılanlara güvenen
-- INSERT'leri patlattığını unutmayın (bkz. 005 başlığı).
-- =========================================================

BEGIN;

DROP FUNCTION IF EXISTS urun_kaydet(
    VARCHAR, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER, VARCHAR, VARCHAR,
    VARCHAR, VARCHAR, NUMERIC, NUMERIC, VARCHAR, NUMERIC, VARCHAR, TEXT,
    INTEGER, BOOLEAN, VARCHAR
);

DROP FUNCTION IF EXISTS urun_sonraki_gorsel_sirasi(VARCHAR);

ALTER TABLE urunler ALTER COLUMN aktif_mi SET DEFAULT TRUE;

ALTER TABLE urunler
    DROP COLUMN IF EXISTS guncelleyen_kullanici,
    DROP COLUMN IF EXISTS olusturan_kullanici;

COMMIT;
