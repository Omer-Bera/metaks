-- =========================================================
-- Migration 007: stok hareketlerine kaplama/montaj/boya/mine kırılımı
--
-- Gerekçe (2026-07-31, kullanıcı kararı): kaplama rengi, kaplama çeşidi ve
-- montaj durumu ÜRÜNÜN değil, o parti STOĞUN özellikleri. Aynı stok kodunun
-- "light gold / askıda" ve "ham / dolap" stoğu ayrı ayrı izlenmeli — tek
-- rakama toplamak iki farklı fiziksel malı aynı sayıymış gibi gösteriyordu.
--
-- Bu alanlar bugüne kadar `urunler`de duruyordu (kaplama_id, boya_mine,
-- montaj_durumu) ve **2.974 satırın hepsinde NULL'dı** (ölçüldü) — yani
-- oradan kaldırmak hiçbir veri kaybetmiyor. Bu migration onları urunler'den
-- DÜŞÜRMÜYOR (bkz. "Kasıtlı kapsam dışı" altta), sadece stok tarafına
-- doğru yerlerini açıyor; Django formu artık onları yazmayacak.
--
-- KOVA KİMLİĞİ kasıtlı olarak dar tutuldu:
--     stok_kodu + lokasyon + kaplama_id + kaplama_cesidi + montaj
-- boya ve mine bilerek kimliğin DIŞINDA — ikisi de serbest metin ve kimlik
-- anahtarına girerlerse "kırmızı", "Kırmızı" ve "kırmızı " üç ayrı stok
-- kovası açar, stok sessizce kaybolur. Onlar partinin açıklayıcı bilgisi.
--
-- UYGULAMA ANI: defterde 5 satır var (hepsi 2026-07-31 11:52–12:14 arası,
-- stok kodu 1005910 üzerinde, omersalihbera@pm.me tarafından). Migration 006
-- defteri boşaltmıştı; bu beş satır ondan SONRA girildi. Yani docs/INFO.md ve
-- CLAUDE.md'nin "defter boş" bilgisi bu migration yazılırken güncel değildi.
--
-- Bu satırların kaplama alanları NULL kalıyor, yani hepsi tek bir
-- "belirtilmemiş kaplama" kovasına düşüyor ve ürün başına TOPLAMLAR
-- DEĞİŞMİYOR (uygulama öncesi/sonrası v_toplam_stok karşılaştırmasıyla
-- doğrulandı). Geriye dönük veri taşımaya gerek yok: kırılımı olmayan
-- geçmiş hareketler "kaplaması bilinmiyor" olarak okunmalı, uydurulmuş bir
-- renge atanmamalı.
--
-- Bu dosya HENÜZ UYGULANMADI. Ortak veritabanına karşı çalıştırmadan
-- önce kullanıcı onayı gerekir.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1) Kaplama renkleri — `kaplamalar` tablosu 2026-07-31 itibarıyla BOŞ
--    duruyordu ve `urunler.kaplama_id` hiçbir satırda dolu değildi.
--    Kullanıcının verdiği 11 renk referans veri olarak buraya giriyor;
--    yeni renk eklemek artık migration değil tek INSERT.
--    ON CONFLICT: migration'ın tekrar çalıştırılması güvenli olsun.
-- ---------------------------------------------------------
INSERT INTO kaplamalar (kaplama_adi) VALUES
    ('ham'),
    ('free nikel'),
    ('light sarı'),
    ('light gold'),
    ('free siyah'),
    ('kalay kaplama'),
    ('kalay oksit'),
    ('bakır oksit'),
    ('siyah oksit'),
    ('antik sarı'),
    ('avrupa siyah oksit')
ON CONFLICT (kaplama_adi) DO NOTHING;

