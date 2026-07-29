-- =========================================================
-- Migration 001: katalog_durumu (aktif/pasif/inceleme ayrımı)
-- Appsmith Ürünler/Katalog sayfası için — bkz. docs/aktif-urun-veri-sozlesmesi.md
--
-- Bu dosya HENÜZ UYGULANMADI. Ortak veritabanına karşı çalıştırmadan
-- önce kullanıcı onayı gerekir (bkz. CLAUDE.md güvenlik notları).
--
-- Geri alma: bu dosyanın sonundaki ROLLBACK bloğuna bakın (ayrı dosya
-- olarak da tutulur: 001_katalog_durumu_rollback.sql).
-- =========================================================

BEGIN;

-- 1) Üç durumlu katalog durumu kolonu. aktif_mi (mevcut, boolean) ile
--    her zaman tutarlı kalması bir CHECK constraint ile garanti edilir;
--    Appsmith'in hızlı filtresi hâlâ aktif_mi üzerinden çalışabilir
--    (mevcut idx_urunler_aktif indeksini yeniden kullanır), katalog_durumu
--    ise "neden pasif/incelemede" bilgisini taşır.
ALTER TABLE urunler
    ADD COLUMN IF NOT EXISTS katalog_durumu VARCHAR(30) NOT NULL DEFAULT 'PASIF'
        CHECK (katalog_durumu IN ('AKTIF', 'PASIF', 'INCELEME_BEKLIYOR'));

ALTER TABLE urunler
    ADD CONSTRAINT chk_urunler_katalog_durumu_aktif_mi_tutarli
    CHECK (
        (katalog_durumu = 'AKTIF' AND aktif_mi = TRUE)
        OR (katalog_durumu <> 'AKTIF' AND aktif_mi = FALSE)
    );

-- 2) Geriye dönük doldurma: doğrulanmış (aktif + ana_gorsel_mi) bir
--    görseli olan ürünler AKTİF, kalanı PASİF. INCELEME_BEKLIYOR şu an
--    hiçbir satıra otomatik atanmıyor — mevcut veri setinde otomatik
--    tespit edilebilen "belirsiz" bir grup yok (bkz. veri sözleşmesi,
--    "Bilinen sınırlamalar"); ileride elle ya da yeni bir kalite
--    kontrolüyle bu duruma taşınacak satırlar için ayrılmış bir değer.
UPDATE urunler u
SET katalog_durumu = 'AKTIF',
    aktif_mi = TRUE
WHERE EXISTS (
    SELECT 1 FROM urun_gorselleri g
    WHERE g.stok_kodu = u.stok_kodu
      AND g.ana_gorsel_mi = TRUE
      AND g.aktif_mi = TRUE
);

UPDATE urunler u
SET katalog_durumu = 'PASIF',
    aktif_mi = FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM urun_gorselleri g
    WHERE g.stok_kodu = u.stok_kodu
      AND g.ana_gorsel_mi = TRUE
      AND g.aktif_mi = TRUE
);

-- 3) Appsmith'in katalog sorgusu için indeks (aktif_mi zaten indeksli;
--    bu, "pasif nedenini" filtreleyecek bir admin/inceleme ekranı için).
CREATE INDEX IF NOT EXISTS idx_urunler_katalog_durumu
    ON urunler(katalog_durumu);

-- 4) Serbest metin arama (ÜRÜN AÇIKLAMASI içinde "içerir" araması) için.
--    stok_kodu için ayrı bir indekse gerek yok — birincil anahtar (btree)
--    zaten "ILIKE 'X%'" tipi önek aramasını hızlı karşılıyor.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_urunler_aciklama_trgm
    ON urunler USING GIN (aciklama gin_trgm_ops);

-- 5) Aktif ürünleri döndüren view — Appsmith'in tek sorgu kaynağı.
--    Tanımı için bkz. docs/aktif-urun-veri-sozlesmesi.md.
CREATE OR REPLACE VIEW v_aktif_urunler AS
SELECT
    u.stok_kodu,
    u.urun_tipi,
    u.parent_stok_kodu,
    u.varyant_adi,
    u.olcu_mm,
    u.boy_ligne,
    u.boya_mine,
    u.gramaj_gr,
    u.montaj_durumu,
    u.aciklama,
    u.kritik_stok_esigi,
    k.kategori_id,
    k.kategori_adi,
    h.hammadde_id,
    h.hammadde_adi,
    kp.kaplama_id,
    kp.kaplama_adi,
    g.dosya_adi AS ana_gorsel_dosya_adi,
    -- Appsmith'te tek bir kolonda çoklu alan arayabilmek için birleşik
    -- metin (csv_guncelle.py'deki arama_metni_olustur() ile aynı fikir).
    lower(
        coalesce(u.stok_kodu, '') || ' ' ||
        coalesce(k.kategori_adi, '') || ' ' ||
        coalesce(h.hammadde_adi, '') || ' ' ||
        coalesce(kp.kaplama_adi, '') || ' ' ||
        coalesce(u.aciklama, '')
    ) AS arama_metni
FROM urunler u
LEFT JOIN kategoriler k ON k.kategori_id = u.kategori_id
LEFT JOIN hammaddeler h ON h.hammadde_id = u.hammadde_id
LEFT JOIN kaplamalar kp ON kp.kaplama_id = u.kaplama_id
LEFT JOIN urun_gorselleri g
    ON g.stok_kodu = u.stok_kodu
   AND g.ana_gorsel_mi = TRUE
   AND g.aktif_mi = TRUE
WHERE u.katalog_durumu = 'AKTIF';

COMMIT;
