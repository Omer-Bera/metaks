-- =========================================================
-- Migration 008: ürün/SKU ayrımı, stok belgeleri ve fason iş emirleri
--
-- Bu migration EKLEMELİDİR. Mevcut urunler ve stok_hareketleri satırlarını
-- silmez; her ürün için aynı kodlu bir BELIRSIZ (miras) SKU açar ve geçmiş
-- hareketleri bu SKU ile yeni stok belgesi başlıklarına bağlar.
--
-- Ortak veritabanına uygulamadan önce AGENTS.md uyarıları gereği yedek,
-- disposable kopya testi ve kullanıcı onayı zorunludur.
-- =========================================================

BEGIN;

-- Stokta fiziksel konumdan bağımsız kullanılabilirlik durumu.
CREATE TABLE stok_durumlari (
    stok_durumu_kodu VARCHAR(30) PRIMARY KEY,
    stok_durumu_adi VARCHAR(100) NOT NULL UNIQUE,
    kullanilabilir_mi BOOLEAN NOT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO stok_durumlari
    (stok_durumu_kodu, stok_durumu_adi, kullanilabilir_mi)
VALUES
    ('SERBEST', 'Serbest', TRUE),
    ('KALITE_BEKLIYOR', 'Kalite bekliyor', FALSE),
    ('BLOKE', 'Bloke', FALSE);

-- Mine ve boya renkleri serbest metin yerine ortak, kontrollü referanstır.
CREATE TABLE renkler (
    renk_id SERIAL PRIMARY KEY,
    renk_adi VARCHAR(100) NOT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_renkler_adi_ci ON renkler (lower(btrim(renk_adi)));

-- Müşteri/tedarikçi/fasoncu aynı tüzel kişi olabilir; roller ayrı tutulur.
CREATE TABLE is_ortaklari (
    is_ortagi_id BIGSERIAL PRIMARY KEY,
    kod VARCHAR(50) NOT NULL UNIQUE,
    unvan VARCHAR(255) NOT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
    olusturan_kullanici VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE is_ortagi_rolleri (
    is_ortagi_id BIGINT NOT NULL REFERENCES is_ortaklari(is_ortagi_id) ON DELETE CASCADE,
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('MUSTERI', 'TEDARIKCI', 'FASONCU')),
    PRIMARY KEY (is_ortagi_id, rol)
);

ALTER TABLE lokasyonlar
    ADD COLUMN is_ortagi_id BIGINT NULL
        REFERENCES is_ortaklari(is_ortagi_id) ON DELETE RESTRICT;

-- Mevcut FASON lokasyonları veri kaybetmeden birer fasoncu kaydına bağlanır.
INSERT INTO is_ortaklari (kod, unvan)
SELECT 'FASON-' || l.lokasyon_id::TEXT, l.lokasyon_adi
FROM lokasyonlar l
WHERE l.tip = 'FASON'
ON CONFLICT (kod) DO NOTHING;

INSERT INTO is_ortagi_rolleri (is_ortagi_id, rol)
SELECT io.is_ortagi_id, 'FASONCU'
FROM is_ortaklari io
WHERE io.kod LIKE 'FASON-%'
ON CONFLICT DO NOTHING;

UPDATE lokasyonlar l
SET is_ortagi_id = io.is_ortagi_id
FROM is_ortaklari io
WHERE l.tip = 'FASON'
  AND l.is_ortagi_id IS NULL
  AND io.kod = 'FASON-' || l.lokasyon_id::TEXT;

CREATE INDEX idx_lokasyonlar_is_ortagi ON lokasyonlar(is_ortagi_id);

CREATE OR REPLACE FUNCTION is_ortagi_kaydet(
    p_kod VARCHAR,
    p_unvan VARCHAR,
    p_roller JSONB,
    p_yapan_kullanici VARCHAR
) RETURNS TABLE (is_ortagi_id BIGINT, atlandi BOOLEAN, mesaj TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_rol TEXT;
BEGIN
    IF NULLIF(btrim(p_kod), '') IS NULL OR NULLIF(btrim(p_unvan), '') IS NULL THEN
        RAISE EXCEPTION 'İş ortağı kodu ve unvanı zorunludur.';
    END IF;
    IF NULLIF(btrim(p_yapan_kullanici), '') IS NULL THEN
        RAISE EXCEPTION 'İşlemi yapan kullanıcı zorunludur.';
    END IF;
    IF jsonb_typeof(p_roller) <> 'array' OR jsonb_array_length(p_roller) = 0 THEN
        RAISE EXCEPTION 'En az bir iş ortağı rolü seçilmelidir.';
    END IF;

    SELECT io.is_ortagi_id INTO v_id FROM is_ortaklari io WHERE io.kod = btrim(p_kod);
    IF FOUND THEN
        RETURN QUERY SELECT v_id, TRUE, 'Bu kodlu iş ortağı zaten kayıtlı.'::TEXT;
        RETURN;
    END IF;

    INSERT INTO is_ortaklari (kod, unvan, olusturan_kullanici)
    VALUES (btrim(p_kod), btrim(p_unvan), p_yapan_kullanici)
    RETURNING is_ortaklari.is_ortagi_id INTO v_id;

    FOR v_rol IN SELECT jsonb_array_elements_text(p_roller)
    LOOP
        IF v_rol NOT IN ('MUSTERI', 'TEDARIKCI', 'FASONCU') THEN
            RAISE EXCEPTION 'Geçersiz iş ortağı rolü: "%".', v_rol;
        END IF;
        INSERT INTO is_ortagi_rolleri (is_ortagi_id, rol) VALUES (v_id, v_rol);
    END LOOP;

    RETURN QUERY SELECT v_id, FALSE, 'İş ortağı oluşturuldu.'::TEXT;
END;
$$;

-- Ürün katalog kimliğidir; stok_kalemi (SKU) ise ayrı sevk edilebilir varyanttır.
CREATE TABLE stok_kalemleri (
    stok_kalemi_id BIGSERIAL PRIMARY KEY,
    sku_kodu VARCHAR(100) NOT NULL UNIQUE,
    urun_kodu VARCHAR(100) NOT NULL
        REFERENCES urunler(stok_kodu) ON UPDATE CASCADE ON DELETE RESTRICT,
    nitelik_durumu VARCHAR(20) NOT NULL DEFAULT 'TANIMLI'
        CHECK (nitelik_durumu IN ('BELIRSIZ', 'TANIMLI')),
    kaplama_id INTEGER NULL REFERENCES kaplamalar(kaplama_id) ON DELETE RESTRICT,
    boya_renk_id INTEGER NULL REFERENCES renkler(renk_id) ON DELETE RESTRICT,
    mine_renk_id INTEGER NULL REFERENCES renkler(renk_id) ON DELETE RESTRICT,
    montaj_durumu VARCHAR(20) NOT NULL DEFAULT 'BELIRSIZ'
        CHECK (montaj_durumu IN ('BELIRSIZ', 'HAM', 'YARI_MONTE', 'MONTE')),
    satilabilir_mi BOOLEAN NOT NULL DEFAULT TRUE,
    stoklanabilir_mi BOOLEAN NOT NULL DEFAULT TRUE,
    kritik_stok_esigi INTEGER NOT NULL DEFAULT 0 CHECK (kritik_stok_esigi >= 0),
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
    olusturan_kullanici VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_stok_kalemleri_nitelik
    ON stok_kalemleri (
        urun_kodu,
        COALESCE(kaplama_id, -1),
        COALESCE(boya_renk_id, -1),
        COALESCE(mine_renk_id, -1),
        montaj_durumu
    )
    WHERE nitelik_durumu = 'TANIMLI';

CREATE INDEX idx_stok_kalemleri_urun ON stok_kalemleri(urun_kodu);

-- Mevcut kodun ne ham ne de kaplamalı olduğu varsayılır: BELIRSIZ miras SKU.
INSERT INTO stok_kalemleri (
    sku_kodu, urun_kodu, nitelik_durumu, montaj_durumu,
    satilabilir_mi, stoklanabilir_mi, kritik_stok_esigi, aktif_mi
)
SELECT
    u.stok_kodu, u.stok_kodu, 'BELIRSIZ', 'BELIRSIZ',
    TRUE, u.stok_takip_edilsin_mi, u.kritik_stok_esigi, TRUE
FROM urunler u
ON CONFLICT (sku_kodu) DO NOTHING;

-- Parti kontrolü SKU bazında isteğe bağlıdır; geriye dönük zorunluluk yoktur.
CREATE TABLE stok_partileri (
    parti_id BIGSERIAL PRIMARY KEY,
    stok_kalemi_id BIGINT NOT NULL
        REFERENCES stok_kalemleri(stok_kalemi_id) ON DELETE RESTRICT,
    parti_no VARCHAR(100) NOT NULL,
    tedarikci_parti_no VARCHAR(100) NULL,
    uretim_tarihi DATE NULL,
    aciklama TEXT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (stok_kalemi_id, parti_no)
);
CREATE UNIQUE INDEX uq_stok_partileri_no_ci
    ON stok_partileri (stok_kalemi_id, lower(btrim(parti_no)));

-- Fason iş emri planlanan akışı taşır; gerçekleşen miktarlar stok defterinden okunur.
CREATE TABLE fason_is_emirleri (
    fason_is_emri_id BIGSERIAL PRIMARY KEY,
    istemci_islem_kimligi UUID NOT NULL UNIQUE,
    emir_no VARCHAR(30) NULL UNIQUE,
    is_ortagi_id BIGINT NOT NULL
        REFERENCES is_ortaklari(is_ortagi_id) ON DELETE RESTRICT,
    fason_lokasyon_id INTEGER NOT NULL
        REFERENCES lokasyonlar(lokasyon_id) ON DELETE RESTRICT,
    kaynak_stok_kalemi_id BIGINT NOT NULL
        REFERENCES stok_kalemleri(stok_kalemi_id) ON DELETE RESTRICT,
    hedef_stok_kalemi_id BIGINT NOT NULL
        REFERENCES stok_kalemleri(stok_kalemi_id) ON DELETE RESTRICT,
    islem_turu VARCHAR(30) NOT NULL
        CHECK (islem_turu IN ('KAPLAMA', 'MINE', 'BOYA', 'MONTAJ', 'DIGER')),
    kaplama_cesidi VARCHAR(20) NULL
        CHECK (kaplama_cesidi IS NULL OR kaplama_cesidi IN ('ASKIDA', 'DOLAP')),
    planlanan_miktar INTEGER NOT NULL CHECK (planlanan_miktar > 0),
    beklenen_donus_tarihi DATE NULL,
    durum VARCHAR(20) NOT NULL DEFAULT 'ACIK'
        CHECK (durum IN ('ACIK', 'TAMAMLANDI', 'IPTAL')),
    aciklama TEXT NULL,
    olusturan_kullanici VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fason_is_emirleri_durum ON fason_is_emirleri(durum, beklenen_donus_tarihi);

CREATE TABLE stok_islem_nedenleri (
    islem_nedeni VARCHAR(30) PRIMARY KEY,
    islem_adi VARCHAR(100) NOT NULL UNIQUE,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO stok_islem_nedenleri (islem_nedeni, islem_adi) VALUES
    ('SATIN_ALMA_KABUL', 'Satın alma kabulü'),
    ('URETIM_GIRIS', 'Üretimden giriş'),
    ('SATIS_SEVKI', 'Satış sevkiyatı'),
    ('IC_TRANSFER', 'İç transfer'),
    ('FASON_SEVK', 'Fasona sevk'),
    ('FASON_DONUS', 'Fasondan dönüş'),
    ('SAYIM', 'Sayım'),
    ('DUZELTME', 'Düzeltme'),
    ('FIRE', 'Fire'),
    ('MUSTERI_IADE', 'Müşteri iadesi'),
    ('TEDARIKCI_IADE', 'Tedarikçi iadesi'),
    ('STOK_SINIFLANDIRMA', 'Stok sınıflandırma'),
    ('MIRAS_HAREKET', 'Miras hareket');

-- Belge başlığı iş amacını, karşı tarafı ve çok satırlı atomik işlemi birleştirir.
CREATE TABLE stok_islemleri (
    stok_islem_id BIGSERIAL PRIMARY KEY,
    istemci_islem_kimligi UUID NOT NULL UNIQUE,
    islem_nedeni VARCHAR(30) NOT NULL
        REFERENCES stok_islem_nedenleri(islem_nedeni) ON DELETE RESTRICT,
    is_ortagi_id BIGINT NULL
        REFERENCES is_ortaklari(is_ortagi_id) ON DELETE RESTRICT,
    belge_no VARCHAR(100) NULL,
    fason_is_emri_id BIGINT NULL
        REFERENCES fason_is_emirleri(fason_is_emri_id) ON DELETE RESTRICT,
    duzelttigi_stok_islem_id BIGINT NULL
        REFERENCES stok_islemleri(stok_islem_id) ON DELETE RESTRICT,
    aciklama TEXT NULL,
    yapan_kullanici VARCHAR(255) NOT NULL,
    miras_hareket_id BIGINT NULL UNIQUE,
    islem_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stok_islemleri_neden ON stok_islemleri(islem_nedeni, islem_tarihi);
CREATE INDEX idx_stok_islemleri_fason ON stok_islemleri(fason_is_emri_id);
CREATE UNIQUE INDEX uq_stok_islemleri_belge
    ON stok_islemleri (
        islem_nedeni,
        COALESCE(is_ortagi_id, -1),
        lower(btrim(belge_no))
    )
    WHERE belge_no IS NOT NULL AND btrim(belge_no) <> '';

ALTER TABLE stok_hareketleri
    ADD COLUMN stok_islem_id BIGINT NULL
        REFERENCES stok_islemleri(stok_islem_id) ON DELETE RESTRICT,
    ADD COLUMN stok_kalemi_id BIGINT NULL
        REFERENCES stok_kalemleri(stok_kalemi_id) ON DELETE RESTRICT,
    ADD COLUMN parti_id BIGINT NULL
        REFERENCES stok_partileri(parti_id) ON DELETE RESTRICT,
    ADD COLUMN stok_durumu_kodu VARCHAR(30) NOT NULL DEFAULT 'SERBEST'
        REFERENCES stok_durumlari(stok_durumu_kodu) ON DELETE RESTRICT;

CREATE INDEX idx_stok_hareketleri_stok_islem ON stok_hareketleri(stok_islem_id);
CREATE INDEX idx_stok_hareketleri_sku_lokasyon
    ON stok_hareketleri(stok_kalemi_id, kaynak_lokasyon_id, hedef_lokasyon_id, stok_durumu_kodu);

-- Geçmiş hareketin işlem nedeni bilinmediği için uydurulmaz; MIRAS_HAREKET olur.
INSERT INTO stok_islemleri (
    istemci_islem_kimligi, islem_nedeni, aciklama, yapan_kullanici,
    miras_hareket_id, islem_tarihi, created_at
)
SELECT
    COALESCE(
        sh.istemci_islem_kimligi,
        (
            substr(md5('miras-hareket:' || sh.hareket_id::TEXT), 1, 8) || '-' ||
            substr(md5('miras-hareket:' || sh.hareket_id::TEXT), 9, 4) || '-' ||
            substr(md5('miras-hareket:' || sh.hareket_id::TEXT), 13, 4) || '-' ||
            substr(md5('miras-hareket:' || sh.hareket_id::TEXT), 17, 4) || '-' ||
            substr(md5('miras-hareket:' || sh.hareket_id::TEXT), 21, 12)
        )::UUID
    ),
    'MIRAS_HAREKET', sh.aciklama, sh.yapan_kullanici,
    sh.hareket_id, sh.islem_tarihi, sh.created_at
FROM stok_hareketleri sh;

UPDATE stok_hareketleri sh
SET
    stok_islem_id = si.stok_islem_id,
    stok_kalemi_id = sk.stok_kalemi_id
FROM stok_islemleri si, stok_kalemleri sk
WHERE si.miras_hareket_id = sh.hareket_id
  AND sk.sku_kodu = sh.stok_kodu
  AND sk.nitelik_durumu = 'BELIRSIZ';

-- Bütün tarihçe bağlandıktan sonra yeni defter satırlarının başlıksız veya SKU'suz
-- yazılmasına şema düzeyinde de izin verme.
ALTER TABLE stok_hareketleri
    ALTER COLUMN stok_islem_id SET NOT NULL,
    ALTER COLUMN stok_kalemi_id SET NOT NULL;

-- Yeni yetkili okuma yüzeyi: SKU × lokasyon × durum × parti bakiyesi.
CREATE VIEW v_stok_bakiye AS
SELECT
    md5(
        hareket.stok_kalemi_id::TEXT || ':' || hareket.lokasyon_id::TEXT || ':' ||
        hareket.stok_durumu_kodu || ':' || COALESCE(hareket.parti_id::TEXT, '-')
    ) AS bakiye_anahtari,
    hareket.stok_kalemi_id,
    sk.sku_kodu,
    sk.urun_kodu,
    sk.nitelik_durumu,
    sk.kaplama_id,
    kp.kaplama_adi,
    sk.boya_renk_id,
    br.renk_adi AS boya_renk_adi,
    sk.mine_renk_id,
    mr.renk_adi AS mine_renk_adi,
    sk.montaj_durumu,
    sk.satilabilir_mi,
    sk.kritik_stok_esigi,
    hareket.lokasyon_id,
    ld.lokasyon_adi,
    ld.tam_ad AS lokasyon_tam_adi,
    ld.tip AS lokasyon_tipi,
    lok.is_ortagi_id,
    hareket.stok_durumu_kodu,
    sd.stok_durumu_adi,
    sd.kullanilabilir_mi,
    hareket.parti_id,
    sp.parti_no,
    SUM(hareket.net_miktar)::INTEGER AS mevcut_miktar
FROM (
    SELECT
        COALESCE(sh.stok_kalemi_id, miras.stok_kalemi_id) AS stok_kalemi_id,
        sh.hedef_lokasyon_id AS lokasyon_id,
        sh.stok_durumu_kodu,
        sh.parti_id,
        sh.miktar AS net_miktar
    FROM stok_hareketleri sh
    LEFT JOIN stok_kalemleri miras
      ON miras.sku_kodu = sh.stok_kodu AND miras.nitelik_durumu = 'BELIRSIZ'
    WHERE sh.hedef_lokasyon_id IS NOT NULL
    UNION ALL
    SELECT
        COALESCE(sh.stok_kalemi_id, miras.stok_kalemi_id) AS stok_kalemi_id,
        sh.kaynak_lokasyon_id AS lokasyon_id,
        sh.stok_durumu_kodu,
        sh.parti_id,
        -sh.miktar AS net_miktar
    FROM stok_hareketleri sh
    LEFT JOIN stok_kalemleri miras
      ON miras.sku_kodu = sh.stok_kodu AND miras.nitelik_durumu = 'BELIRSIZ'
    WHERE sh.kaynak_lokasyon_id IS NOT NULL
) hareket
JOIN stok_kalemleri sk ON sk.stok_kalemi_id = hareket.stok_kalemi_id
JOIN v_lokasyonlar_detay ld ON ld.lokasyon_id = hareket.lokasyon_id
JOIN lokasyonlar lok ON lok.lokasyon_id = hareket.lokasyon_id
JOIN stok_durumlari sd ON sd.stok_durumu_kodu = hareket.stok_durumu_kodu
LEFT JOIN kaplamalar kp ON kp.kaplama_id = sk.kaplama_id
LEFT JOIN renkler br ON br.renk_id = sk.boya_renk_id
LEFT JOIN renkler mr ON mr.renk_id = sk.mine_renk_id
LEFT JOIN stok_partileri sp ON sp.parti_id = hareket.parti_id
GROUP BY
    hareket.stok_kalemi_id, sk.sku_kodu, sk.urun_kodu, sk.nitelik_durumu,
    sk.kaplama_id, kp.kaplama_adi, sk.boya_renk_id, br.renk_adi,
    sk.mine_renk_id, mr.renk_adi, sk.montaj_durumu, sk.satilabilir_mi,
    sk.kritik_stok_esigi, hareket.lokasyon_id, ld.lokasyon_adi, ld.tam_ad,
    ld.tip, lok.is_ortagi_id, hareket.stok_durumu_kodu, sd.stok_durumu_adi,
    sd.kullanilabilir_mi, hareket.parti_id, sp.parti_no;

CREATE VIEW v_stok_urun_ozet AS
SELECT
    urun_kodu,
    COALESCE(SUM(mevcut_miktar), 0)::INTEGER AS sahip_olunan_toplam,
    COALESCE(SUM(mevcut_miktar) FILTER (
        WHERE lokasyon_tipi IN ('DAHILI', 'NUMUNE')
    ), 0)::INTEGER AS tesis_ici_toplam,
    COALESCE(SUM(mevcut_miktar) FILTER (
        WHERE lokasyon_tipi = 'DAHILI'
          AND stok_durumu_kodu = 'SERBEST'
          AND satilabilir_mi
    ), 0)::INTEGER AS satisa_hazir_toplam,
    COALESCE(SUM(mevcut_miktar) FILTER (WHERE lokasyon_tipi = 'FASON'), 0)::INTEGER
        AS fasonda_toplam,
    COALESCE(SUM(mevcut_miktar) FILTER (WHERE lokasyon_tipi = 'NUMUNE'), 0)::INTEGER
        AS numunede_toplam,
    COALESCE(SUM(mevcut_miktar) FILTER (
        WHERE stok_durumu_kodu = 'KALITE_BEKLIYOR'
    ), 0)::INTEGER AS kalite_bekleyen_toplam,
    COALESCE(SUM(mevcut_miktar) FILTER (
        WHERE stok_durumu_kodu = 'BLOKE'
    ), 0)::INTEGER AS bloke_toplam
FROM v_stok_bakiye
GROUP BY urun_kodu;

CREATE VIEW v_fason_is_emri_ozet AS
SELECT
    fie.fason_is_emri_id,
    fie.emir_no,
    fie.is_ortagi_id,
    io.unvan AS fasoncu_adi,
    fie.fason_lokasyon_id,
    ld.tam_ad AS fason_lokasyonu,
    fie.kaynak_stok_kalemi_id,
    kaynak.sku_kodu AS kaynak_sku_kodu,
    fie.hedef_stok_kalemi_id,
    hedef.sku_kodu AS hedef_sku_kodu,
    fie.islem_turu,
    fie.kaplama_cesidi,
    fie.planlanan_miktar,
    fie.beklenen_donus_tarihi,
    fie.durum,
    fie.aciklama,
    COALESCE(gerceklesen.gonderilen, 0)::INTEGER AS gonderilen_miktar,
    COALESCE(gerceklesen.donen, 0)::INTEGER AS donen_miktar,
    COALESCE(gerceklesen.fire, 0)::INTEGER AS fire_miktari,
    GREATEST(
        COALESCE(gerceklesen.gonderilen, 0)
        - COALESCE(gerceklesen.donen, 0)
        - COALESCE(gerceklesen.fire, 0), 0
    )::INTEGER AS fason_bakiye,
    GREATEST(
        fie.planlanan_miktar
        - COALESCE(gerceklesen.donen, 0)
        - COALESCE(gerceklesen.fire, 0), 0
    )::INTEGER AS acik_miktar
FROM fason_is_emirleri fie
JOIN is_ortaklari io ON io.is_ortagi_id = fie.is_ortagi_id
JOIN v_lokasyonlar_detay ld ON ld.lokasyon_id = fie.fason_lokasyon_id
JOIN stok_kalemleri kaynak ON kaynak.stok_kalemi_id = fie.kaynak_stok_kalemi_id
JOIN stok_kalemleri hedef ON hedef.stok_kalemi_id = fie.hedef_stok_kalemi_id
LEFT JOIN LATERAL (
    SELECT
        SUM(sh.miktar) FILTER (
            WHERE si.islem_nedeni = 'FASON_SEVK'
              AND sh.hedef_lokasyon_id = fie.fason_lokasyon_id
        ) AS gonderilen,
        SUM(sh.miktar) FILTER (
            WHERE si.islem_nedeni = 'FASON_DONUS'
              AND sh.hedef_lokasyon_id IS NOT NULL
              AND sh.hedef_lokasyon_id <> fie.fason_lokasyon_id
        ) AS donen,
        SUM(sh.miktar) FILTER (WHERE si.islem_nedeni = 'FIRE') AS fire
    FROM stok_islemleri si
    JOIN stok_hareketleri sh ON sh.stok_islem_id = si.stok_islem_id
    WHERE si.fason_is_emri_id = fie.fason_is_emri_id
) gerceklesen ON TRUE;

-- Yeni SKU kodu yalnız kullanılan kombinasyon için, ürün koduna sıralı soneklenir.
CREATE OR REPLACE FUNCTION stok_kalemi_kaydet(
    p_urun_kodu VARCHAR,
    p_kaplama_id INTEGER,
    p_boya_renk VARCHAR,
    p_mine_renk VARCHAR,
    p_montaj_durumu VARCHAR,
    p_yapan_kullanici VARCHAR
) RETURNS TABLE (
    stok_kalemi_id BIGINT, sku_kodu VARCHAR, atlandi BOOLEAN, mesaj TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_boya_id INTEGER;
    v_mine_id INTEGER;
    v_sira INTEGER;
    v_sku VARCHAR;
    v_id BIGINT;
BEGIN
    IF p_yapan_kullanici IS NULL OR btrim(p_yapan_kullanici) = '' THEN
        RAISE EXCEPTION 'İşlemi yapan kullanıcı zorunludur.';
    END IF;
    IF p_montaj_durumu NOT IN ('HAM', 'YARI_MONTE', 'MONTE') THEN
        RAISE EXCEPTION 'Montaj durumu HAM, YARI_MONTE veya MONTE olmalıdır.';
    END IF;

    PERFORM 1 FROM urunler WHERE stok_kodu = p_urun_kodu FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Ürün bulunamadı: "%".', p_urun_kodu;
    END IF;
    IF p_kaplama_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM kaplamalar WHERE kaplama_id = p_kaplama_id AND aktif_mi) THEN
        RAISE EXCEPTION 'Aktif kaplama bulunamadı (id: %).', p_kaplama_id;
    END IF;

    IF NULLIF(btrim(p_boya_renk), '') IS NOT NULL THEN
        SELECT renk_id INTO v_boya_id
        FROM renkler WHERE lower(btrim(renk_adi)) = lower(btrim(p_boya_renk));
        IF NOT FOUND THEN
            INSERT INTO renkler (renk_adi) VALUES (btrim(p_boya_renk))
            ON CONFLICT DO NOTHING RETURNING renk_id INTO v_boya_id;
            IF v_boya_id IS NULL THEN
                SELECT renk_id INTO v_boya_id
                FROM renkler WHERE lower(btrim(renk_adi)) = lower(btrim(p_boya_renk));
            END IF;
        END IF;
    END IF;
    IF NULLIF(btrim(p_mine_renk), '') IS NOT NULL THEN
        SELECT renk_id INTO v_mine_id
        FROM renkler WHERE lower(btrim(renk_adi)) = lower(btrim(p_mine_renk));
        IF NOT FOUND THEN
            INSERT INTO renkler (renk_adi) VALUES (btrim(p_mine_renk))
            ON CONFLICT DO NOTHING RETURNING renk_id INTO v_mine_id;
            IF v_mine_id IS NULL THEN
                SELECT renk_id INTO v_mine_id
                FROM renkler WHERE lower(btrim(renk_adi)) = lower(btrim(p_mine_renk));
            END IF;
        END IF;
    END IF;

    SELECT sk.stok_kalemi_id, sk.sku_kodu INTO v_id, v_sku
    FROM stok_kalemleri sk
    WHERE sk.urun_kodu = p_urun_kodu
      AND sk.nitelik_durumu = 'TANIMLI'
      AND sk.kaplama_id IS NOT DISTINCT FROM p_kaplama_id
      AND sk.boya_renk_id IS NOT DISTINCT FROM v_boya_id
      AND sk.mine_renk_id IS NOT DISTINCT FROM v_mine_id
      AND sk.montaj_durumu = p_montaj_durumu;

    IF FOUND THEN
        RETURN QUERY SELECT v_id, v_sku, TRUE, 'Bu stok varyantı zaten kayıtlı.'::TEXT;
        RETURN;
    END IF;

    SELECT COALESCE(
        MAX(NULLIF(substring(sk.sku_kodu FROM '-V([0-9]+)$'), '')::INTEGER), 0
    ) + 1
    INTO v_sira
    FROM stok_kalemleri sk
    WHERE sk.urun_kodu = p_urun_kodu;

    v_sku := p_urun_kodu || '-V' || lpad(v_sira::TEXT, 2, '0');
    INSERT INTO stok_kalemleri (
        sku_kodu, urun_kodu, nitelik_durumu, kaplama_id,
        boya_renk_id, mine_renk_id, montaj_durumu, olusturan_kullanici
    ) VALUES (
        v_sku, p_urun_kodu, 'TANIMLI', p_kaplama_id,
        v_boya_id, v_mine_id, p_montaj_durumu, p_yapan_kullanici
    ) RETURNING stok_kalemleri.stok_kalemi_id INTO v_id;

    RETURN QUERY SELECT v_id, v_sku, FALSE, 'Stok varyantı oluşturuldu.'::TEXT;
END;
$$;

CREATE OR REPLACE FUNCTION fason_is_emri_kaydet(
    p_istemci_islem_kimligi UUID,
    p_is_ortagi_id BIGINT,
    p_fason_lokasyon_id INTEGER,
    p_kaynak_stok_kalemi_id BIGINT,
    p_hedef_stok_kalemi_id BIGINT,
    p_islem_turu VARCHAR,
    p_planlanan_miktar INTEGER,
    p_beklenen_donus_tarihi DATE,
    p_kaplama_cesidi VARCHAR,
    p_aciklama TEXT,
    p_yapan_kullanici VARCHAR
) RETURNS TABLE (
    fason_is_emri_id BIGINT, emir_no VARCHAR, atlandi BOOLEAN, mesaj TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id BIGINT;
    v_no VARCHAR;
BEGIN
    SELECT fie.fason_is_emri_id, fie.emir_no INTO v_id, v_no
    FROM fason_is_emirleri fie
    WHERE fie.istemci_islem_kimligi = p_istemci_islem_kimligi;
    IF FOUND THEN
        RETURN QUERY SELECT v_id, v_no, TRUE, 'Bu fason iş emri zaten oluşturulmuş.'::TEXT;
        RETURN;
    END IF;

    IF p_istemci_islem_kimligi IS NULL THEN
        RAISE EXCEPTION 'İstemci işlem kimliği zorunludur.';
    END IF;
    IF p_yapan_kullanici IS NULL OR btrim(p_yapan_kullanici) = '' THEN
        RAISE EXCEPTION 'İşlemi yapan kullanıcı zorunludur.';
    END IF;
    IF p_planlanan_miktar <= 0 THEN
        RAISE EXCEPTION 'Planlanan miktar sıfırdan büyük olmalıdır.';
    END IF;
    IF p_islem_turu NOT IN ('KAPLAMA', 'MINE', 'BOYA', 'MONTAJ', 'DIGER') THEN
        RAISE EXCEPTION 'Geçersiz fason işlem türü.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM stok_kalemleri
        WHERE stok_kalemi_id = p_kaynak_stok_kalemi_id AND aktif_mi AND stoklanabilir_mi
    ) OR NOT EXISTS (
        SELECT 1 FROM stok_kalemleri
        WHERE stok_kalemi_id = p_hedef_stok_kalemi_id AND aktif_mi AND stoklanabilir_mi
    ) THEN
        RAISE EXCEPTION 'Kaynak ve hedef SKU aktif ve stoklanabilir olmalıdır.';
    END IF;
    IF p_kaplama_cesidi IS NOT NULL AND p_kaplama_cesidi NOT IN ('ASKIDA', 'DOLAP') THEN
        RAISE EXCEPTION 'Kaplama çeşidi ASKIDA veya DOLAP olmalıdır.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM is_ortagi_rolleri
        WHERE is_ortagi_id = p_is_ortagi_id AND rol = 'FASONCU'
    ) THEN
        RAISE EXCEPTION 'Seçilen iş ortağı fasoncu değildir.';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM v_lokasyonlar_detay d
        JOIN lokasyonlar l ON l.lokasyon_id = d.lokasyon_id
        WHERE d.lokasyon_id = p_fason_lokasyon_id
          AND d.tip = 'FASON' AND d.aktif_mi AND d.yaprak_mi
          AND l.is_ortagi_id = p_is_ortagi_id
    ) THEN
        RAISE EXCEPTION 'Seçilen fason lokasyonu bu fasoncuya bağlı aktif bir yaprak lokasyon değildir.';
    END IF;

    INSERT INTO fason_is_emirleri (
        istemci_islem_kimligi, is_ortagi_id, fason_lokasyon_id,
        kaynak_stok_kalemi_id, hedef_stok_kalemi_id, islem_turu,
        kaplama_cesidi, planlanan_miktar, beklenen_donus_tarihi,
        aciklama, olusturan_kullanici
    ) VALUES (
        p_istemci_islem_kimligi, p_is_ortagi_id, p_fason_lokasyon_id,
        p_kaynak_stok_kalemi_id, p_hedef_stok_kalemi_id, p_islem_turu,
        p_kaplama_cesidi, p_planlanan_miktar, p_beklenen_donus_tarihi,
        NULLIF(btrim(p_aciklama), ''), p_yapan_kullanici
    )
    ON CONFLICT (istemci_islem_kimligi) DO NOTHING
    RETURNING fason_is_emirleri.fason_is_emri_id INTO v_id;

    IF v_id IS NULL THEN
        SELECT fie.fason_is_emri_id, fie.emir_no INTO v_id, v_no
        FROM fason_is_emirleri fie
        WHERE fie.istemci_islem_kimligi = p_istemci_islem_kimligi;
        RETURN QUERY SELECT v_id, v_no, TRUE,
            'Bu fason iş emri zaten oluşturulmuş.'::TEXT;
        RETURN;
    END IF;

    v_no := 'F-' || to_char(CURRENT_DATE, 'YYYY') || '-' || lpad(v_id::TEXT, 6, '0');
    UPDATE fason_is_emirleri fie SET emir_no = v_no WHERE fie.fason_is_emri_id = v_id;

    RETURN QUERY SELECT v_id, v_no, FALSE, 'Fason iş emri oluşturuldu.'::TEXT;
END;
$$;

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

-- Eski Django çağrıları için imza korunur; doğrudan INSERT etmek yerine yeni belge
-- kapısına tek satırlı bir stok işlemi olarak yönlendirilir.
-- 007 gövdesi rollback için farklı adla saklanır.
ALTER FUNCTION stok_hareketi_kaydet(
    UUID, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER, TEXT, VARCHAR,
    INTEGER, VARCHAR, BOOLEAN, VARCHAR, VARCHAR
) RENAME TO stok_hareketi_kaydet_v007;

CREATE FUNCTION stok_hareketi_kaydet(
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

-- Defter satırları düzeltilemez/silinemez; yanlış işlem yeni ters kayıtla düzeltilir.
CREATE OR REPLACE FUNCTION stok_hareketi_degistirilemez()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Kaydedilmiş stok hareketi değiştirilemez veya silinemez; ters/düzeltme işlemi oluşturun.';
END;
$$;

CREATE TRIGGER trg_stok_hareketi_degistirilemez
BEFORE UPDATE OR DELETE ON stok_hareketleri
FOR EACH ROW EXECUTE FUNCTION stok_hareketi_degistirilemez();

COMMIT;
