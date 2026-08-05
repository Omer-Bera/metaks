-- Migration 010 hedefli kabul testi. Yalnız disposable/restored veritabanında,
-- migration uygulandıktan sonra çalıştırılır. Bütün örnek satırlar geri alınır.
--
-- 010 UYGULANMAMIŞ bir kopyada bu dosya hata vermelidir (testin sessizce
-- geçmediğinin kanıtı): ilk yapısal denetim lak_mi kolonunu bulamaz.
\set ON_ERROR_STOP on
BEGIN;

-- =========================================================
-- A) Yapısal denetimler: kolonlar, kısıt, indeks, fonksiyonlar
-- =========================================================
DO $$
DECLARE
    v_adet INTEGER;
    v_def TEXT;
    v_pred TEXT;
BEGIN
    -- A1) Üç yeni kolon: BOOLEAN, NOT NULL, DEFAULT FALSE
    SELECT count(*) INTO v_adet
    FROM information_schema.columns
    WHERE table_name = 'stok_kalemleri'
      AND column_name IN ('lak_mi', 'vernik_mi', 'iscilik_mi')
      AND data_type = 'boolean'
      AND is_nullable = 'NO'
      AND column_default = 'false';
    IF v_adet <> 3 THEN
        RAISE EXCEPTION 'A1: lak_mi/vernik_mi/iscilik_mi kolonları BOOLEAN NOT NULL DEFAULT FALSE değil (bulunan: %).', v_adet;
    END IF;

    -- A2) Üç kolonun da belirsizlik uyarısını taşıyan yorumu olmalı
    SELECT count(*) INTO v_adet
    FROM pg_attribute a
    WHERE a.attrelid = 'stok_kalemleri'::regclass
      AND a.attname IN ('lak_mi', 'vernik_mi', 'iscilik_mi')
      AND col_description(a.attrelid, a.attnum) LIKE '%BELIRSIZ%';
    IF v_adet <> 3 THEN
        RAISE EXCEPTION 'A2: Yeni kolonlarda miras/BELIRSIZ belirsizliğini anlatan yorum eksik (bulunan: %).', v_adet;
    END IF;

    -- A3) montaj_durumu CHECK'i yeni değer kümesini taşımalı
    SELECT pg_get_constraintdef(oid) INTO v_def
    FROM pg_constraint
    WHERE conrelid = 'stok_kalemleri'::regclass
      AND conname = 'stok_kalemleri_montaj_durumu_check';
    IF v_def IS NULL OR v_def LIKE '%HAM%' OR v_def NOT LIKE '%DEMONTE%' THEN
        RAISE EXCEPTION 'A3: montaj_durumu CHECK''i DEMONTE''ye geçmemiş: %', COALESCE(v_def, '<kısıt yok>');
    END IF;

    -- A4) Tekillik indeksi üç yeni kolonu kapsamalı, kısmi koşulu korumalı
    SELECT pg_get_indexdef(indexrelid), pg_get_expr(indpred, indrelid)
    INTO v_def, v_pred
    FROM pg_index WHERE indexrelid = 'uq_stok_kalemleri_nitelik'::regclass;
    IF v_def NOT LIKE '%lak_mi%' OR v_def NOT LIKE '%vernik_mi%'
       OR v_def NOT LIKE '%iscilik_mi%' THEN
        RAISE EXCEPTION 'A4: uq_stok_kalemleri_nitelik üç yeni kolonu kapsamıyor: %', v_def;
    END IF;
    IF v_pred IS NULL OR v_pred NOT LIKE '%TANIMLI%' THEN
        RAISE EXCEPTION 'A4: uq_stok_kalemleri_nitelik kısmi indeks koşulunu kaybetmiş: %', COALESCE(v_pred, '<koşulsuz>');
    END IF;
    IF v_def NOT LIKE '%boya_renk_id%' OR v_def NOT LIKE '%mine_renk_id%' THEN
        RAISE EXCEPTION 'A4: Boya/mine rengi tekillik indeksinden düşmüş: %', v_def;
    END IF;

    -- A5) Eski 6 parametreli gövde rollback için saklanmış olmalı
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = 'stok_kalemi_kaydet_v008'
    ) THEN
        RAISE EXCEPTION 'A5: stok_kalemi_kaydet_v008 yok; rollback eski gövdeyi geri getiremez.';
    END IF;

    -- A6) 'ham' kaplaması pasife alınmış ama SİLİNMEMİŞ olmalı
    SELECT count(*) INTO v_adet FROM kaplamalar WHERE lower(btrim(kaplama_adi)) = 'ham';
    IF v_adet <> 1 THEN
        RAISE EXCEPTION 'A6: "ham" kaplaması silinmiş veya çoğalmış (bulunan: %).', v_adet;
    END IF;
    IF EXISTS (SELECT 1 FROM kaplamalar WHERE lower(btrim(kaplama_adi)) = 'ham' AND aktif_mi) THEN
        RAISE EXCEPTION 'A6: "ham" kaplaması hâlâ aktif.';
    END IF;

    -- A7) Uyumluluk sarmalayıcısında 'HAM' literali kalmamalı
    SELECT p.prosrc INTO v_def
    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname = 'stok_hareketi_kaydet';
    IF v_def LIKE '%''HAM''%' THEN
        RAISE EXCEPTION 'A7: stok_hareketi_kaydet gövdesinde hâlâ ''HAM'' literali var.';
    END IF;
