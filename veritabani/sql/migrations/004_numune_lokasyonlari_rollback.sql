-- =========================================================
-- Migration 004 rollback: numune lokasyon hiyerarşisini geri al
--
-- View'lar 002'deki, stok_hareketi_kaydet() 003'teki haline döndürülür.
--
-- ⚠️ Bu rollback, NUMUNE tipinde ya da ust_lokasyon_id dolu bir lokasyon
-- varsa BİLEREK durur: geri alma o satırları sessizce yok etmek ya da
-- kısıt ihlaline düşmek anlamına gelirdi. Önce o lokasyonları (ve varsa
-- onlara bağlı stok hareketlerini) elle ele alın.
-- =========================================================

BEGIN;

DO $$
DECLARE
    v_numune INTEGER;
    v_alt INTEGER;
BEGIN
    SELECT count(*) INTO v_numune FROM lokasyonlar WHERE tip = 'NUMUNE';
    SELECT count(*) INTO v_alt    FROM lokasyonlar WHERE ust_lokasyon_id IS NOT NULL;

    IF v_numune > 0 OR v_alt > 0 THEN
        RAISE EXCEPTION
            'Geri alma durduruldu: % adet NUMUNE tipli, % adet alt lokasyon var. Önce bunları temizleyin.',
            v_numune, v_alt;
    END IF;
END;
$$;

-- ---------------------------------------------------------
-- 1) 004'te eklenen/değiştirilen view'lar. Bağımlılık sırası önemli:
--    v_toplam_stok/v_fiziksel_stok/v_numune_konumlari ->
--    v_lokasyon_stok_ozet -> v_lokasyonlar_detay
--    v_lokasyon_stok_ozet CREATE OR REPLACE ile eski haline
--    döndürülemez (kolon çıkarılıyor), o yüzden DROP + CREATE.
-- ---------------------------------------------------------
DROP VIEW IF EXISTS v_numune_konumlari;
DROP VIEW IF EXISTS v_fiziksel_stok;
DROP VIEW IF EXISTS v_toplam_stok;
DROP VIEW IF EXISTS v_lokasyon_stok_ozet;
DROP VIEW IF EXISTS v_lokasyonlar_detay;

-- 002'deki tanım, birebir.
CREATE VIEW v_lokasyon_stok_ozet AS
SELECT
    hareket.stok_kodu,
    hareket.lokasyon_id,
    l.lokasyon_adi,
    l.tip AS lokasyon_tipi,
    SUM(hareket.net_miktar) AS mevcut_miktar
FROM (
    SELECT stok_kodu, hedef_lokasyon_id AS lokasyon_id, miktar AS net_miktar
    FROM stok_hareketleri
    WHERE hedef_lokasyon_id IS NOT NULL
    UNION ALL
    SELECT stok_kodu, kaynak_lokasyon_id AS lokasyon_id, -miktar AS net_miktar
    FROM stok_hareketleri
    WHERE kaynak_lokasyon_id IS NOT NULL
) hareket
JOIN lokasyonlar l ON l.lokasyon_id = hareket.lokasyon_id
GROUP BY hareket.stok_kodu, hareket.lokasyon_id, l.lokasyon_adi, l.tip;

CREATE VIEW v_toplam_stok AS
SELECT
    stok_kodu,
    SUM(mevcut_miktar) AS toplam_miktar
FROM v_lokasyon_stok_ozet
GROUP BY stok_kodu;

-- ---------------------------------------------------------
-- 2) Hiyerarşi kolonları ve kısıtları
-- ---------------------------------------------------------
ALTER TABLE lokasyonlar DROP CONSTRAINT IF EXISTS lokasyonlar_ust_lokasyon_fkey;
ALTER TABLE lokasyonlar DROP CONSTRAINT IF EXISTS uq_lokasyonlar_id_kok;

DROP INDEX IF EXISTS uq_lokasyonlar_ust_ad_tip;
DROP INDEX IF EXISTS uq_lokasyonlar_kod;
DROP INDEX IF EXISTS idx_lokasyonlar_ust;