-- ---------------------------------------------------------
-- 2) Defterin yeni kolonları. Hepsi NULL'a izin veriyor: geçmiş/bilinmeyen
--    hareketler "belirtilmemiş" kovasına düşer, NOT NULL koymak defteri
--    doldurulamaz hale getirirdi.
--
--    kaplama_id FK'sı ON DELETE RESTRICT — bir rengi silmek, o renkte
--    hareketi olan defteri sahipsiz bırakmasın (lokasyon FK'larıyla aynı
--    duruş). urunler.kaplama_id ise SET NULL; oradaki niyet farklıydı.
-- ---------------------------------------------------------
ALTER TABLE stok_hareketleri
    ADD COLUMN IF NOT EXISTS kaplama_id     INTEGER     NULL,
    ADD COLUMN IF NOT EXISTS kaplama_cesidi VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS montaj         BOOLEAN     NULL,
    ADD COLUMN IF NOT EXISTS boya           VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS mine           VARCHAR(100) NULL;

ALTER TABLE stok_hareketleri
    ADD CONSTRAINT stok_hareketleri_kaplama_id_fkey
    FOREIGN KEY (kaplama_id) REFERENCES kaplamalar(kaplama_id)
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- Kaplama çeşidi = kaplama YÖNTEMİ (askıda/dolap). İki değer olduğu için
-- referans tablosu değil CHECK: yeni bir yöntem çıkması beklenmiyor, ve
-- iki satırlık bir tablo için JOIN maliyeti anlamsız olurdu.
ALTER TABLE stok_hareketleri
    ADD CONSTRAINT chk_stok_hareketleri_kaplama_cesidi
    CHECK (kaplama_cesidi IS NULL OR kaplama_cesidi IN ('ASKIDA', 'DOLAP'));

-- ---------------------------------------------------------
-- 3) v_lokasyon_stok_ozet: kova kırılımı eklendi.
--
--    Yeni kolonlar SONA eklendi — CREATE OR REPLACE VIEW var olan
--    kolonların adını/tipini/sırasını değiştirmeye izin vermiyor, yalnızca
--    sona ekleme yapılabiliyor. Mevcut yedi kolon birebir korundu.
--
--    ARTIK (stok_kodu, lokasyon) başına BİRDEN FAZLA satır dönebilir —
--    her kova bir satır. Bu, view'ın anlamındaki asıl değişiklik ve
--    aşağıdaki 4. maddede fonksiyonun düzeltilme sebebi.
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_lokasyon_stok_ozet AS
SELECT
    hareket.stok_kodu,
    hareket.lokasyon_id,
    d.lokasyon_adi,
    d.tip AS lokasyon_tipi,
    SUM(hareket.net_miktar) AS mevcut_miktar,
    d.kod    AS lokasyon_kodu,
    d.tam_ad AS lokasyon_tam_adi,
    hareket.kaplama_id,
    kp.kaplama_adi,
    hareket.kaplama_cesidi,
    hareket.montaj
FROM (
    SELECT stok_kodu, hedef_lokasyon_id AS lokasyon_id, miktar AS net_miktar,
           kaplama_id, kaplama_cesidi, montaj
    FROM stok_hareketleri
    WHERE hedef_lokasyon_id IS NOT NULL
    UNION ALL
    SELECT stok_kodu, kaynak_lokasyon_id AS lokasyon_id, -miktar AS net_miktar,
           kaplama_id, kaplama_cesidi, montaj
    FROM stok_hareketleri
    WHERE kaynak_lokasyon_id IS NOT NULL
) hareket
JOIN v_lokasyonlar_detay d ON d.lokasyon_id = hareket.lokasyon_id
LEFT JOIN kaplamalar kp ON kp.kaplama_id = hareket.kaplama_id
GROUP BY hareket.stok_kodu, hareket.lokasyon_id, d.lokasyon_adi, d.tip,
         d.kod, d.tam_ad,
         hareket.kaplama_id, kp.kaplama_adi, hareket.kaplama_cesidi, hareket.montaj;

-- v_toplam_stok, v_fiziksel_stok ve v_numune_konumlari BİLEREK
-- değiştirilmedi. İlk ikisi zaten `SUM(mevcut_miktar) GROUP BY stok_kodu`
-- yapıyor; altlarındaki satır sayısı artınca sonuç aynı kalıyor (ürün
-- başına tek toplam). Bu önemli: katalogdaki "sadece stokta olanlar"
-- filtresi, ana ekranın sayım ilerlemesi ve stok kartlarındaki tek rakam
-- hepsi "ürün başına tek satır" sözleşmesine dayanıyor — kırılımı oraya
-- taşımak üçünü birden sessizce bozardı. Kırılıma ihtiyacı olan tek yer
-- detay dökümü, o da zaten v_lokasyon_stok_ozet'ten okuyor.

