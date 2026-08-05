-- DİKKAT — bu test yalnız 008/009 seviyesindeki bir kopyada geçerlidir.
-- Migration 010 uygulanmış bir kopyada BEKLENDİĞİ GİBİ hata verir: aşağıda
-- `stok_kalemi_kaydet()` eski altı parametreli imzasıyla çağrılıyor (010 imzayı
-- üç BOOLEAN ile değiştirdi) ve montaj hali 'HAM' olarak veriliyor (010 bu
-- değeri 'DEMONTE' yaptı). Bu bir bozukluk değil, tarihsel bir kabul kaydıdır;
-- gövdesi bilerek değiştirilmiyor. 010 ve sonrası için
-- `010_sku_nitelikleri_test.sql` ve `011_stok_islemi_kurallari_test.sql`
-- dosyalarını kullanın.
--
-- Migration 008 hedefli kabul testi. Yalnız disposable/restored veritabanında,
-- migration uygulandıktan sonra çalıştırılır. Bütün örnek hareketler geri alınır.
\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    v_sku BIGINT;
    v_urun VARCHAR;
    v_hedef_sku BIGINT;
    v_ic1 INTEGER;
    v_ic2 INTEGER;
    v_fason INTEGER;
    v_fasoncu BIGINT;
    v_ortak BIGINT;
    v_emir BIGINT;
    v_once INTEGER;
    v_sonra INTEGER;
    v_hazir INTEGER;
    v_fasonda INTEGER;
    v_adet INTEGER;
    v_sonuc RECORD;