ALTER TABLE lokasyonlar
    DROP COLUMN IF EXISTS ust_kok_mu,
    DROP COLUMN IF EXISTS kok_mu,
    DROP COLUMN IF EXISTS kod,
    DROP COLUMN IF EXISTS ust_lokasyon_id;

ALTER TABLE lokasyonlar
    ADD CONSTRAINT uq_lokasyonlar_ad_tip UNIQUE (lokasyon_adi, tip);

-- ---------------------------------------------------------
-- 3) Lokasyon tipi kısıtı 001 öncesi haline
-- ---------------------------------------------------------
ALTER TABLE lokasyonlar DROP CONSTRAINT lokasyonlar_tip_check;

ALTER TABLE lokasyonlar ADD CONSTRAINT lokasyonlar_tip_check
    CHECK (tip IN ('DAHILI', 'FASON'));

-- ---------------------------------------------------------
-- 4) stok_hareketi_kaydet() 003'teki haline (yaprak kontrolü olmadan).
--    Gövde 003_stok_hareketi_fonksiyonu.sql ile birebir aynıdır.
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION stok_hareketi_kaydet(
    p_istemci_islem_kimligi UUID,
    p_stok_kodu VARCHAR,
    p_islem_tipi VARCHAR,
    p_miktar INTEGER,
    p_kaynak_lokasyon_id INTEGER DEFAULT NULL,
    p_hedef_lokasyon_id INTEGER DEFAULT NULL,
    p_aciklama TEXT DEFAULT NULL,
    p_yapan_kullanici VARCHAR DEFAULT NULL
) RETURNS TABLE (hareket_id BIGINT, uygulanan_miktar INTEGER, atlandi BOOLEAN, mesaj TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_mevcut INTEGER;
    v_fark INTEGER;
    v_hareket_id BIGINT;
    v_kaynak INTEGER;
    v_hedef INTEGER;
    v_miktar INTEGER;
    v_kaynak_mevcut INTEGER;
BEGIN
    -- Mükerrer gönderim koruması: aynı istemci kimliği daha önce
    -- kaydedilmişse yeni satır eklemeden mevcut sonucu bildir.
    IF p_istemci_islem_kimligi IS NOT NULL THEN
        SELECT sh.hareket_id INTO v_hareket_id
        FROM stok_hareketleri sh
        WHERE sh.istemci_islem_kimligi = p_istemci_islem_kimligi;

        IF FOUND THEN
            RETURN QUERY SELECT v_hareket_id, 0, TRUE,
                'Bu işlem zaten kaydedilmiş (aynı istemci kimliği), tekrar eklenmedi.'::TEXT;
            RETURN;
        END IF;
    END IF;

    IF p_yapan_kullanici IS NULL OR btrim(p_yapan_kullanici) = '' THEN
        RAISE EXCEPTION 'İşlemi yapan kullanıcı bilgisi zorunludur.';
    END IF;

    IF p_islem_tipi = 'SAYIM_DEVRI' THEN
        IF p_miktar < 0 THEN
            RAISE EXCEPTION 'Sayılan miktar negatif olamaz.';
        END IF;
    ELSE
        IF p_miktar <= 0 THEN
            RAISE EXCEPTION 'Miktar sıfırdan büyük olmalıdır.';
        END IF;
    END IF;

    IF p_islem_tipi = 'GIRIS' AND p_hedef_lokasyon_id IS NULL THEN
        RAISE EXCEPTION 'GİRİŞ işlemi için hedef lokasyon zorunludur.';
    ELSIF p_islem_tipi = 'CIKIS' AND p_kaynak_lokasyon_id IS NULL THEN
        RAISE EXCEPTION 'ÇIKIŞ işlemi için kaynak lokasyon zorunludur.';
    ELSIF p_islem_tipi = 'DUZELTME' AND p_kaynak_lokasyon_id IS NULL AND p_hedef_lokasyon_id IS NULL THEN
        RAISE EXCEPTION 'DÜZELTME işlemi için en az bir lokasyon (kaynak ya da hedef) zorunludur.';
    ELSIF p_islem_tipi = 'TRANSFER' AND (p_kaynak_lokasyon_id IS NULL OR p_hedef_lokasyon_id IS NULL) THEN
        RAISE EXCEPTION 'TRANSFER işlemi için hem kaynak hem hedef lokasyon zorunludur.';
    END IF;
    -- TRANSFER'de kaynak = hedef olamaz zaten tablonun kendi CHECK
    -- constraint'i (chk_transfer_farkli_lokasyon) ile korunuyor.

    IF p_islem_tipi = 'SAYIM_DEVRI' THEN
        IF p_hedef_lokasyon_id IS NULL THEN
            RAISE EXCEPTION 'SAYIM_DEVRI için sayımın yapıldığı lokasyon (p_hedef_lokasyon_id) zorunludur';
        END IF;

        SELECT COALESCE(mevcut_miktar, 0) INTO v_mevcut
        FROM v_lokasyon_stok_ozet
        WHERE stok_kodu = p_stok_kodu AND lokasyon_id = p_hedef_lokasyon_id;

        v_fark := p_miktar - COALESCE(v_mevcut, 0);

        IF v_fark = 0 THEN
            RETURN QUERY SELECT NULL::BIGINT, 0, TRUE,
                'Sayılan miktar sistemdeki miktarla aynı, hareket kaydı oluşturulmadı.'::TEXT;
            RETURN;
        ELSIF v_fark > 0 THEN
            v_kaynak := NULL;
            v_hedef := p_hedef_lokasyon_id;
            v_miktar := v_fark;
        ELSE
            v_kaynak := p_hedef_lokasyon_id;
            v_hedef := NULL;
            v_miktar := ABS(v_fark);
        END IF;
    ELSE
        v_kaynak := p_kaynak_lokasyon_id;
        v_hedef := p_hedef_lokasyon_id;
        v_miktar := p_miktar;
    END IF;

    -- Yeterli stok kontrolü: kaynak lokasyondan bir şey düşülecekse,
    -- oradaki mevcut miktarı aşamaz (SAYIM_DEVRI'nin azaltma ucu da dahil,
    -- ama matematiksel olarak o zaten hep yeterli çıkar).
    IF v_kaynak IS NOT NULL THEN
        SELECT COALESCE(mevcut_miktar, 0) INTO v_kaynak_mevcut
        FROM v_lokasyon_stok_ozet
        WHERE stok_kodu = p_stok_kodu AND lokasyon_id = v_kaynak;

        IF v_miktar > COALESCE(v_kaynak_mevcut, 0) THEN
            RAISE EXCEPTION 'Yetersiz stok: bu lokasyonda % adet var, % adet çıkış isteniyor.',
                COALESCE(v_kaynak_mevcut, 0), v_miktar;
        END IF;
    END IF;

    INSERT INTO stok_hareketleri
        (istemci_islem_kimligi, stok_kodu, miktar, kaynak_lokasyon_id, hedef_lokasyon_id, islem_tipi, aciklama, yapan_kullanici)
    VALUES
        (p_istemci_islem_kimligi, p_stok_kodu, v_miktar, v_kaynak, v_hedef, p_islem_tipi, p_aciklama, p_yapan_kullanici)
    RETURNING stok_hareketleri.hareket_id INTO v_hareket_id;

    IF p_islem_tipi = 'SAYIM_DEVRI' THEN
        RETURN QUERY SELECT v_hareket_id, v_fark, FALSE,
            format('Fark %s olarak kaydedildi (önceki sistem miktarı: %s, sayılan: %s).', v_fark, v_mevcut, p_miktar)::TEXT;
    ELSE
        RETURN QUERY SELECT v_hareket_id, v_miktar, FALSE, 'Kaydedildi.'::TEXT;
    END IF;
END;
$$;

COMMIT;
