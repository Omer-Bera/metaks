-- =========================================================
-- Migration 003: mükerrer gönderim koruması + atomik stok hareketi fonksiyonu
-- Appsmith StokIslemi sayfasının KaydetButton'ı için — bkz.
-- docs/aktif-urun-veri-sozlesmesi.md
--
-- Bu dosya HENÜZ UYGULANMADI. Ortak veritabanına karşı çalıştırmadan
-- önce kullanıcı onayı gerekir.
-- =========================================================

BEGIN;

-- 1) İstemci tarafında (Appsmith'te, buton tıklanınca) üretilen bir UUID.
--    Aynı UUID ile ikinci bir çağrı gelirse (çift tıklama, ağ tekrar denemesi)
--    fonksiyon yeni bir satır eklemez, ilk sonucu döndürür. NULL'a izin
--    verilir (ileride toplu/manuel eklenen satırlar için gerekmeyebilir),
--    UNIQUE kısıtı NULL'ları birden fazla kez kabul eder (Postgres normal
--    davranışı), sadece dolu değerler için tekrarı engeller.
ALTER TABLE stok_hareketleri
    ADD COLUMN IF NOT EXISTS istemci_islem_kimligi UUID NULL;

ALTER TABLE stok_hareketleri
    ADD CONSTRAINT uq_stok_hareketleri_istemci_kimligi
    UNIQUE (istemci_islem_kimligi);

-- 2) Tek giriş noktası: Appsmith'in KaydetButton'ı SADECE bu fonksiyonu
--    çağırmalı, stok_hareketleri'ne doğrudan INSERT atmamalı.
--
--    SAYIM_DEVRI özel durumu: p_miktar burada hareketin kendisi DEĞİL,
--    personelin fiziksel olarak SAYDIĞI TOPLAM bakiyedir. Fonksiyon,
--    v_lokasyon_stok_ozet'teki mevcut miktarla farkını kendisi hesaplayıp
--    gerçek ledger hareketini (fark) yazar. Sayım lokasyonu her zaman
--    p_hedef_lokasyon_id parametresiyle verilir; fark negatifse (sayılan
--    < mevcut) fonksiyon bunu otomatik olarak o lokasyondan bir çıkış
--    (kaynak_lokasyon_id) olarak kaydeder.
--
--    Diğer tüm işlem tipleri (GIRIS/CIKIS/TRANSFER/DUZELTME) için p_miktar
--    doğrudan hareket miktarıdır, caller kaynak/hedef lokasyonu kendi
--    belirler (schema'daki CHECK constraint'ler TRANSFER için ikisinin de
--    dolu ve farklı olmasını zaten zorunlu kılıyor).
CREATE OR REPLACE FUNCTION stok_hareketi_kaydet(
    p_istemci_islem_kimligi UUID,
    p_stok_kodu VARCHAR,
    p_islem_tipi VARCHAR,
    p_miktar INTEGER,
    p_kaynak_lokasyon_id INTEGER DEFAULT NULL,
    p_hedef_lokasyon_id INTEGER DEFAULT NULL,
    p_aciklama TEXT DEFAULT NULL
) RETURNS TABLE (hareket_id BIGINT, uygulanan_miktar INTEGER, atlandi BOOLEAN, mesaj TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_mevcut INTEGER;
    v_fark INTEGER;
    v_hareket_id BIGINT;
BEGIN
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
            INSERT INTO stok_hareketleri
                (istemci_islem_kimligi, stok_kodu, miktar, hedef_lokasyon_id, islem_tipi, aciklama)
            VALUES
                (p_istemci_islem_kimligi, p_stok_kodu, v_fark, p_hedef_lokasyon_id, 'SAYIM_DEVRI', p_aciklama)
            RETURNING stok_hareketleri.hareket_id INTO v_hareket_id;
        ELSE
            INSERT INTO stok_hareketleri
                (istemci_islem_kimligi, stok_kodu, miktar, kaynak_lokasyon_id, islem_tipi, aciklama)
            VALUES
                (p_istemci_islem_kimligi, p_stok_kodu, ABS(v_fark), p_hedef_lokasyon_id, 'SAYIM_DEVRI', p_aciklama)
            RETURNING stok_hareketleri.hareket_id INTO v_hareket_id;
        END IF;

        RETURN QUERY SELECT v_hareket_id, v_fark, FALSE,
            format('Fark %s olarak kaydedildi (önceki sistem miktarı: %s, sayılan: %s).', v_fark, v_mevcut, p_miktar)::TEXT;
        RETURN;
    END IF;

    INSERT INTO stok_hareketleri
        (istemci_islem_kimligi, stok_kodu, miktar, kaynak_lokasyon_id, hedef_lokasyon_id, islem_tipi, aciklama)
    VALUES
        (p_istemci_islem_kimligi, p_stok_kodu, p_miktar, p_kaynak_lokasyon_id, p_hedef_lokasyon_id, p_islem_tipi, p_aciklama)
    RETURNING stok_hareketleri.hareket_id INTO v_hareket_id;

    RETURN QUERY SELECT v_hareket_id, p_miktar, FALSE, 'Kaydedildi.'::TEXT;
END;
$$;

COMMIT;