-- ---------------------------------------------------------
-- 4) stok_hareketi_kaydet(): kova farkındalığı
--
--    DROP şart: PostgreSQL fonksiyonları (ad + argüman tipleri) ile
--    tanımlar. Yeni parametreleri DEFAULT'lu eklemek CREATE OR REPLACE ile
--    eski fonksiyonu değiştirmez, YANINA ikinci bir aşırı yükleme koyar ve
--    Django'nun 8 argümanlı çağrısı "function is not unique" ile belirsiz
--    hale gelirdi. Önce eski imza düşürülüyor.
--
--    Yeni parametreler sona eklendi ve hepsi DEFAULT NULL — yani mevcut
--    8 argümanlı çağrılar (Django stok_servisi.py) değişmeden çalışmaya
--    devam ediyor, kovası "belirtilmemiş" olur.
-- ---------------------------------------------------------
DROP FUNCTION IF EXISTS stok_hareketi_kaydet(
    UUID, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER, TEXT, VARCHAR
);

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
    v_mevcut INTEGER;
    v_fark INTEGER;
    v_hareket_id BIGINT;
    v_kaynak INTEGER;
    v_hedef INTEGER;
    v_miktar INTEGER;
    v_kaynak_mevcut INTEGER;
    v_ust_ad VARCHAR;
    v_kova TEXT;
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

    -- Kova alanlarının doğrulaması. CHECK/FK zaten koruyor ama oradan
    -- gelen mesaj İngilizce ve kısıt adı içeriyor; kullanıcıya gösterilen
    -- metin bu fonksiyonun sorumluluğu (projenin geri kalanıyla aynı duruş).
    IF p_kaplama_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM kaplamalar kp WHERE kp.kaplama_id = p_kaplama_id) THEN
        RAISE EXCEPTION 'Kaplama rengi bulunamadı (id: %).', p_kaplama_id;
    END IF;

    IF p_kaplama_cesidi IS NOT NULL AND p_kaplama_cesidi NOT IN ('ASKIDA', 'DOLAP') THEN
        RAISE EXCEPTION 'Kaplama çeşidi yalnızca ASKIDA ya da DOLAP olabilir (gelen: %).',
            p_kaplama_cesidi;
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
    -- TRANSFER'de kova TAŞINIR: mal fiziksel olarak aynı kaplamada
    -- kalıyor, yani tek kova parametresi seti iki uca da uygulanıyor.

    -- (004'ten AYNEN korunuyor) sadece yaprak lokasyona hareket yazılabilir.
    -- Alt lokasyonu olan bir lokasyon (örn. "Numune Dolabı 1") kaynak ya da
    -- hedef olarak verilirse reddedilir. v_lokasyonlar_detay.yaprak_mi ile
    -- birebir aynı tanım.
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

    -- Hata mesajlarında kullanılacak okunur kova adı.
    SELECT COALESCE(
        NULLIF(
            concat_ws(' · ',
                (SELECT kp.kaplama_adi FROM kaplamalar kp WHERE kp.kaplama_id = p_kaplama_id),
                CASE p_kaplama_cesidi WHEN 'ASKIDA' THEN 'askıda'
                                      WHEN 'DOLAP'  THEN 'dolap' END,
                CASE WHEN p_montaj IS TRUE THEN 'montajlı'
                     WHEN p_montaj IS FALSE THEN 'montajsız' END
            ), ''),
        'belirtilmemiş kaplama')
    INTO v_kova;

    IF p_islem_tipi = 'SAYIM_DEVRI' THEN
        IF p_hedef_lokasyon_id IS NULL THEN
            RAISE EXCEPTION 'SAYIM_DEVRI için sayımın yapıldığı lokasyon (p_hedef_lokasyon_id) zorunludur';
        END IF;

        -- Sayım artık KOVA bazında: "bu lokasyonda light gold/askıda olan
        -- kaç adet" sorusunun cevabı. IS NOT DISTINCT FROM şart — kovanın
        -- alanları NULL olabiliyor ve `= NULL` hiçbir zaman eşleşmezdi,
        -- yani belirtilmemiş kova hep 0 okunup her sayımda sahte fark
        -- yazardı.
        SELECT COALESCE(o.mevcut_miktar, 0) INTO v_mevcut
        FROM v_lokasyon_stok_ozet o
        WHERE o.stok_kodu = p_stok_kodu
          AND o.lokasyon_id = p_hedef_lokasyon_id
          AND o.kaplama_id     IS NOT DISTINCT FROM p_kaplama_id
          AND o.kaplama_cesidi IS NOT DISTINCT FROM p_kaplama_cesidi
          AND o.montaj         IS NOT DISTINCT FROM p_montaj;

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

    -- Yeterli stok kontrolü — artık KOVA bazında. Bu, kırılımın asıl
    -- sebebi: "light gold" stoğundan çıkış yaparken "ham" stoğunun
    -- bakiyesine bakmak yanlış cevap verirdi.
    IF v_kaynak IS NOT NULL THEN
        SELECT COALESCE(o.mevcut_miktar, 0) INTO v_kaynak_mevcut
        FROM v_lokasyon_stok_ozet o
        WHERE o.stok_kodu = p_stok_kodu
          AND o.lokasyon_id = v_kaynak
          AND o.kaplama_id     IS NOT DISTINCT FROM p_kaplama_id
          AND o.kaplama_cesidi IS NOT DISTINCT FROM p_kaplama_cesidi
          AND o.montaj         IS NOT DISTINCT FROM p_montaj;

        IF v_miktar > COALESCE(v_kaynak_mevcut, 0) THEN
            RAISE EXCEPTION 'Yetersiz stok: bu lokasyonda "%" için % adet var, % adet çıkış isteniyor.',
                v_kova, COALESCE(v_kaynak_mevcut, 0), v_miktar;
        END IF;
    END IF;

    INSERT INTO stok_hareketleri
        (istemci_islem_kimligi, stok_kodu, miktar, kaynak_lokasyon_id, hedef_lokasyon_id,
         islem_tipi, aciklama, yapan_kullanici,
         kaplama_id, kaplama_cesidi, montaj, boya, mine)
    VALUES
        (p_istemci_islem_kimligi, p_stok_kodu, v_miktar, v_kaynak, v_hedef,
         p_islem_tipi, p_aciklama, p_yapan_kullanici,
         p_kaplama_id, p_kaplama_cesidi, p_montaj,
         NULLIF(btrim(p_boya), ''), NULLIF(btrim(p_mine), ''))
    RETURNING stok_hareketleri.hareket_id INTO v_hareket_id;

    IF p_islem_tipi = 'SAYIM_DEVRI' THEN
        RETURN QUERY SELECT v_hareket_id, v_fark, FALSE,
            format('Fark %s olarak kaydedildi (%s — önceki sistem miktarı: %s, sayılan: %s).',
                   v_fark, v_kova, v_mevcut, p_miktar)::TEXT;
    ELSE
        RETURN QUERY SELECT v_hareket_id, v_miktar, FALSE, 'Kaydedildi.'::TEXT;
    END IF;
END;
$$;

COMMIT;

-- =========================================================
-- Kasıtlı kapsam dışı
--
-- 1) `urunler.kaplama_id`, `urunler.boya_mine`, `urunler.montaj_durumu`
--    kolonları DÜŞÜRÜLMEDİ. Üçü de 2.974 satırın hepsinde NULL, yani
--    Django formundan çıkarmak veri kaybetmiyor ve kolonları düşürmek
--    bugün hiçbir şey kazandırmıyor — buna karşılık `urun_kaydet()`'in
--    imzasını da değiştirmeyi gerektirirdi (ikinci bir DROP FUNCTION,
--    ikinci bir geri alma riski). Boş kolon zararsız; gerçekten
--    gerekirse ayrı ve küçük bir migration'ın işi.
--
-- 2) Ek indeks eklenmedi. Kova sorguları view üzerinden tam tarama
--    yapıyor ama defter bugün 0 satır; ölçmeden indeks eklemek erken
--    optimizasyon olurdu. Defter büyüdüğünde (stok_kodu, kaplama_id)
--    bileşik indeksi ilk bakılacak yer.
-- =========================================================
