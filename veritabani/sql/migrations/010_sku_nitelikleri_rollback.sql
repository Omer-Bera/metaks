-- =========================================================
-- Migration 010 rollback
--
-- 010'un HEPSİNİ tersine çevirir: sarmalayıcı literali, stok_kalemi_kaydet()
-- imzası, 'ham' kaplamasının aktifliği, montaj_durumu değerleri ('DEMONTE' ->
-- 'HAM'), tekillik indeksinin 008 hâli ve üç yeni kolon.
--
-- VERİ KAYBI UYARISI: lak_mi / vernik_mi / iscilik_mi kolonları DROP edilir.
-- 010 uygulandıktan sonra bu niteliklerle ayrılmış SKU'lar açıldıysa, kolonlar
-- düştüğünde o ayrım kaybolur. Bu yüzden dosya, 008 tekillik anahtarına göre
-- çakışan TANIMLI satır varsa en başta DURUR: iki ayrı SKU'yu sessizce aynı
-- kimliğe indirmek, rollback'in yapabileceği en kötü şeydir.
--
-- ÖNKOŞUL: 010 uygulanmadan önce ölçülen durum (2026-08-06) 'ham'
-- kaplamasının aktif_mi=TRUE olduğuydu; aşağıdaki UPDATE onu koşulsuz olarak
-- TRUE'ya döndürür. 010 dışında bir sebeple pasife alınmış olsaydı bu satır
-- onu yanlışlıkla aktifleştirirdi.
--
-- Ortak veritabanında yalnız doğrulanmış yedekle kullanın.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 0) Önkoşul: 008 tekillik anahtarına göre çakışma var mı?
-- ---------------------------------------------------------
DO $$
DECLARE
    v_cakisan INTEGER;
BEGIN
    SELECT count(*) INTO v_cakisan FROM (
        SELECT 1
        FROM stok_kalemleri
        WHERE nitelik_durumu = 'TANIMLI'
        GROUP BY urun_kodu,
                 COALESCE(kaplama_id, -1),
                 COALESCE(boya_renk_id, -1),
                 COALESCE(mine_renk_id, -1),
                 montaj_durumu
        HAVING count(*) > 1
    ) x;
    IF v_cakisan > 0 THEN
        RAISE EXCEPTION
            'Rollback durduruldu: yalnız lak/vernik/işçilik farkıyla ayrılan % kimlik grubu var. Kolonlar düşürülürse bu SKU''lar aynı kimliğe iner. Önce bu varyantları elle birleştirin veya pasife alın.',
            v_cakisan;
    END IF;
END;
$$;