END;
$$;

-- =========================================================
-- B) Davranış denetimleri
-- =========================================================
DO $$
DECLARE
    v_urun VARCHAR;
    v_kaplama INTEGER;
    v_ham_kaplama INTEGER;
    v_id_a BIGINT;
    v_id_b BIGINT;
    v_sku_a VARCHAR;
    v_sku_b VARCHAR;
    v_adet INTEGER;
    v_miras_once INTEGER;
    v_sonuc RECORD;
BEGIN
    SELECT sk.urun_kodu INTO v_urun
    FROM stok_kalemleri sk
    WHERE sk.nitelik_durumu = 'BELIRSIZ' AND sk.aktif_mi
    ORDER BY sk.stok_kalemi_id LIMIT 1;
    SELECT kaplama_id INTO v_kaplama
    FROM kaplamalar WHERE aktif_mi AND lower(btrim(kaplama_adi)) <> 'ham'
    ORDER BY kaplama_id LIMIT 1;
    SELECT kaplama_id INTO v_ham_kaplama
    FROM kaplamalar WHERE lower(btrim(kaplama_adi)) = 'ham';
    IF v_urun IS NULL OR v_kaplama IS NULL OR v_ham_kaplama IS NULL THEN
        RAISE EXCEPTION 'Test için bir miras SKU, bir aktif kaplama ve "ham" kaplama satırı gerekir.';
    END IF;

    -- -----------------------------------------------------
    -- B1) 'HAM' montaj hali reddedilir, 'DEMONTE' kabul edilir
    -- -----------------------------------------------------
    BEGIN
        PERFORM * FROM stok_kalemi_kaydet(
            v_urun, v_kaplama, NULL, NULL, 'HAM', FALSE, FALSE, FALSE, 'migration-test'
        );
        RAISE EXCEPTION 'B1: HAM montaj hali kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'B1: HAM montaj hali kabul edildi.' THEN RAISE; END IF;
    END;

    SELECT * INTO v_sonuc FROM stok_kalemi_kaydet(
        v_urun, v_kaplama, NULL, NULL, 'DEMONTE', FALSE, FALSE, FALSE, 'migration-test'
    );
    v_id_a := v_sonuc.stok_kalemi_id;
    v_sku_a := v_sonuc.sku_kodu;
    IF v_id_a IS NULL OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B1: DEMONTE montaj hali yeni SKU olarak kabul edilmedi.';
    END IF;
    IF (SELECT montaj_durumu FROM stok_kalemleri WHERE stok_kalemi_id = v_id_a) <> 'DEMONTE' THEN
        RAISE EXCEPTION 'B1: Oluşan SKU DEMONTE olarak kaydedilmedi.';
    END IF;

    -- CHECK kısıtı doğrudan INSERT'te de 'HAM'ı reddetmeli
    BEGIN
        INSERT INTO stok_kalemleri (sku_kodu, urun_kodu, nitelik_durumu, montaj_durumu)
        VALUES ('M010-HAM-CHECK', v_urun, 'TANIMLI', 'HAM');
        RAISE EXCEPTION 'B1: CHECK kısıtı HAM değerini kabul etti.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'B1: CHECK kısıtı HAM değerini kabul etti.' THEN RAISE; END IF;
    END;

    -- -----------------------------------------------------
    -- B2) Aynı kombinasyon ikinci kez: atlandi=TRUE, AYNI SKU
    --     (sonraki faz fason iş emrinde hedef SKU'yu buna dayanarak türetiyor)
    -- -----------------------------------------------------
    SELECT * INTO v_sonuc FROM stok_kalemi_kaydet(
        v_urun, v_kaplama, NULL, NULL, 'DEMONTE', FALSE, FALSE, FALSE, 'migration-test'
    );
    IF NOT v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B2: Aynı nitelik kombinasyonu ikinci kez yeni SKU açtı.';
    END IF;
    IF v_sonuc.stok_kalemi_id <> v_id_a OR v_sonuc.sku_kodu <> v_sku_a THEN
        RAISE EXCEPTION 'B2: atlandi=TRUE dönerken mevcut SKU''nun kendisi dönmedi.';
    END IF;

    -- -----------------------------------------------------
    -- B3) Yalnız lak_mi farkı AYRI SKU açabilmeli
    -- -----------------------------------------------------
    SELECT * INTO v_sonuc FROM stok_kalemi_kaydet(
        v_urun, v_kaplama, NULL, NULL, 'DEMONTE', TRUE, FALSE, FALSE, 'migration-test'
    );
    IF v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B3: Yalnız lak farkı olan kombinasyon mevcut SKU''ya eşlendi.';
    END IF;
    v_id_b := v_sonuc.stok_kalemi_id;
    v_sku_b := v_sonuc.sku_kodu;
    IF v_id_b = v_id_a OR v_sku_b = v_sku_a THEN
        RAISE EXCEPTION 'B3: Lak farkı ayrı SKU üretmedi.';
    END IF;

    -- Aynısı vernik ve işçilik için de geçerli olmalı
    SELECT * INTO v_sonuc FROM stok_kalemi_kaydet(
        v_urun, v_kaplama, NULL, NULL, 'DEMONTE', FALSE, TRUE, FALSE, 'migration-test'
    );
    IF v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B3: Yalnız vernik farkı olan kombinasyon mevcut SKU''ya eşlendi.';
    END IF;
    SELECT * INTO v_sonuc FROM stok_kalemi_kaydet(
        v_urun, v_kaplama, NULL, NULL, 'DEMONTE', FALSE, FALSE, TRUE, 'migration-test'
    );
    IF v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B3: Yalnız işçilik farkı olan kombinasyon mevcut SKU''ya eşlendi.';
    END IF;

    SELECT count(*) INTO v_adet
    FROM stok_kalemleri
    WHERE urun_kodu = v_urun AND nitelik_durumu = 'TANIMLI'
      AND kaplama_id = v_kaplama AND montaj_durumu = 'DEMONTE';
    IF v_adet <> 4 THEN
        RAISE EXCEPTION 'B3: Dört ayrı lak/vernik/işçilik kombinasyonu beklenirken % SKU var.', v_adet;
    END IF;

    -- -----------------------------------------------------
    -- B4) Tekillik indeksi TANIMLI satırlarda gerçekten uyguluyor
    -- -----------------------------------------------------
    BEGIN
        INSERT INTO stok_kalemleri (
            sku_kodu, urun_kodu, nitelik_durumu, kaplama_id,
            montaj_durumu, lak_mi, vernik_mi, iscilik_mi
        ) VALUES (
            'M010-CAKISMA', v_urun, 'TANIMLI', v_kaplama,
            'DEMONTE', TRUE, FALSE, FALSE
        );
        RAISE EXCEPTION 'B4: Tekillik indeksi aynı kombinasyonu ikinci kez kabul etti.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'B4: Tekillik indeksi aynı kombinasyonu ikinci kez kabul etti.' THEN RAISE; END IF;
    END;

    -- -----------------------------------------------------
    -- B5) nitelik_durumu='BELIRSIZ' satırlar tekillik indeksine GİRMİYOR
    --     Üç satırın da nitelik demeti birebir aynı; kısmi indeks kapsamadığı
    --     için ikisi de yazılabilmeli.
    -- -----------------------------------------------------
    SELECT count(*) INTO v_miras_once
    FROM stok_kalemleri WHERE urun_kodu = v_urun AND nitelik_durumu = 'BELIRSIZ';

    INSERT INTO stok_kalemleri (
        sku_kodu, urun_kodu, nitelik_durumu, montaj_durumu,
        lak_mi, vernik_mi, iscilik_mi
    ) VALUES
        ('M010-BELIRSIZ-A', v_urun, 'BELIRSIZ', 'BELIRSIZ', FALSE, FALSE, FALSE),
        ('M010-BELIRSIZ-B', v_urun, 'BELIRSIZ', 'BELIRSIZ', FALSE, FALSE, FALSE);

    SELECT count(*) INTO v_adet
    FROM stok_kalemleri WHERE urun_kodu = v_urun AND nitelik_durumu = 'BELIRSIZ';
    IF v_adet <> v_miras_once + 2 THEN
        RAISE EXCEPTION 'B5: Aynı nitelik demetli BELIRSIZ satırlar yazılamadı (% -> %).', v_miras_once, v_adet;
    END IF;

    -- -----------------------------------------------------
    -- B6) NULL nitelik reddedilir (TANIMLI SKU belirsiz nitelik taşıyamaz)
    -- -----------------------------------------------------
    BEGIN
        PERFORM * FROM stok_kalemi_kaydet(
            v_urun, v_kaplama, NULL, NULL, 'MONTE', NULL, FALSE, FALSE, 'migration-test'
        );
        RAISE EXCEPTION 'B6: NULL lak niteliği kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'B6: NULL lak niteliği kabul edildi.' THEN RAISE; END IF;
    END;

    -- -----------------------------------------------------
    -- B7) Pasife alınmış 'ham' kaplaması yeni SKU'da kullanılamaz
    -- -----------------------------------------------------
    BEGIN
        PERFORM * FROM stok_kalemi_kaydet(
            v_urun, v_ham_kaplama, NULL, NULL, 'DEMONTE', FALSE, FALSE, FALSE, 'migration-test'
        );
        RAISE EXCEPTION 'B7: Pasif "ham" kaplamasıyla SKU açılabildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'B7: Pasif "ham" kaplamasıyla SKU açılabildi.' THEN RAISE; END IF;
    END;

    -- -----------------------------------------------------
    -- B8) Eski 6 parametreli imza artık çağrılamaz
    --     (varsayılansız yeni imza sessiz "laksız" kaydını engelliyor)
    -- -----------------------------------------------------
    BEGIN
        PERFORM * FROM stok_kalemi_kaydet(
            v_urun, v_kaplama, NULL, NULL, 'MONTE', 'migration-test'
        );
        RAISE EXCEPTION 'B8: Eski 6 parametreli imza hâlâ çağrılabiliyor.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'B8: Eski 6 parametreli imza hâlâ çağrılabiliyor.' THEN RAISE; END IF;
    END;

    -- -----------------------------------------------------
    -- B9) Boya/mine rengi hâlâ kimliğin parçası (ikili niteliğe indirilmedi)
    -- -----------------------------------------------------
    SELECT * INTO v_sonuc FROM stok_kalemi_kaydet(
        v_urun, v_kaplama, 'M010-BOYA', NULL, 'DEMONTE', FALSE, FALSE, FALSE, 'migration-test'
    );
    IF v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B9: Yalnız boya rengi farkı olan kombinasyon mevcut SKU''ya eşlendi.';
    END IF;
    IF (SELECT boya_renk_id FROM stok_kalemleri WHERE stok_kalemi_id = v_sonuc.stok_kalemi_id) IS NULL THEN
        RAISE EXCEPTION 'B9: Boya rengi SKU''ya yazılmadı.';
    END IF;
END;
$$;

ROLLBACK;
