-- =========================================================
-- Migration 001 geri alma (rollback)
-- 001_katalog_durumu.sql'in tersini yapar. Transaction içinde çalışır.
-- =========================================================

BEGIN;

DROP VIEW IF EXISTS v_aktif_urunler;

DROP INDEX IF EXISTS idx_urunler_aciklama_trgm;
DROP INDEX IF EXISTS idx_urunler_katalog_durumu;

ALTER TABLE urunler
    DROP CONSTRAINT IF EXISTS chk_urunler_katalog_durumu_aktif_mi_tutarli;

ALTER TABLE urunler
    DROP COLUMN IF EXISTS katalog_durumu;

-- aktif_mi migration öncesi zaten tüm satırlarda TRUE idi; geri
-- alırken de aynı duruma döndürülür (migration öncesi hiç kullanılmıyordu).
UPDATE urunler SET aktif_mi = TRUE;

-- pg_trgm extension'ı kasıtlı olarak KALDIRILMIYOR — başka bir yerde
-- kullanılıyor olabilir ve extension'ları geri almak riskli/gereksiz.

COMMIT;