-- ---------------------------------------------------------
-- 1) Uyumluluk sarmalayıcısı: montaj eşleştirmesi 'DEMONTE' -> 'HAM'
--    Gövde 008'dekiyle birebir aynıdır.
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION stok_hareketi_kaydet(
    p_istemci_islem_kimligi UUID,
    p_stok_kodu VARCHAR,
    p_islem_tipi VARCHAR,
    p_miktar INTEGER,
    p_kaynak_lokasyon_id INTEGER DEFAULT NULL,
    p_hedef_lokasyon_id INTEGER DEFAULT NULL,
    p_aciklama TEXT DEFAULT NULL,
    p_yapan_kullanici VARCHAR DEFAULT NULL,
    p_kaplama_id INTEGER DEFAULT NULL,
    p_kaplama_cesidi VARCHAR DEFAULT NULL,
    p_montaj BOOLEAN DEFAULT NULL,
    p_boya VARCHAR DEFAULT NULL,
    p_mine VARCHAR DEFAULT NULL
) RETURNS TABLE (hareket_id BIGINT, uygulanan_miktar INTEGER, atlandi BOOLEAN, mesaj TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_sku_id BIGINT;
    v_islem_id BIGINT;
    v_hareket_sayisi INTEGER;
    v_atlandi BOOLEAN;
    v_mesaj TEXT;
    v_uuid UUID;
BEGIN
    v_uuid := COALESCE(
        p_istemci_islem_kimligi,
        (
            substr(md5(clock_timestamp()::TEXT || random()::TEXT), 1, 8) || '-' ||
            substr(md5(clock_timestamp()::TEXT || random()::TEXT), 9, 4) || '-' ||
            substr(md5(clock_timestamp()::TEXT || random()::TEXT), 13, 4) || '-' ||
            substr(md5(clock_timestamp()::TEXT || random()::TEXT), 17, 4) || '-' ||
            substr(md5(clock_timestamp()::TEXT || random()::TEXT), 21, 12)
        )::UUID
    );

    SELECT sk.stok_kalemi_id INTO v_sku_id
    FROM stok_kalemleri sk
    LEFT JOIN renkler br ON br.renk_id = sk.boya_renk_id
    LEFT JOIN renkler mr ON mr.renk_id = sk.mine_renk_id
    WHERE sk.urun_kodu = p_stok_kodu AND sk.aktif_mi
      AND (
        (p_kaplama_id IS NULL AND p_montaj IS NULL
         AND NULLIF(btrim(p_boya), '') IS NULL AND NULLIF(btrim(p_mine), '') IS NULL
         AND sk.nitelik_durumu = 'BELIRSIZ')
        OR
        (sk.nitelik_durumu = 'TANIMLI'
         AND sk.kaplama_id IS NOT DISTINCT FROM p_kaplama_id
         AND sk.montaj_durumu = CASE WHEN p_montaj IS TRUE THEN 'MONTE'
                                     WHEN p_montaj IS FALSE THEN 'HAM'
                                     ELSE 'BELIRSIZ' END
         AND lower(br.renk_adi) IS NOT DISTINCT FROM lower(NULLIF(btrim(p_boya), ''))
         AND lower(mr.renk_adi) IS NOT DISTINCT FROM lower(NULLIF(btrim(p_mine), '')))
      )
    ORDER BY (sk.nitelik_durumu = 'BELIRSIZ') DESC
    LIMIT 1;

    IF v_sku_id IS NULL THEN
        RAISE EXCEPTION 'Eski işlem alanlarıyla eşleşen SKU yok; yeni Stok işlemi ekranından varyant seçin.';
    END IF;

    SELECT sonuc.stok_islem_id, sonuc.hareket_sayisi, sonuc.atlandi, sonuc.mesaj
    INTO v_islem_id, v_hareket_sayisi, v_atlandi, v_mesaj
    FROM stok_islemi_kaydet(
        v_uuid, 'MIRAS_HAREKET', NULL, NULL, NULL, NULL, p_aciklama,
        p_yapan_kullanici,
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku_id,
            'islem_tipi', p_islem_tipi,
            'miktar', p_miktar,
            'kaynak_lokasyon_id', p_kaynak_lokasyon_id,
            'hedef_lokasyon_id', p_hedef_lokasyon_id,
            'stok_durumu_kodu', 'SERBEST'
        ))
    ) sonuc;

    SELECT sh.hareket_id, sh.miktar INTO hareket_id, uygulanan_miktar
    FROM stok_hareketleri sh
    WHERE sh.stok_islem_id = v_islem_id
    ORDER BY sh.hareket_id
    LIMIT 1;
    atlandi := v_atlandi;
    mesaj := v_mesaj;
    RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------
-- 2) stok_kalemi_kaydet(): 010 imzası düşer, 008 gövdesi adını geri alır
-- ---------------------------------------------------------
DROP FUNCTION IF EXISTS stok_kalemi_kaydet(
    VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, BOOLEAN, BOOLEAN, BOOLEAN, VARCHAR
);
ALTER FUNCTION stok_kalemi_kaydet_v008(
    VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR
) RENAME TO stok_kalemi_kaydet;

-- ---------------------------------------------------------
-- 3) kaplamalar: 'ham' satırı yeniden aktif
-- ---------------------------------------------------------
UPDATE kaplamalar SET aktif_mi = TRUE WHERE lower(btrim(kaplama_adi)) = 'ham';

-- ---------------------------------------------------------
-- 4) montaj_durumu: 'DEMONTE' -> 'HAM', 008 CHECK'i geri
-- ---------------------------------------------------------
ALTER TABLE stok_kalemleri
    DROP CONSTRAINT stok_kalemleri_montaj_durumu_check;

UPDATE stok_kalemleri SET montaj_durumu = 'HAM' WHERE montaj_durumu = 'DEMONTE';

ALTER TABLE stok_kalemleri
    ADD CONSTRAINT stok_kalemleri_montaj_durumu_check
    CHECK (montaj_durumu IN ('BELIRSIZ', 'HAM', 'YARI_MONTE', 'MONTE'));

-- ---------------------------------------------------------
-- 5) Tekillik indeksi 008 hâline döner, üç kolon düşer
--    Kısmi indeks koşulu burada da aynen korunur.
-- ---------------------------------------------------------
DROP INDEX uq_stok_kalemleri_nitelik;

ALTER TABLE stok_kalemleri
    DROP COLUMN lak_mi,
    DROP COLUMN vernik_mi,
    DROP COLUMN iscilik_mi;

CREATE UNIQUE INDEX uq_stok_kalemleri_nitelik
    ON stok_kalemleri (
        urun_kodu,
        COALESCE(kaplama_id, -1),
        COALESCE(boya_renk_id, -1),
        COALESCE(mine_renk_id, -1),
        montaj_durumu
    )
    WHERE nitelik_durumu = 'TANIMLI';

COMMIT;
