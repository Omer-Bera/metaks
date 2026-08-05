-- =========================================================
-- Migration 011 rollback
--
-- `stok_islemi_kaydet()` gövdesini migration 008'deki hâline birebir geri
-- yazar: iade karşı taraf zorunluluğu ve amaç ↔ lokasyon tipi kuralları düşer.
-- İmza değişmediği için `CREATE OR REPLACE` yeterlidir; düşürülecek nesne yok.
--
-- Aşağıdaki gövde `sql/migrations/008_stok_urun_modeli.sql` içindeki
-- fonksiyonun birebir kopyasıdır (elle yazılmadı, o dosyadan alındı).
-- Doğrulaması: rollback sonrası `pg_get_functiondef` çıktısı, yalnız 008
-- uygulanmış bir kopyadaki çıktıyla aynı olmalıdır.
--
-- 011 veri yazmadığı ve şema değiştirmediği için bu rollback'in veri kaybı
-- riski yoktur; kurallar yalnız yeni yazımları etkiliyordu.
--
-- Ortak veritabanında yalnız doğrulanmış yedekle kullanın.
-- =========================================================

BEGIN;

-- JSON satır biçimi:
-- {stok_kalemi_id, islem_tipi, miktar, kaynak_lokasyon_id?,
--  hedef_lokasyon_id?, stok_durumu_kodu?, parti_id?, parti_no?}
CREATE OR REPLACE FUNCTION stok_islemi_kaydet(
    p_istemci_islem_kimligi UUID,
    p_islem_nedeni VARCHAR,
    p_is_ortagi_id BIGINT,
    p_belge_no VARCHAR,
    p_fason_is_emri_id BIGINT,
    p_duzelttigi_stok_islem_id BIGINT,
    p_aciklama TEXT,
    p_yapan_kullanici VARCHAR,
    p_satirlar JSONB
) RETURNS TABLE (
    stok_islem_id BIGINT, hareket_sayisi INTEGER, atlandi BOOLEAN, mesaj TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_islem_id BIGINT;
    v_satir JSONB;
    v_sira INTEGER := 0;
    v_hareket_sayisi INTEGER := 0;
    v_sku_id BIGINT;
    v_urun_kodu VARCHAR;
    v_tip VARCHAR;
    v_miktar INTEGER;
    v_kaynak INTEGER;
    v_hedef INTEGER;
    v_durum VARCHAR;
    v_parti BIGINT;
    v_parti_no VARCHAR;
    v_mevcut INTEGER;
    v_fark INTEGER;
    v_hareket_uuid UUID;
    v_fason_is_ortagi BIGINT;
    v_fason_lokasyon INTEGER;
    v_fason_kaynak_sku BIGINT;
    v_fason_hedef_sku BIGINT;
    v_fason_planlanan INTEGER;
    v_fason_gonderilen INTEGER;
    v_fason_donen INTEGER;
    v_fason_fire INTEGER;
BEGIN
    SELECT si.stok_islem_id INTO v_islem_id
    FROM stok_islemleri si
    WHERE si.istemci_islem_kimligi = p_istemci_islem_kimligi;
    IF FOUND THEN
        RETURN QUERY SELECT v_islem_id, 0, TRUE,
            'Bu stok işlemi zaten kaydedilmiş, tekrar eklenmedi.'::TEXT;
        RETURN;
    END IF;

    IF p_istemci_islem_kimligi IS NULL THEN
        RAISE EXCEPTION 'İstemci işlem kimliği zorunludur.';
    END IF;
    IF p_yapan_kullanici IS NULL OR btrim(p_yapan_kullanici) = '' THEN
        RAISE EXCEPTION 'İşlemi yapan kullanıcı zorunludur.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM stok_islem_nedenleri WHERE islem_nedeni = p_islem_nedeni AND aktif_mi
    ) THEN
        RAISE EXCEPTION 'Geçersiz veya pasif işlem nedeni: "%".', p_islem_nedeni;
    END IF;
    IF jsonb_typeof(p_satirlar) <> 'array' OR jsonb_array_length(p_satirlar) = 0 THEN
        RAISE EXCEPTION 'Stok işlemi en az bir satır içermelidir.';
    END IF;
    IF p_islem_nedeni = 'DUZELTME'
       AND (p_aciklama IS NULL OR btrim(p_aciklama) = '') THEN
        RAISE EXCEPTION 'Düzeltme için açıklama zorunludur.';
    END IF;
    IF p_islem_nedeni = 'DUZELTME' AND p_duzelttigi_stok_islem_id IS NULL THEN
        RAISE EXCEPTION 'Düzeltmenin tersine çevirdiği stok işlemi zorunludur.';
    END IF;
    IF p_duzelttigi_stok_islem_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM stok_islemleri si
        WHERE si.stok_islem_id = p_duzelttigi_stok_islem_id
    ) THEN
        RAISE EXCEPTION 'Düzeltilmek istenen stok işlemi bulunamadı.';
    END IF;
    IF p_islem_nedeni IN ('SATIN_ALMA_KABUL', 'SATIS_SEVKI')
       AND p_is_ortagi_id IS NULL THEN
        RAISE EXCEPTION 'Bu işlem için müşteri/tedarikçi seçimi zorunludur.';
    END IF;
    IF p_islem_nedeni = 'SATIN_ALMA_KABUL' AND NOT EXISTS (
        SELECT 1 FROM is_ortaklari io
        JOIN is_ortagi_rolleri r USING (is_ortagi_id)
        WHERE io.is_ortagi_id = p_is_ortagi_id AND io.aktif_mi AND r.rol = 'TEDARIKCI'
    ) THEN
        RAISE EXCEPTION 'Satın alma kabulünde aktif bir tedarikçi seçilmelidir.';
    END IF;
    IF p_islem_nedeni = 'SATIS_SEVKI' AND NOT EXISTS (
        SELECT 1 FROM is_ortaklari io
        JOIN is_ortagi_rolleri r USING (is_ortagi_id)
        WHERE io.is_ortagi_id = p_is_ortagi_id AND io.aktif_mi AND r.rol = 'MUSTERI'
    ) THEN
        RAISE EXCEPTION 'Satış sevkiyatında aktif bir müşteri seçilmelidir.';
    END IF;
    IF NULLIF(btrim(p_belge_no), '') IS NOT NULL AND EXISTS (
        SELECT 1 FROM stok_islemleri
        WHERE islem_nedeni = p_islem_nedeni
          AND is_ortagi_id IS NOT DISTINCT FROM p_is_ortagi_id
          AND lower(btrim(belge_no)) = lower(btrim(p_belge_no))
    ) THEN
        RAISE EXCEPTION 'Aynı işlem nedeni, karşı taraf ve belge numarası daha önce kaydedilmiş.';
    END IF;
    IF p_islem_nedeni IN ('FASON_SEVK', 'FASON_DONUS', 'FIRE') THEN
        IF p_fason_is_emri_id IS NULL THEN
            RAISE EXCEPTION 'Fason sevk/dönüş için iş emri zorunludur.';
        END IF;
        SELECT
            fie.is_ortagi_id, fie.fason_lokasyon_id,
            fie.kaynak_stok_kalemi_id, fie.hedef_stok_kalemi_id,
            fie.planlanan_miktar
        INTO
            v_fason_is_ortagi, v_fason_lokasyon,
            v_fason_kaynak_sku, v_fason_hedef_sku, v_fason_planlanan
        FROM fason_is_emirleri fie
        WHERE fie.fason_is_emri_id = p_fason_is_emri_id AND fie.durum = 'ACIK'
        FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Açık fason iş emri bulunamadı.';
        END IF;
        IF p_is_ortagi_id IS NOT NULL AND p_is_ortagi_id <> v_fason_is_ortagi THEN
            RAISE EXCEPTION 'İşlemdeki fasoncu iş emriyle uyuşmuyor.';
        END IF;
        p_is_ortagi_id := v_fason_is_ortagi;
    END IF;

    INSERT INTO stok_islemleri (
        istemci_islem_kimligi, islem_nedeni, is_ortagi_id, belge_no,
        fason_is_emri_id, duzelttigi_stok_islem_id, aciklama, yapan_kullanici
    ) VALUES (
        p_istemci_islem_kimligi, p_islem_nedeni, p_is_ortagi_id,
        NULLIF(btrim(p_belge_no), ''), p_fason_is_emri_id,
        p_duzelttigi_stok_islem_id, NULLIF(btrim(p_aciklama), ''), p_yapan_kullanici
    )
    ON CONFLICT (istemci_islem_kimligi) DO NOTHING
    RETURNING stok_islemleri.stok_islem_id INTO v_islem_id;

    -- İlk SELECT ile INSERT arasına aynı UUID'li başka transaction girmişse UNIQUE
    -- hatası üretmek yerine onun tamamlanmış sonucunu idempotent yanıt olarak döndür.
    IF v_islem_id IS NULL THEN
        SELECT si.stok_islem_id INTO v_islem_id
        FROM stok_islemleri si
        WHERE si.istemci_islem_kimligi = p_istemci_islem_kimligi;
        RETURN QUERY SELECT v_islem_id, 0, TRUE,
            'Bu stok işlemi zaten kaydedilmiş, tekrar eklenmedi.'::TEXT;
        RETURN;
    END IF;

    FOR v_satir IN SELECT value FROM jsonb_array_elements(p_satirlar)
    LOOP
        v_sira := v_sira + 1;
        v_sku_id := NULLIF(v_satir->>'stok_kalemi_id', '')::BIGINT;
        v_tip := upper(COALESCE(v_satir->>'islem_tipi', ''));
        v_miktar := NULLIF(v_satir->>'miktar', '')::INTEGER;
        v_kaynak := NULLIF(v_satir->>'kaynak_lokasyon_id', '')::INTEGER;
        v_hedef := NULLIF(v_satir->>'hedef_lokasyon_id', '')::INTEGER;
        v_durum := COALESCE(NULLIF(v_satir->>'stok_durumu_kodu', ''), 'SERBEST');
        v_parti := NULLIF(v_satir->>'parti_id', '')::BIGINT;
        v_parti_no := NULLIF(btrim(v_satir->>'parti_no'), '');

        SELECT sk.urun_kodu INTO v_urun_kodu
        FROM stok_kalemleri sk
        WHERE sk.stok_kalemi_id = v_sku_id AND sk.aktif_mi AND sk.stoklanabilir_mi;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Satır %: aktif ve stoklanabilir SKU bulunamadı.', v_sira;
        END IF;
        IF v_parti IS NULL AND v_parti_no IS NOT NULL THEN
            SELECT sp.parti_id INTO v_parti
            FROM stok_partileri sp
            WHERE sp.stok_kalemi_id = v_sku_id
              AND lower(sp.parti_no) = lower(v_parti_no)
              AND sp.aktif_mi;
            IF NOT FOUND THEN
                IF v_tip NOT IN ('GIRIS', 'SAYIM_DEVRI', 'DUZELTME') OR v_kaynak IS NOT NULL THEN
                    RAISE EXCEPTION 'Satır %: kaynak SKU için parti bulunamadı.', v_sira;
                END IF;
                INSERT INTO stok_partileri (stok_kalemi_id, parti_no)
                VALUES (v_sku_id, v_parti_no)
                RETURNING stok_partileri.parti_id INTO v_parti;
            END IF;
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM stok_durumlari WHERE stok_durumu_kodu = v_durum AND aktif_mi
        ) THEN
            RAISE EXCEPTION 'Satır %: geçersiz stok durumu.', v_sira;
        END IF;
        IF v_parti IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM stok_partileri
            WHERE parti_id = v_parti AND stok_kalemi_id = v_sku_id AND aktif_mi
        ) THEN
            RAISE EXCEPTION 'Satır %: parti seçilen SKU ile uyuşmuyor.', v_sira;
        END IF;
        IF v_tip NOT IN ('GIRIS', 'CIKIS', 'TRANSFER', 'SAYIM_DEVRI', 'DUZELTME') THEN
            RAISE EXCEPTION 'Satır %: geçersiz işlem tipi.', v_sira;
        END IF;
        IF p_islem_nedeni IN ('SATIN_ALMA_KABUL', 'MUSTERI_IADE') AND v_tip <> 'GIRIS' THEN
            RAISE EXCEPTION 'Satır %: bu işlem nedeni yalnız giriş oluşturabilir.', v_sira;
        ELSIF p_islem_nedeni = 'URETIM_GIRIS' AND v_tip NOT IN ('GIRIS', 'CIKIS') THEN
            RAISE EXCEPTION 'Satır %: üretim işlemi yalnız tüketim ve giriş satırı oluşturabilir.', v_sira;
        ELSIF p_islem_nedeni IN ('SATIS_SEVKI', 'TEDARIKCI_IADE', 'FIRE')
              AND v_tip <> 'CIKIS' THEN
            RAISE EXCEPTION 'Satır %: bu işlem nedeni yalnız çıkış oluşturabilir.', v_sira;
        ELSIF p_islem_nedeni = 'IC_TRANSFER' AND v_tip <> 'TRANSFER' THEN
            RAISE EXCEPTION 'Satır %: iç transfer yalnız transfer satırı oluşturabilir.', v_sira;
        ELSIF p_islem_nedeni = 'SAYIM' AND v_tip <> 'SAYIM_DEVRI' THEN
            RAISE EXCEPTION 'Satır %: sayım yalnız sayım farkı satırı oluşturabilir.', v_sira;
        ELSIF p_islem_nedeni = 'DUZELTME' AND v_tip <> 'DUZELTME' THEN
            RAISE EXCEPTION 'Satır %: düzeltme yalnız düzeltme satırı oluşturabilir.', v_sira;
        ELSIF p_islem_nedeni = 'STOK_SINIFLANDIRMA' AND v_tip NOT IN ('GIRIS', 'CIKIS') THEN
            RAISE EXCEPTION 'Satır %: stok sınıflandırma yalnız çıkış/giriş satırı oluşturabilir.', v_sira;
        END IF;
        IF (v_tip = 'SAYIM_DEVRI' AND (v_miktar IS NULL OR v_miktar < 0))
           OR (v_tip <> 'SAYIM_DEVRI' AND (v_miktar IS NULL OR v_miktar <= 0)) THEN
            RAISE EXCEPTION 'Satır %: miktar geçersiz.', v_sira;
        END IF;

        IF v_tip = 'GIRIS' AND v_hedef IS NULL THEN
            RAISE EXCEPTION 'Satır %: giriş için hedef lokasyon zorunludur.', v_sira;
        ELSIF v_tip = 'CIKIS' AND v_kaynak IS NULL THEN
            RAISE EXCEPTION 'Satır %: çıkış için kaynak lokasyon zorunludur.', v_sira;
        ELSIF v_tip = 'TRANSFER' AND (v_kaynak IS NULL OR v_hedef IS NULL OR v_kaynak = v_hedef) THEN
            RAISE EXCEPTION 'Satır %: transfer için farklı kaynak ve hedef zorunludur.', v_sira;
        ELSIF v_tip = 'SAYIM_DEVRI' AND v_hedef IS NULL THEN
            RAISE EXCEPTION 'Satır %: sayım lokasyonu zorunludur.', v_sira;
        ELSIF v_tip = 'DUZELTME' AND v_kaynak IS NULL AND v_hedef IS NULL THEN
            RAISE EXCEPTION 'Satır %: düzeltme için kaynak veya hedef zorunludur.', v_sira;
        END IF;

        IF v_kaynak IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM v_lokasyonlar_detay
            WHERE lokasyon_id = v_kaynak AND aktif_mi AND yaprak_mi
        ) THEN
            RAISE EXCEPTION 'Satır %: kaynak aktif bir yaprak lokasyon değildir.', v_sira;
        END IF;
        IF v_hedef IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM v_lokasyonlar_detay
            WHERE lokasyon_id = v_hedef AND aktif_mi AND yaprak_mi
        ) THEN
            RAISE EXCEPTION 'Satır %: hedef aktif bir yaprak lokasyon değildir.', v_sira;
        END IF;

        IF p_islem_nedeni = 'FASON_SEVK'
           AND (v_tip <> 'TRANSFER' OR v_sku_id <> v_fason_kaynak_sku
                OR v_hedef <> v_fason_lokasyon
                OR NOT EXISTS (
                    SELECT 1 FROM lokasyonlar WHERE lokasyon_id = v_kaynak AND tip = 'DAHILI'
                )) THEN
            RAISE EXCEPTION 'Satır %: fason sevk, iş emrindeki kaynak SKU''yu fason lokasyonuna transfer etmelidir.', v_sira;
        END IF;
        IF p_islem_nedeni = 'FASON_DONUS' THEN
            IF v_tip = 'TRANSFER'
               AND (v_sku_id <> v_fason_kaynak_sku OR v_fason_kaynak_sku <> v_fason_hedef_sku
                    OR v_kaynak <> v_fason_lokasyon
                    OR NOT EXISTS (
                        SELECT 1 FROM lokasyonlar WHERE lokasyon_id = v_hedef AND tip = 'DAHILI'
                    )) THEN
                RAISE EXCEPTION 'Satır %: aynı SKU fason dönüşü iş emriyle uyuşmuyor.', v_sira;
            ELSIF v_tip = 'CIKIS'
               AND (v_sku_id <> v_fason_kaynak_sku OR v_kaynak <> v_fason_lokasyon) THEN
                RAISE EXCEPTION 'Satır %: fason dönüş tüketimi iş emrindeki kaynak SKU/lokasyonla uyuşmuyor.', v_sira;
            ELSIF v_tip = 'GIRIS'
               AND (v_sku_id <> v_fason_hedef_sku
                    OR NOT EXISTS (
                        SELECT 1 FROM lokasyonlar WHERE lokasyon_id = v_hedef AND tip = 'DAHILI'
                    )) THEN
                RAISE EXCEPTION 'Satır %: fason dönüş çıktısı iş emrindeki hedef SKU ile uyuşmuyor.', v_sira;
            ELSIF v_tip NOT IN ('TRANSFER', 'CIKIS', 'GIRIS') THEN
                RAISE EXCEPTION 'Satır %: fason dönüşünde geçersiz teknik hareket.', v_sira;
            END IF;
        END IF;
        IF p_islem_nedeni = 'FIRE'
           AND (v_tip <> 'CIKIS' OR v_sku_id <> v_fason_kaynak_sku
                OR v_kaynak <> v_fason_lokasyon) THEN
            RAISE EXCEPTION 'Satır %: fason fire iş emrindeki kaynak SKU ve fason lokasyonundan düşmelidir.', v_sira;
        END IF;

        -- Aynı SKU/lokasyondaki eşzamanlı çıkışların ikisi birden bakiyeyi geçmesin.
        IF v_kaynak IS NOT NULL THEN
            PERFORM pg_advisory_xact_lock((v_sku_id % 2147483647)::INTEGER, v_kaynak);
        END IF;

        IF v_tip = 'SAYIM_DEVRI' THEN
            SELECT COALESCE(SUM(sb.mevcut_miktar), 0)::INTEGER INTO v_mevcut
            FROM v_stok_bakiye sb
            WHERE sb.stok_kalemi_id = v_sku_id
              AND sb.lokasyon_id = v_hedef
              AND sb.stok_durumu_kodu = v_durum
              AND sb.parti_id IS NOT DISTINCT FROM v_parti;
            v_fark := v_miktar - v_mevcut;
            IF v_fark = 0 THEN
                CONTINUE;
            ELSIF v_fark > 0 THEN
                v_kaynak := NULL;
                v_miktar := v_fark;
            ELSE
                v_kaynak := v_hedef;
                v_hedef := NULL;
                v_miktar := abs(v_fark);
            END IF;
        END IF;

        IF v_kaynak IS NOT NULL THEN
            SELECT COALESCE(SUM(sb.mevcut_miktar), 0)::INTEGER INTO v_mevcut
            FROM v_stok_bakiye sb
            WHERE sb.stok_kalemi_id = v_sku_id
              AND sb.lokasyon_id = v_kaynak
              AND sb.stok_durumu_kodu = v_durum
              AND sb.parti_id IS NOT DISTINCT FROM v_parti;
            IF v_miktar > v_mevcut THEN
                RAISE EXCEPTION 'Satır %: yetersiz stok; mevcut %, istenen %.',
                    v_sira, v_mevcut, v_miktar;
            END IF;
        END IF;

        v_hareket_uuid := (
            substr(md5(p_istemci_islem_kimligi::TEXT || ':' || v_sira::TEXT), 1, 8) || '-' ||
            substr(md5(p_istemci_islem_kimligi::TEXT || ':' || v_sira::TEXT), 9, 4) || '-' ||
            substr(md5(p_istemci_islem_kimligi::TEXT || ':' || v_sira::TEXT), 13, 4) || '-' ||
            substr(md5(p_istemci_islem_kimligi::TEXT || ':' || v_sira::TEXT), 17, 4) || '-' ||
            substr(md5(p_istemci_islem_kimligi::TEXT || ':' || v_sira::TEXT), 21, 12)
        )::UUID;

        INSERT INTO stok_hareketleri (
            istemci_islem_kimligi, stok_islem_id, stok_kalemi_id, stok_kodu,
            miktar, kaynak_lokasyon_id, hedef_lokasyon_id, islem_tipi,
            aciklama, yapan_kullanici, stok_durumu_kodu, parti_id
        ) VALUES (
            v_hareket_uuid, v_islem_id, v_sku_id, v_urun_kodu,
            v_miktar, v_kaynak, v_hedef, v_tip,
            NULLIF(btrim(p_aciklama), ''), p_yapan_kullanici, v_durum, v_parti
        );
        v_hareket_sayisi := v_hareket_sayisi + 1;
    END LOOP;

    IF p_islem_nedeni IN ('FASON_SEVK', 'FASON_DONUS', 'FIRE') THEN
        SELECT gonderilen_miktar, donen_miktar, fire_miktari
        INTO v_fason_gonderilen, v_fason_donen, v_fason_fire
        FROM v_fason_is_emri_ozet
        WHERE fason_is_emri_id = p_fason_is_emri_id;
        IF v_fason_gonderilen > v_fason_planlanan THEN
            RAISE EXCEPTION 'İş emrinde planlanan % adetten fazla sevk yapılamaz.',
                v_fason_planlanan;
        END IF;
        IF v_fason_donen > v_fason_gonderilen THEN
            RAISE EXCEPTION 'Fason dönüş miktarı bu iş emrinde gönderilen miktarı aşamaz.';
        END IF;
        IF v_fason_donen + v_fason_fire > v_fason_gonderilen THEN
            RAISE EXCEPTION 'Fason dönüş ve fire toplamı gönderilen miktarı aşamaz.';
        END IF;
        IF v_fason_donen + v_fason_fire = v_fason_planlanan THEN
            UPDATE fason_is_emirleri
            SET durum = 'TAMAMLANDI', updated_at = CURRENT_TIMESTAMP
            WHERE fason_is_emri_id = p_fason_is_emri_id;
        END IF;
    END IF;

    RETURN QUERY SELECT
        v_islem_id,
        v_hareket_sayisi,
        (v_hareket_sayisi = 0),
        CASE WHEN v_hareket_sayisi = 0
             THEN 'Girilen sayım sistem bakiyesiyle aynı; hareket oluşturulmadı.'
             ELSE format('%s hareket satırı atomik olarak kaydedildi.', v_hareket_sayisi)
        END::TEXT;
END;
$$;

COMMIT;
