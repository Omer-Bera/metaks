-- =========================================================
-- Migration 007 ROLLBACK: stok kaplama kırılımını geri al
--
-- Sıra önemli ve şu mantıkta: view'lar yeni kolonlara BAĞIMLI, o yüzden
-- önce view'lar 007 öncesi haline döndürülüyor, sonra kolonlar düşürülüyor.
-- Ters sırada "cannot drop column ... because other objects depend on it"
-- alınırdı.
--
-- CREATE OR REPLACE VIEW kolon SİLEMEZ (yalnızca sona ekleyebilir), bu
-- yüzden dört view'ın da DROP + yeniden yaratılması şart. Dördü de
-- v_lokasyon_stok_ozet'e bağlı olduğu için bağımlılık sırasıyla
-- düşürülüyor: yapraklar önce, kök sonra.
--
-- Fonksiyonun geri yazılan hali migration 003 dosyasındaki DEĞİL, uygulama
-- anındaki CANLI hali — yani 004'ün eklediği yaprak-lokasyon kontrolünü
-- içeriyor (pg_get_functiondef ile alındı). 003'ün dosyasından kopyalamak
-- o güvenlik kuralını sessizce düşürürdü.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1) View'ları 007 öncesi tanımlarına döndür
-- ---------------------------------------------------------
DROP VIEW IF EXISTS v_numune_konumlari;
DROP VIEW IF EXISTS v_fiziksel_stok;
DROP VIEW IF EXISTS v_toplam_stok;
DROP VIEW IF EXISTS v_lokasyon_stok_ozet;

CREATE VIEW v_lokasyon_stok_ozet AS
SELECT
    hareket.stok_kodu,
    hareket.lokasyon_id,
    d.lokasyon_adi,
    d.tip AS lokasyon_tipi,
    SUM(hareket.net_miktar) AS mevcut_miktar,
    d.kod    AS lokasyon_kodu,
    d.tam_ad AS lokasyon_tam_adi
FROM (
    SELECT stok_kodu, hedef_lokasyon_id AS lokasyon_id, miktar AS net_miktar
    FROM stok_hareketleri
    WHERE hedef_lokasyon_id IS NOT NULL
    UNION ALL
    SELECT stok_kodu, kaynak_lokasyon_id AS lokasyon_id, -miktar AS net_miktar
    FROM stok_hareketleri
    WHERE kaynak_lokasyon_id IS NOT NULL
) hareket
JOIN v_lokasyonlar_detay d ON d.lokasyon_id = hareket.lokasyon_id
GROUP BY hareket.stok_kodu, hareket.lokasyon_id, d.lokasyon_adi, d.tip, d.kod, d.tam_ad;

CREATE VIEW v_toplam_stok AS
SELECT
    stok_kodu,
    SUM(mevcut_miktar) AS toplam_miktar
FROM v_lokasyon_stok_ozet
WHERE lokasyon_tipi <> 'NUMUNE'
GROUP BY stok_kodu;

CREATE VIEW v_fiziksel_stok AS
SELECT
    stok_kodu,
    SUM(mevcut_miktar) AS toplam_miktar
FROM v_lokasyon_stok_ozet
GROUP BY stok_kodu;

CREATE VIEW v_numune_konumlari AS
SELECT
    stok_kodu,
    lokasyon_id,
    lokasyon_kodu,
    lokasyon_tam_adi,
    mevcut_miktar
FROM v_lokasyon_stok_ozet
WHERE lokasyon_tipi = 'NUMUNE' AND mevcut_miktar > 0;

-- ---------------------------------------------------------
-- 2) Fonksiyonu 007 öncesi (8 parametreli) haline döndür
-- ---------------------------------------------------------
DROP FUNCTION IF EXISTS stok_hareketi_kaydet(
    UUID, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER, TEXT, VARCHAR,
    INTEGER, VARCHAR, BOOLEAN, VARCHAR, VARCHAR
);

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
    v_ust_ad VARCHAR;
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

    -- YENİ (004): sadece yaprak lokasyona hareket yazılabilir. Alt
    -- lokasyonu olan bir lokasyon (örn. "Numune Dolabı 1") kaynak ya da
    -- hedef olarak verilirse reddedilir. v_lokasyonlar_detay.yaprak_mi
    -- ile birebir aynı tanım.
    IF p_kaynak_lokasyon_id IS NOT NULL
       AND EXISTS (SELECT 1 FROM lokasyonlar c WHERE c.ust_lokasyon_id = p_kaynak_lokasyon_id) THEN
        SELECT l.lokasyon_adi INTO v_ust_ad FROM lokasyonlar l WHERE l.lokasyon_id = p_kaynak_lokasyon_id;
        RAISE EXCEPTION '"%" bir üst lokasyondur (alt lokasyonları var); stok hareketi doğrudan buraya yazılamaz, alt lokasyonlardan birini seçin.', v_ust_ad;
    END IF;

    IF p_hedef_lokasyon_id IS NOT NULL
       AND EXISTS (SELECT 1 FROM lokasyonlar c WHERE c.ust_lokasyon_id = p_hedef_lokasyon_id) THEN
        SELECT l.lokasyon_adi INTO v_ust_ad FROM lokasyonlar l WHERE l.lokasyon_id = p_hedef_lokasyon_id;
        RAISE EXCEPTION '"%" bir üst lokasyondur (alt lokasyonları var); stok hareketi doğrudan buraya yazılamaz, alt lokasyonlardan birini seçin.', v_ust_ad;
    END IF;

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

-- ---------------------------------------------------------
-- 3) Defterin yeni kolonları ve kısıtları
-- ---------------------------------------------------------
ALTER TABLE stok_hareketleri
    DROP CONSTRAINT IF EXISTS chk_stok_hareketleri_kaplama_cesidi;

ALTER TABLE stok_hareketleri
    DROP CONSTRAINT IF EXISTS stok_hareketleri_kaplama_id_fkey;

ALTER TABLE stok_hareketleri
    DROP COLUMN IF EXISTS kaplama_id,
    DROP COLUMN IF EXISTS kaplama_cesidi,
    DROP COLUMN IF EXISTS montaj,
    DROP COLUMN IF EXISTS boya,
    DROP COLUMN IF EXISTS mine;

-- ---------------------------------------------------------
-- 4) 007'nin eklediği 11 kaplama rengi
--
-- NOT EXISTS koruması bilinçli: bu arada bir ürüne renk atanmışsa o satır
-- YERİNDE BIRAKILIYOR. urunler.kaplama_id FK'sı ON DELETE SET NULL, yani
-- korumasız bir DELETE hata vermez — sessizce o ürünün rengini siler.
-- Rollback'in veri kaybettirmesi kabul edilemez; eksik temizlik yeğdir.
-- ---------------------------------------------------------
DELETE FROM kaplamalar k
WHERE k.kaplama_adi IN (
        'ham', 'free nikel', 'light sarı', 'light gold', 'free siyah',
        'kalay kaplama', 'kalay oksit', 'bakır oksit', 'siyah oksit',
        'antik sarı', 'avrupa siyah oksit'
      )
  AND NOT EXISTS (SELECT 1 FROM urunler u WHERE u.kaplama_id = k.kaplama_id);

COMMIT;
