-- =========================================================
-- Migration 003: mükerrer gönderim koruması + atomik stok hareketi fonksiyonu
-- Appsmith StokIslemi sayfasının KaydetButton'ı için — bkz.
-- docs/aktif-urun-veri-sozlesmesi.md
--
-- 2026-07-29 revizyonu: "master plan" prompt'unun Prompt 3 gereksinimleri
-- ışığında üç kontrol daha eklendi — yeterli stok kontrolü, işlemi yapan
-- kullanıcı zorunluluğu, işlem tipine göre lokasyon zorunluluğu.
--
-- Bu dosya HENÜZ UYGULANMADI. Ortak veritabanına karşı çalıştırmadan
-- önce kullanıcı onayı gerekir.
-- =========================================================

BEGIN;

-- 1) İstemci tarafında (Appsmith'te, buton tıklanınca) üretilen bir UUID —
--    mükerrer gönderim koruması için (bkz. fonksiyon içindeki kontrol).
ALTER TABLE stok_hareketleri
    ADD COLUMN IF NOT EXISTS istemci_islem_kimligi UUID NULL;

ALTER TABLE stok_hareketleri
    ADD CONSTRAINT uq_stok_hareketleri_istemci_kimligi
    UNIQUE (istemci_islem_kimligi);

-- 2) İşlemi yapan kullanıcı. Appsmith'in kendi kullanıcı sistemi ile
--    Postgres bağlantısı arasında 1-1 eşleşme yok (herkes aynı depo_admin
--    ile bağlanıyor) — bu yüzden Postgres'in current_user'ına güvenilemez,
--    değer Appsmith'ten ({{ appsmith.user.email }}) parametre olarak
--    açıkça geçirilmeli. Tablo boş olduğu için NOT NULL, DEFAULT'suz
--    ekleniyor — bundan sonraki her satır bunu zorunlu taşıyacak.
ALTER TABLE stok_hareketleri
    ADD COLUMN IF NOT EXISTS yapan_kullanici VARCHAR(255) NOT NULL;

-- 3) Tek giriş noktası: Appsmith'in KaydetButton'ı SADECE bu fonksiyonu
--    çağırmalı, stok_hareketleri'ne doğrudan INSERT atmamalı. Aşağıdaki
--    kontrolleri uygular:
--      - istemci_islem_kimligi ile mükerrer gönderim koruması
--      - yapan_kullanici zorunlu
--      - miktar > 0 (SAYIM_DEVRI'de sayılan toplam >= 0)
--      - işlem tipine göre lokasyon zorunluluğu (GIRIS->hedef, CIKIS->kaynak,
--        TRANSFER->ikisi, DUZELTME->en az biri)
--      - kaynak lokasyondan düşülecek miktar oradaki mevcut miktarı aşamaz
--        (CIKIS, TRANSFER'in kaynak ucu, DUZELTME'nin azaltma ucu için)
--      - SAYIM_DEVRI: p_miktar sayılan TOPLAM bakiyedir, fonksiyon farkı
--        kendisi hesaplayıp gerçek ledger hareketini yazar (fark sıfırsa
--        hiçbir satır eklenmez)
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
