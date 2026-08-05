-- =========================================================
-- Migration 008 rollback
-- Yeni stok belgeleri/SKU/fason nesnelerini kaldırır; urunler ve eski hareket
-- satırları yerinde kalır. Ortak veritabanında yalnız doğrulanmış yedekle kullanın.
-- =========================================================

BEGIN;

DROP TRIGGER IF EXISTS trg_stok_hareketi_degistirilemez ON stok_hareketleri;
DROP FUNCTION IF EXISTS stok_hareketi_degistirilemez();

-- 008 sarmalayıcısını kaldırıp migration sırasında saklanan 007 gövdesini geri al.
DROP FUNCTION IF EXISTS stok_hareketi_kaydet(
    UUID, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER, TEXT, VARCHAR,
    INTEGER, VARCHAR, BOOLEAN, VARCHAR, VARCHAR
);
ALTER FUNCTION stok_hareketi_kaydet_v007(
    UUID, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER, TEXT, VARCHAR,
    INTEGER, VARCHAR, BOOLEAN, VARCHAR, VARCHAR
) RENAME TO stok_hareketi_kaydet;

DROP FUNCTION IF EXISTS stok_islemi_kaydet(
    UUID, VARCHAR, BIGINT, VARCHAR, BIGINT, BIGINT, TEXT, VARCHAR, JSONB
);
DROP FUNCTION IF EXISTS fason_is_emri_kaydet(
    UUID, BIGINT, INTEGER, BIGINT, BIGINT, VARCHAR, INTEGER, DATE, VARCHAR, TEXT, VARCHAR
);
DROP FUNCTION IF EXISTS stok_kalemi_kaydet(VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS is_ortagi_kaydet(VARCHAR, VARCHAR, JSONB, VARCHAR);

DROP VIEW IF EXISTS v_fason_is_emri_ozet;
DROP VIEW IF EXISTS v_stok_urun_ozet;
DROP VIEW IF EXISTS v_stok_bakiye;

ALTER TABLE stok_hareketleri
    DROP COLUMN IF EXISTS stok_islem_id,
    DROP COLUMN IF EXISTS stok_kalemi_id,
    DROP COLUMN IF EXISTS parti_id,
    DROP COLUMN IF EXISTS stok_durumu_kodu;

DROP TABLE IF EXISTS stok_islemleri;
DROP TABLE IF EXISTS stok_islem_nedenleri;
DROP TABLE IF EXISTS fason_is_emirleri;
DROP TABLE IF EXISTS stok_partileri;
DROP TABLE IF EXISTS stok_kalemleri;

ALTER TABLE lokasyonlar DROP COLUMN IF EXISTS is_ortagi_id;

DROP TABLE IF EXISTS is_ortagi_rolleri;
DROP TABLE IF EXISTS is_ortaklari;
DROP TABLE IF EXISTS renkler;
DROP TABLE IF EXISTS stok_durumlari;

COMMIT;
