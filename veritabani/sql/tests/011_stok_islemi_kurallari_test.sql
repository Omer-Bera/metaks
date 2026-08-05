-- Migration 011 hedefli kabul testi. Yalnız disposable/restored veritabanında,
-- 010 VE 011 uygulandıktan sonra çalıştırılır. Bütün örnek veri (lokasyonlar,
-- iş ortakları, SKU'lar, hareketler) transaction sonunda geri alınır.
--
-- 010 bağımlılığı: test kendi hedef SKU'sunu 010'un dokuz parametreli
-- `stok_kalemi_kaydet()` imzasıyla açar. Doğrulama turu zaten
-- 010 ileri -> 011 ileri -> bu test -> 011 rollback -> 010 rollback biçimindedir.
--
-- 011 UYGULANMAMIŞ bir kopyada bu dosya hata vermelidir (testin sessizce
-- geçmediğinin kanıtı): karşı tarafsız müşteri iadesi kabul edilir ve B1
-- sentinel'i patlar.
\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    v_urun VARCHAR;
    v_sku BIGINT;
    v_hedef_sku BIGINT;
    v_ic1 INTEGER;
    v_ic2 INTEGER;
    v_fason INTEGER;
    v_fasoncu BIGINT;
    v_num_dolap INTEGER;
    v_numune INTEGER;
    v_musteri BIGINT;
    v_tedarikci BIGINT;
    v_rolsuz BIGINT;
    v_pasif_musteri BIGINT;
    v_kaplama INTEGER;
    v_emir BIGINT;
    v_seed_islem BIGINT;
    v_adet INTEGER;
    v_donen INTEGER;
    v_bakiye INTEGER;
    v_sonuc RECORD;
BEGIN
    -- =====================================================
    -- A) Örnek veri
    -- =====================================================
    SELECT sk.stok_kalemi_id, sk.urun_kodu INTO v_sku, v_urun
    FROM stok_kalemleri sk
    WHERE sk.nitelik_durumu = 'BELIRSIZ' AND sk.aktif_mi AND sk.stoklanabilir_mi
    ORDER BY sk.stok_kalemi_id LIMIT 1;
    SELECT min(lokasyon_id), max(lokasyon_id) INTO v_ic1, v_ic2
    FROM v_lokasyonlar_detay WHERE aktif_mi AND yaprak_mi AND tip = 'DAHILI';
    SELECT ld.lokasyon_id, l.is_ortagi_id INTO v_fason, v_fasoncu
    FROM v_lokasyonlar_detay ld JOIN lokasyonlar l USING (lokasyon_id)
    WHERE ld.aktif_mi AND ld.yaprak_mi AND ld.tip = 'FASON'
      AND l.is_ortagi_id IS NOT NULL LIMIT 1;
    SELECT kaplama_id INTO v_kaplama
    FROM kaplamalar WHERE aktif_mi ORDER BY kaplama_id LIMIT 1;
    IF v_sku IS NULL OR v_ic1 IS NULL OR v_ic2 IS NULL OR v_ic1 = v_ic2
       OR v_fason IS NULL OR v_kaplama IS NULL THEN
        RAISE EXCEPTION 'A: test için bir SKU, iki dahili yaprak, bir fason lokasyonu ve bir aktif kaplama gerekir.';
    END IF;

    -- Canlıda henüz NUMUNE hiyerarşisi yok; test kendi dolabını/rafını kurar.
    -- kok_mu ve ust_kok_mu üretilmiş (GENERATED) kolonlardır, ust_lokasyon_id'den
    -- türerler; elle verilmezler.
    INSERT INTO lokasyonlar (lokasyon_adi, tip, aktif_mi)
    VALUES ('M011 Numune Dolabı', 'NUMUNE', TRUE)
    RETURNING lokasyon_id INTO v_num_dolap;
    INSERT INTO lokasyonlar (lokasyon_adi, tip, aktif_mi, ust_lokasyon_id)
    VALUES ('M011 Raf 1', 'NUMUNE', TRUE, v_num_dolap)
    RETURNING lokasyon_id INTO v_numune;
    IF NOT EXISTS (
        SELECT 1 FROM v_lokasyonlar_detay
        WHERE lokasyon_id = v_numune AND aktif_mi AND yaprak_mi AND tip = 'NUMUNE'
    ) THEN
        RAISE EXCEPTION 'A: numune rafı aktif yaprak olarak kurulamadı.';
    END IF;

    SELECT is_ortagi_id INTO v_musteri FROM is_ortagi_kaydet(
        'M011-MUS', 'Migration 011 müşterisi', '["MUSTERI"]'::jsonb, 'migration-test');
    SELECT is_ortagi_id INTO v_tedarikci FROM is_ortagi_kaydet(
        'M011-TED', 'Migration 011 tedarikçisi', '["TEDARIKCI"]'::jsonb, 'migration-test');
    -- MUSTERI/TEDARIKCI rolü OLMAYAN ortak (yalnız fasoncu rolü var).
    SELECT is_ortagi_id INTO v_rolsuz FROM is_ortagi_kaydet(
        'M011-ROLSUZ', 'Migration 011 rolsüz ortak', '["FASONCU"]'::jsonb, 'migration-test');
    -- Rolü doğru ama PASİF ortak.
    SELECT is_ortagi_kaydet.is_ortagi_id INTO v_pasif_musteri FROM is_ortagi_kaydet(
        'M011-PASIF', 'Migration 011 pasif müşteri', '["MUSTERI"]'::jsonb, 'migration-test');
    UPDATE is_ortaklari SET aktif_mi = FALSE WHERE is_ortagi_id = v_pasif_musteri;

    -- Çıkış testleri için dahili stok tohumu (üretim girişi karşı taraf istemez).
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000001', 'URETIM_GIRIS', NULL,
        'M011-TOHUM', NULL, NULL, 'test tohum', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 500,
            'hedef_lokasyon_id', v_ic1, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    v_seed_islem := v_sonuc.stok_islem_id;
    IF v_sonuc.hareket_sayisi <> 1 THEN
        RAISE EXCEPTION 'A: stok tohumu yazılamadı.';
    END IF;

    -- =====================================================
    -- B) Kural 1 — iadelerde karşı taraf zorunlu ve rollü
    -- =====================================================

    -- B1) Karşı taraf HİÇ verilmemiş müşteri iadesi reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000002', 'MUSTERI_IADE', NULL,
            NULL, NULL, NULL, 'karşı tarafsız iade', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 5,
                'hedef_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'B1: karşı tarafsız müşteri iadesi kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'B1:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%müşteri/tedarikçi seçimi zorunludur%' THEN
            RAISE EXCEPTION 'B1: beklenen karşı taraf hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- B2) MUSTERI rolü OLMAYAN ortakla müşteri iadesi reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000003', 'MUSTERI_IADE', v_rolsuz,
            NULL, NULL, NULL, 'rolsüz iade', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 5,
                'hedef_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'B2: rolsüz ortakla müşteri iadesi kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'B2:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%Müşteri iadesinde aktif bir müşteri seçilmelidir%' THEN
            RAISE EXCEPTION 'B2: beklenen rol hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- B3) Rolü doğru ama PASİF ortakla müşteri iadesi reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000004', 'MUSTERI_IADE', v_pasif_musteri,
            NULL, NULL, NULL, 'pasif müşteri iadesi', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 5,
                'hedef_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'B3: pasif müşteriyle iade kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'B3:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%Müşteri iadesinde aktif bir müşteri seçilmelidir%' THEN
            RAISE EXCEPTION 'B3: beklenen rol hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- B4) Doğru rolle müşteri iadesi GEÇMELİ
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000005', 'MUSTERI_IADE', v_musteri,
        'M011-IADE-1', NULL, NULL, 'geçerli müşteri iadesi', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 7,
            'hedef_lokasyon_id', v_ic1, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B4: doğru rollü müşteri iadesi kaydedilmedi.';
    END IF;

    -- B5) Tedarikçi iadesi MUSTERI rollü ortakla reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000006', 'TEDARIKCI_IADE', v_musteri,
            NULL, NULL, NULL, 'yanlış rollü iade', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 5,
                'kaynak_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'B5: müşteri rollü ortakla tedarikçi iadesi kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'B5:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%Tedarikçi iadesinde aktif bir tedarikçi seçilmelidir%' THEN
            RAISE EXCEPTION 'B5: beklenen rol hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- B6) Doğru rolle tedarikçi iadesi GEÇMELİ
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000007', 'TEDARIKCI_IADE', v_tedarikci,
        'M011-IADE-2', NULL, NULL, 'geçerli tedarikçi iadesi', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 3,
            'kaynak_lokasyon_id', v_ic1, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'B6: doğru rollü tedarikçi iadesi kaydedilmedi.';
    END IF;

    -- =====================================================
    -- C) Kural 2 — amaç ↔ lokasyon tipi
    -- =====================================================

    -- C1) Satış sevkiyatı FASON lokasyonundan reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000008', 'SATIS_SEVKI', v_musteri,
            'M011-SATIS-RED', NULL, NULL, 'fasondan satış', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 1,
                'kaynak_lokasyon_id', v_fason
            ))
        );
        RAISE EXCEPTION 'C1: fason lokasyonundan satış sevkiyatı kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'C1:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%yalnız dahili lokasyondan çıkış yapabilir%' THEN
            RAISE EXCEPTION 'C1: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- C2) Satış sevkiyatı DAHİLİ lokasyondan GEÇMELİ
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000009', 'SATIS_SEVKI', v_musteri,
        'M011-SATIS-1', NULL, NULL, 'dahiliden satış', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 4,
            'kaynak_lokasyon_id', v_ic1, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'C2: dahiliden satış sevkiyatı kaydedilmedi.';
    END IF;

    -- C3) Satın alma kabulü FASON lokasyonuna reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000010', 'SATIN_ALMA_KABUL', v_tedarikci,
            'M011-ALIS-RED', NULL, NULL, 'fasona kabul', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 10,
                'hedef_lokasyon_id', v_fason
            ))
        );
        RAISE EXCEPTION 'C3: fason lokasyonuna satın alma kabulü kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'C3:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%yalnız dahili lokasyona giriş yapabilir%' THEN
            RAISE EXCEPTION 'C3: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- C4) Satın alma kabulü DAHİLİ lokasyona GEÇMELİ
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000011', 'SATIN_ALMA_KABUL', v_tedarikci,
        'M011-ALIS-1', NULL, NULL, 'dahiliye kabul', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 20,
            'hedef_lokasyon_id', v_ic1, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'C4: dahiliye satın alma kabulü kaydedilmedi.';
    END IF;

    -- C5) Müşteri iadesi FASON lokasyonuna reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000012', 'MUSTERI_IADE', v_musteri,
            'M011-IADE-RED', NULL, NULL, 'fasona iade', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 2,
                'hedef_lokasyon_id', v_fason
            ))
        );
        RAISE EXCEPTION 'C5: fason lokasyonuna müşteri iadesi kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'C5:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%yalnız dahili lokasyona giriş yapabilir%' THEN
            RAISE EXCEPTION 'C5: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- C6) İç transfer FASON lokasyonuna reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000013', 'IC_TRANSFER', NULL,
            NULL, NULL, NULL, 'fasona iç transfer', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 2,
                'kaynak_lokasyon_id', v_ic1, 'hedef_lokasyon_id', v_fason
            ))
        );
        RAISE EXCEPTION 'C6: fason lokasyonuna iç transfer kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'C6:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%iç transferin iki ucu da dahili veya numune lokasyonu olmalıdır%' THEN
            RAISE EXCEPTION 'C6: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- C7) İç transfer FASON lokasyonundan da reddedilmeli (kaynak ucu)
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000014', 'IC_TRANSFER', NULL,
            NULL, NULL, NULL, 'fasondan iç transfer', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 2,
                'kaynak_lokasyon_id', v_fason, 'hedef_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'C7: fason lokasyonundan iç transfer kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'C7:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%iç transferin iki ucu da dahili veya numune lokasyonu olmalıdır%' THEN
            RAISE EXCEPTION 'C7: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- C8) İç transfer NUMUNE rafına GEÇMELİ
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000015', 'IC_TRANSFER', NULL,
        NULL, NULL, NULL, 'numuneye iç transfer', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 6,
            'kaynak_lokasyon_id', v_ic1, 'hedef_lokasyon_id', v_numune,
            'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'C8: numune rafına iç transfer kaydedilmedi.';
    END IF;
    SELECT COALESCE(SUM(mevcut_miktar), 0)::INTEGER INTO v_bakiye
    FROM v_stok_bakiye WHERE stok_kalemi_id = v_sku AND lokasyon_id = v_numune;
    IF v_bakiye <> 6 THEN
        RAISE EXCEPTION 'C8: numune rafı bakiyesi 6 olmalıydı, % bulundu.', v_bakiye;
    END IF;

    -- C9) İç transfer iki dahili yaprak arasında GEÇMELİ (008 davranışı bozulmadı)
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000016', 'IC_TRANSFER', NULL,
        NULL, NULL, NULL, 'dahili iç transfer', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 3,
            'kaynak_lokasyon_id', v_ic1, 'hedef_lokasyon_id', v_ic2,
            'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'C9: dahili-dahili iç transfer kaydedilmedi.';
    END IF;

    -- C10) Sayım NUMUNE rafında ÇALIŞMALI
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000017', 'SAYIM', NULL,
        NULL, NULL, NULL, 'numune sayımı', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'SAYIM_DEVRI', 'miktar', 9,
            'hedef_lokasyon_id', v_numune, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 THEN
        RAISE EXCEPTION 'C10: numune rafında sayım farkı yazılmadı.';
    END IF;
    SELECT COALESCE(SUM(mevcut_miktar), 0)::INTEGER INTO v_bakiye
    FROM v_stok_bakiye WHERE stok_kalemi_id = v_sku AND lokasyon_id = v_numune;
    IF v_bakiye <> 9 THEN
        RAISE EXCEPTION 'C10: sayım sonrası numune bakiyesi 9 olmalıydı, % bulundu.', v_bakiye;
    END IF;

    -- C11) Sayım FASON lokasyonunda reddedilmeli
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000018', 'SAYIM', NULL,
            NULL, NULL, NULL, 'fason sayımı', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'SAYIM_DEVRI', 'miktar', 1,
                'hedef_lokasyon_id', v_fason
            ))
        );
        RAISE EXCEPTION 'C11: fason lokasyonunda sayım kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'C11:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%sayım yalnız dahili veya numune lokasyonunda yapılabilir%' THEN
            RAISE EXCEPTION 'C11: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- =====================================================
    -- D) DUZELTME kısıt dışı — fason lokasyonunda HÂLÂ çalışmalı
    -- =====================================================
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000019', 'DUZELTME', NULL,
        NULL, NULL, v_seed_islem, 'fasondaki hatanın düzeltmesi', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'DUZELTME', 'miktar', 2,
            'hedef_lokasyon_id', v_fason, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 OR v_sonuc.atlandi THEN
        RAISE EXCEPTION 'D: fason lokasyonundaki düzeltme engellendi; kısıt düzeltme akışına sızmış.';
    END IF;

    -- =====================================================
    -- E) Fason akışları 008 davranışını aynen korumalı
    -- =====================================================
    SELECT stok_kalemi_id INTO v_hedef_sku FROM stok_kalemi_kaydet(
        v_urun, v_kaplama, NULL, NULL, 'MONTE', FALSE, FALSE, FALSE, 'migration-test'
    );
    SELECT fason_is_emri_id INTO v_emir FROM fason_is_emri_kaydet(
        '01100000-0000-4000-8000-000000000020', v_fasoncu, v_fason,
        v_sku, v_hedef_sku, 'KAPLAMA', 20, CURRENT_DATE + 2, NULL,
        'test iş emri', 'migration-test'
    );

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000021', 'FASON_SEVK', NULL,
        NULL, v_emir, NULL, 'fason sevk', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 20,
            'kaynak_lokasyon_id', v_ic1, 'hedef_lokasyon_id', v_fason,
            'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF v_sonuc.hareket_sayisi <> 1 THEN
        RAISE EXCEPTION 'E: fason sevk 008 davranışını kaybetti.';
    END IF;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000022', 'FASON_DONUS', NULL,
        NULL, v_emir, NULL, 'fason dönüş', 'migration-test',
        jsonb_build_array(
            jsonb_build_object('stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS',
                'miktar', 7, 'kaynak_lokasyon_id', v_fason),
            jsonb_build_object('stok_kalemi_id', v_hedef_sku, 'islem_tipi', 'GIRIS',
                'miktar', 7, 'hedef_lokasyon_id', v_ic1)
        )
    );
    SELECT donen_miktar INTO v_donen
    FROM v_fason_is_emri_ozet WHERE fason_is_emri_id = v_emir;
    IF v_donen <> 7 THEN
        RAISE EXCEPTION 'E: fason dönüşü 008 davranışını kaybetti (dönen: %).', v_donen;
    END IF;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '01100000-0000-4000-8000-000000000023', 'FIRE', NULL,
        NULL, v_emir, NULL, 'fason fire', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 3,
            'kaynak_lokasyon_id', v_fason
        ))
    );
    SELECT fire_miktari, fason_bakiye INTO v_adet, v_bakiye
    FROM v_fason_is_emri_ozet WHERE fason_is_emri_id = v_emir;
    IF v_adet <> 3 OR v_bakiye <> 10 THEN
        RAISE EXCEPTION 'E: fason fire/açık bakiye 008 davranışını kaybetti (fire: %, bakiye: %).', v_adet, v_bakiye;
    END IF;

    -- Fason sevk hâlâ DAHİLİ kaynak istiyor: 011 bu kontrolü ezmemeli.
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000024', 'FASON_SEVK', NULL,
            NULL, v_emir, NULL, 'numuneden fason sevk', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 1,
                'kaynak_lokasyon_id', v_numune, 'hedef_lokasyon_id', v_fason
            ))
        );
        RAISE EXCEPTION 'E: numune rafından fason sevk kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'E:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%fason sevk, iş emrindeki kaynak SKU%' THEN
            RAISE EXCEPTION 'E: beklenen fason sevk hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- =====================================================
    -- F) Kural gerçekten ısırıyor mu: fason lokasyonunda STOK VARKEN
    --
    -- C1/C7 fason ucunda bakiye sıfırken çalışıyor; kural kaldırılsa bile
    -- "yetersiz stok" hatası alınırdı, yani o assertion'lar tek başına kuralı
    -- kanıtlamıyor. E bölümünden sonra fason lokasyonunda gerçek bakiye var
    -- (20 sevk - 7 dönüş - 3 fire = 10); aşağıdaki üç ret YALNIZ lokasyon tipi
    -- kuralından gelebilir.
    -- =====================================================
    SELECT COALESCE(SUM(mevcut_miktar), 0)::INTEGER INTO v_bakiye
    FROM v_stok_bakiye WHERE stok_kalemi_id = v_sku AND lokasyon_id = v_fason;
    IF v_bakiye < 1 THEN
        RAISE EXCEPTION 'F: fason lokasyonunda bakiye yok (%); bu bölüm kuralı kanıtlayamaz.', v_bakiye;
    END IF;

    -- F1) Satış sevkiyatı, stok VARKEN de fason lokasyonundan yapılamaz
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000025', 'SATIS_SEVKI', v_musteri,
            'M011-SATIS-RED-2', NULL, NULL, 'stoklu fasondan satış', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 1,
                'kaynak_lokasyon_id', v_fason, 'stok_durumu_kodu', 'SERBEST'
            ))
        );
        RAISE EXCEPTION 'F1: stok varken fason lokasyonundan satış sevkiyatı kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'F1:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%yalnız dahili lokasyondan çıkış yapabilir%' THEN
            RAISE EXCEPTION 'F1: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- F2) Tedarikçi iadesi de stok VARKEN fason lokasyonundan yapılamaz
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000026', 'TEDARIKCI_IADE', v_tedarikci,
            'M011-IADE-RED-2', NULL, NULL, 'stoklu fasondan iade', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 1,
                'kaynak_lokasyon_id', v_fason, 'stok_durumu_kodu', 'SERBEST'
            ))
        );
        RAISE EXCEPTION 'F2: stok varken fason lokasyonundan tedarikçi iadesi kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'F2:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%yalnız dahili lokasyondan çıkış yapabilir%' THEN
            RAISE EXCEPTION 'F2: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;

    -- F3) İç transfer de stok VARKEN fason lokasyonundan yapılamaz
    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '01100000-0000-4000-8000-000000000027', 'IC_TRANSFER', NULL,
            NULL, NULL, NULL, 'stoklu fasondan iç transfer', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 1,
                'kaynak_lokasyon_id', v_fason, 'hedef_lokasyon_id', v_ic1,
                'stok_durumu_kodu', 'SERBEST'
            ))
        );
        RAISE EXCEPTION 'F3: stok varken fason lokasyonundan iç transfer kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE 'F3:%' THEN RAISE; END IF;
        IF SQLERRM NOT LIKE '%iç transferin iki ucu da dahili veya numune lokasyonu olmalıdır%' THEN
            RAISE EXCEPTION 'F3: beklenen lokasyon tipi hatası değil, gelen: %', SQLERRM;
        END IF;
    END;
END;
$$;

ROLLBACK;