BEGIN
    SELECT stok_kalemi_id, urun_kodu INTO v_sku, v_urun
    FROM stok_kalemleri
    WHERE nitelik_durumu = 'BELIRSIZ' AND aktif_mi AND stoklanabilir_mi
    ORDER BY stok_kalemi_id LIMIT 1;
    SELECT min(lokasyon_id), max(lokasyon_id) INTO v_ic1, v_ic2
    FROM v_lokasyonlar_detay WHERE aktif_mi AND yaprak_mi AND tip = 'DAHILI';
    SELECT ld.lokasyon_id, l.is_ortagi_id INTO v_fason, v_fasoncu
    FROM v_lokasyonlar_detay ld JOIN lokasyonlar l USING (lokasyon_id)
    WHERE ld.aktif_mi AND ld.yaprak_mi AND ld.tip = 'FASON'
      AND l.is_ortagi_id IS NOT NULL LIMIT 1;
    IF v_sku IS NULL OR v_ic1 IS NULL OR v_ic2 IS NULL OR v_ic1 = v_ic2
       OR v_fason IS NULL THEN
        RAISE EXCEPTION 'Test için bir SKU, iki dahili yaprak ve bir fason lokasyonu gerekir.';
    END IF;

    SELECT is_ortagi_id INTO v_ortak
    FROM is_ortagi_kaydet(
        'M008-TEST', 'Migration 008 test ortağı',
        '["MUSTERI", "TEDARIKCI"]'::jsonb, 'migration-test'
    );
    SELECT stok_kalemi_id INTO v_hedef_sku
    FROM stok_kalemi_kaydet(
        v_urun, (SELECT kaplama_id FROM kaplamalar WHERE aktif_mi ORDER BY kaplama_id LIMIT 1),
        NULL, NULL, 'HAM', 'migration-test'
    );

    SELECT COALESCE(sahip_olunan_toplam, 0) INTO v_once
    FROM v_stok_urun_ozet WHERE urun_kodu = v_urun;
    v_once := COALESCE(v_once, 0);

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000001', 'SATIN_ALMA_KABUL', v_ortak,
        'M008-ALIS-1', NULL, NULL, 'test kabul', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 100,
            'hedef_lokasyon_id', v_ic1, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    SELECT sahip_olunan_toplam, satisa_hazir_toplam
    INTO v_sonra, v_hazir FROM v_stok_urun_ozet WHERE urun_kodu = v_urun;
    IF v_sonra <> v_once + 100 OR v_hazir < 100 THEN
        RAISE EXCEPTION 'Satın alma toplam/satışa hazır stoğu doğru artırmadı.';
    END IF;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000001', 'SATIN_ALMA_KABUL', v_ortak,
        'M008-ALIS-1', NULL, NULL, 'test kabul', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 100,
            'hedef_lokasyon_id', v_ic1, 'stok_durumu_kodu', 'SERBEST'
        ))
    );
    IF NOT v_sonuc.atlandi THEN
        RAISE EXCEPTION 'Aynı istemci kimliği mükerrer isteği durdurmadı.';
    END IF;

    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '00800000-0000-4000-8000-000000000002', 'SATIN_ALMA_KABUL', v_ortak,
            'M008-ALIS-1', NULL, NULL, 'mükerrer belge', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'GIRIS', 'miktar', 1,
                'hedef_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'Mükerrer belge numarası kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'Mükerrer belge numarası kabul edildi.' THEN RAISE; END IF;
    END;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000003', 'SATIS_SEVKI', v_ortak,
        'M008-SATIS-1', NULL, NULL, 'test satış', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 10,
            'kaynak_lokasyon_id', v_ic1
        ))
    );
    SELECT sahip_olunan_toplam INTO v_sonra
    FROM v_stok_urun_ozet WHERE urun_kodu = v_urun;
    IF v_sonra <> v_once + 90 THEN RAISE EXCEPTION 'Satış toplam stoğu doğru azaltmadı.'; END IF;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000004', 'IC_TRANSFER', NULL,
        NULL, NULL, NULL, 'test transfer', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 5,
            'kaynak_lokasyon_id', v_ic1, 'hedef_lokasyon_id', v_ic2
        ))
    );
    SELECT sahip_olunan_toplam INTO v_sonra
    FROM v_stok_urun_ozet WHERE urun_kodu = v_urun;
    IF v_sonra <> v_once + 90 THEN RAISE EXCEPTION 'İç transfer şirket toplamını değiştirdi.'; END IF;

    SELECT fason_is_emri_id INTO v_emir FROM fason_is_emri_kaydet(
        '00800000-0000-4000-8000-000000000005', v_fasoncu, v_fason,
        v_sku, v_hedef_sku, 'KAPLAMA', 20, CURRENT_DATE + 2, NULL,
        'test iş emri', 'migration-test'
    );
    SELECT satisa_hazir_toplam, fasonda_toplam INTO v_hazir, v_fasonda
    FROM v_stok_urun_ozet WHERE urun_kodu = v_urun;
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000006', 'FASON_SEVK', NULL,
        NULL, v_emir, NULL, 'test fason sevk', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'TRANSFER', 'miktar', 20,
            'kaynak_lokasyon_id', v_ic1, 'hedef_lokasyon_id', v_fason
        ))
    );
    IF (SELECT sahip_olunan_toplam FROM v_stok_urun_ozet WHERE urun_kodu = v_urun)
       <> v_once + 90 THEN RAISE EXCEPTION 'Fason sevk şirket toplamını değiştirdi.'; END IF;
    IF (SELECT fasonda_toplam FROM v_stok_urun_ozet WHERE urun_kodu = v_urun) <> v_fasonda + 20
       OR (SELECT satisa_hazir_toplam FROM v_stok_urun_ozet WHERE urun_kodu = v_urun) <> v_hazir - 20
    THEN RAISE EXCEPTION 'Fason sevk kullanılabilir/fason kırılımını doğru taşımadı.'; END IF;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000007', 'FASON_DONUS', NULL,
        NULL, v_emir, NULL, 'test fason dönüş', 'migration-test',
        jsonb_build_array(
            jsonb_build_object('stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS',
                'miktar', 7, 'kaynak_lokasyon_id', v_fason),
            jsonb_build_object('stok_kalemi_id', v_hedef_sku, 'islem_tipi', 'GIRIS',
                'miktar', 7, 'hedef_lokasyon_id', v_ic1)
        )
    );
    SELECT donen_miktar, fason_bakiye INTO v_adet, v_fasonda
    FROM v_fason_is_emri_ozet WHERE fason_is_emri_id = v_emir;
    IF v_adet <> 7 OR v_fasonda <> 13 THEN
        RAISE EXCEPTION 'Kısmi/değişen SKU fason dönüşü yanlış hesaplandı.';
    END IF;
    IF (SELECT sahip_olunan_toplam FROM v_stok_urun_ozet WHERE urun_kodu = v_urun)
       <> v_once + 90 THEN RAISE EXCEPTION 'SKU dönüşümü çift sayım üretti.'; END IF;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000009', 'FIRE', NULL,
        NULL, v_emir, NULL, 'test fason fire', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 3,
            'kaynak_lokasyon_id', v_fason
        ))
    );
    SELECT fire_miktari, fason_bakiye INTO v_adet, v_fasonda
    FROM v_fason_is_emri_ozet WHERE fason_is_emri_id = v_emir;
    IF v_adet <> 3 OR v_fasonda <> 10 THEN
        RAISE EXCEPTION 'Fason fire/açık bakiye yanlış hesaplandı.';
    END IF;

    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '00800000-0000-4000-8000-000000000008', 'SATIS_SEVKI', v_ortak,
            'M008-YETERSIZ', NULL, NULL, 'yetersiz test', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'CIKIS', 'miktar', 1000000,
                'kaynak_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'Yetersiz stok kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'Yetersiz stok kabul edildi.' THEN RAISE; END IF;
    END;

    SELECT COALESCE(SUM(mevcut_miktar), 0)::INTEGER INTO v_adet
    FROM v_stok_bakiye
    WHERE stok_kalemi_id = v_sku AND lokasyon_id = v_ic2
      AND stok_durumu_kodu = 'SERBEST' AND parti_id IS NULL;
    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000010', 'SAYIM', NULL,
        NULL, NULL, NULL, 'test sayım', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_sku, 'islem_tipi', 'SAYIM_DEVRI',
            'miktar', v_adet + 2, 'hedef_lokasyon_id', v_ic2
        ))
    );
    IF (SELECT COALESCE(SUM(mevcut_miktar), 0) FROM v_stok_bakiye
        WHERE stok_kalemi_id = v_sku AND lokasyon_id = v_ic2
          AND stok_durumu_kodu = 'SERBEST' AND parti_id IS NULL) <> v_adet + 2
    THEN RAISE EXCEPTION 'Sayım farkı doğru SKU/lokasyon/duruma yazılmadı.'; END IF;

    SELECT * INTO v_sonuc FROM stok_islemi_kaydet(
        '00800000-0000-4000-8000-000000000011', 'URETIM_GIRIS', NULL,
        'M008-PARTI', NULL, NULL, 'test lot', 'migration-test',
        jsonb_build_array(jsonb_build_object(
            'stok_kalemi_id', v_hedef_sku, 'islem_tipi', 'GIRIS', 'miktar', 4,
            'hedef_lokasyon_id', v_ic1, 'parti_no', 'M008-LOT-1'
        ))
    );
    IF (SELECT mevcut_miktar FROM v_stok_bakiye
        WHERE stok_kalemi_id = v_hedef_sku AND lokasyon_id = v_ic1
          AND parti_no = 'M008-LOT-1') <> 4
    THEN RAISE EXCEPTION 'Parti/lot bakiyesi doğru oluşturulmadı.'; END IF;

    BEGIN
        PERFORM * FROM stok_islemi_kaydet(
            '00800000-0000-4000-8000-000000000012', 'DUZELTME', NULL,
            NULL, NULL, NULL, 'bağlantısız düzeltme', 'migration-test',
            jsonb_build_array(jsonb_build_object(
                'stok_kalemi_id', v_sku, 'islem_tipi', 'DUZELTME', 'miktar', 1,
                'hedef_lokasyon_id', v_ic1
            ))
        );
        RAISE EXCEPTION 'Bağlantısız düzeltme kabul edildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'Bağlantısız düzeltme kabul edildi.' THEN RAISE; END IF;
    END;

    BEGIN
        UPDATE stok_hareketleri SET miktar = miktar + 1
        WHERE stok_islem_id = v_sonuc.stok_islem_id;
        RAISE EXCEPTION 'Defter satırı güncellenebildi.';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'Defter satırı güncellenebildi.' THEN RAISE; END IF;
    END;
END;
$$;

-- Eski ve yeni defter toplamı her ürün için hâlâ birebir olmalı.
DO $$
DECLARE v_uyusmayan INTEGER;
BEGIN
    WITH eski AS (
        SELECT stok_kodu, SUM(net)::INTEGER toplam
        FROM (
            SELECT stok_kodu, miktar net FROM stok_hareketleri WHERE hedef_lokasyon_id IS NOT NULL
            UNION ALL
            SELECT stok_kodu, -miktar FROM stok_hareketleri WHERE kaynak_lokasyon_id IS NOT NULL
        ) x GROUP BY stok_kodu
    ), yeni AS (
        SELECT urun_kodu stok_kodu, sahip_olunan_toplam toplam FROM v_stok_urun_ozet
    )
    SELECT count(*) INTO v_uyusmayan FROM eski FULL JOIN yeni USING (stok_kodu)
    WHERE eski.toplam IS DISTINCT FROM yeni.toplam;
    IF v_uyusmayan <> 0 THEN
        RAISE EXCEPTION 'Eski/yeni ürün toplamlarında % uyumsuzluk var.', v_uyusmayan;
    END IF;
END;
$$;

ROLLBACK;
