-- =========================================================
-- METAKS DEPO / ERP VERİTABANI ŞEMASI
-- PostgreSQL 16
-- =========================================================


-- =========================================================
-- 1. REFERANS / LOOKUP TABLOLARI
-- =========================================================

CREATE TABLE IF NOT EXISTS kategoriler (
    kategori_id SERIAL PRIMARY KEY,

    kategori_adi VARCHAR(100) NOT NULL UNIQUE,

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS hammaddeler (
    hammadde_id SERIAL PRIMARY KEY,

    hammadde_adi VARCHAR(100) NOT NULL UNIQUE,

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS kaplamalar (
    kaplama_id SERIAL PRIMARY KEY,

    kaplama_adi VARCHAR(100) NOT NULL UNIQUE,

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS lokasyonlar (
    lokasyon_id SERIAL PRIMARY KEY,

    lokasyon_adi VARCHAR(100) NOT NULL,

    tip VARCHAR(50) NOT NULL
        CHECK (
            tip IN (
                'DAHILI',
                'FASON'
            )
        ),

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_lokasyonlar_ad_tip
        UNIQUE (lokasyon_adi, tip)
);


-- =========================================================
-- 2. ANA VERİ TABLOSU
-- MASTER DATA: URUNLER
-- =========================================================

CREATE TABLE IF NOT EXISTS urunler (
    stok_kodu VARCHAR(100) PRIMARY KEY,

    kategori_id INTEGER
        REFERENCES kategoriler(kategori_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    hammadde_id INTEGER NULL
        REFERENCES hammaddeler(hammadde_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    kaplama_id INTEGER NULL
        REFERENCES kaplamalar(kaplama_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,


    -- -----------------------------------------------------
    -- ANA ÜRÜN / ALT PARÇA / VARYANT İLİŞKİSİ
    -- -----------------------------------------------------

    parent_stok_kodu VARCHAR(100) NULL
        REFERENCES urunler(stok_kodu)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    urun_tipi VARCHAR(20) NOT NULL DEFAULT 'ANA_URUN'
        CHECK (
            urun_tipi IN (
                'ANA_URUN',
                'ALT_PARCA',
                'VARYANT'
            )
        ),


    -- -----------------------------------------------------
    -- VARYANT VE KALIP BİLGİLERİ
    -- -----------------------------------------------------

    varyant_adi VARCHAR(100) NULL,

    kalip_versiyonu VARCHAR(100) NULL,


    -- -----------------------------------------------------
    -- FİZİKSEL VE TEKNİK ÖZELLİKLER
    -- -----------------------------------------------------

    olcu_mm NUMERIC(6,2) NULL,

    boy_ligne NUMERIC(6,2) NULL,

    boya_mine VARCHAR(100) NULL,

    gramaj_gr NUMERIC(10,3) NULL,

    montaj_durumu VARCHAR(50) NULL,

    aciklama TEXT NULL,


    -- -----------------------------------------------------
    -- STOK VE DURUM BİLGİLERİ
    -- -----------------------------------------------------

    kritik_stok_esigi INTEGER NOT NULL DEFAULT 0
        CHECK (kritik_stok_esigi >= 0),

    stok_takip_edilsin_mi BOOLEAN NOT NULL DEFAULT TRUE,

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,


    -- -----------------------------------------------------
    -- ZAMAN BİLGİLERİ
    -- -----------------------------------------------------

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,


    -- Bir ürün kendi parent kaydı olamaz.
    CONSTRAINT chk_urun_parent_kendisi_olamaz
        CHECK (
            parent_stok_kodu IS NULL
            OR parent_stok_kodu <> stok_kodu
        ),


    -- Alt parça ve varyantların bir parent kaydı olmalıdır.
    CONSTRAINT chk_alt_parca_varyant_parent
        CHECK (
            urun_tipi = 'ANA_URUN'
            OR parent_stok_kodu IS NOT NULL
        )
);


-- =========================================================
-- 3. STOK HAREKETLERİ
-- LEDGER TABLOSU
-- =========================================================

CREATE TABLE IF NOT EXISTS stok_hareketleri (
    hareket_id BIGSERIAL PRIMARY KEY,

    stok_kodu VARCHAR(100) NOT NULL
        REFERENCES urunler(stok_kodu)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    gecici_kod VARCHAR(50) NULL,

    miktar INTEGER NOT NULL
        CHECK (miktar <> 0),

    kaynak_lokasyon_id INTEGER NULL
        REFERENCES lokasyonlar(lokasyon_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    hedef_lokasyon_id INTEGER NULL
        REFERENCES lokasyonlar(lokasyon_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    islem_tipi VARCHAR(50) NOT NULL
        CHECK (
            islem_tipi IN (
                'SAYIM_DEVRI',
                'GIRIS',
                'CIKIS',
                'TRANSFER',
                'DUZELTME'
            )
        ),

    aciklama TEXT NULL,

    islem_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,


    -- Transferde kaynak ve hedef aynı olamaz.
    CONSTRAINT chk_transfer_farkli_lokasyon
        CHECK (
            islem_tipi <> 'TRANSFER'
            OR (
                kaynak_lokasyon_id IS NOT NULL
                AND hedef_lokasyon_id IS NOT NULL
                AND kaynak_lokasyon_id <> hedef_lokasyon_id
            )
        )
);


-- =========================================================
-- 4. ÜRÜN GÖRSELLERİ VE MEDYA DOSYALARI
-- =========================================================

CREATE TABLE IF NOT EXISTS urun_gorselleri (
    gorsel_id BIGSERIAL PRIMARY KEY,

    stok_kodu VARCHAR(100) NOT NULL
        REFERENCES urunler(stok_kodu)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    dosya_adi TEXT NOT NULL,

    ana_gorsel_mi BOOLEAN NOT NULL DEFAULT FALSE,

    sira_no INTEGER NOT NULL DEFAULT 1
        CHECK (sira_no > 0),

    medya_tipi VARCHAR(30) NOT NULL DEFAULT 'URUN_GORSELI'
        CHECK (
            medya_tipi IN (
                'URUN_GORSELI',
                'TEKNIK_CIZIM',
                'KATALOG',
                'VIDEO',
                'DIGER'
            )
        ),

    aciklama TEXT NULL,

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    olusturma_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_urun_gorselleri_dosya
        UNIQUE (stok_kodu, dosya_adi)
);


-- =========================================================
-- 5. PERFORMANS İNDEKSLERİ
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_urunler_kategori
    ON urunler(kategori_id);


CREATE INDEX IF NOT EXISTS idx_urunler_hammadde
    ON urunler(hammadde_id);


CREATE INDEX IF NOT EXISTS idx_urunler_kaplama
    ON urunler(kaplama_id);


CREATE INDEX IF NOT EXISTS idx_urunler_parent
    ON urunler(parent_stok_kodu);


CREATE INDEX IF NOT EXISTS idx_urunler_urun_tipi
    ON urunler(urun_tipi);


CREATE INDEX IF NOT EXISTS idx_urunler_aktif
    ON urunler(aktif_mi);


CREATE INDEX IF NOT EXISTS idx_stok_hareketleri_kodu
    ON stok_hareketleri(stok_kodu);


CREATE INDEX IF NOT EXISTS idx_stok_hareketleri_tarih
    ON stok_hareketleri(islem_tarihi);


CREATE INDEX IF NOT EXISTS idx_stok_hareketleri_kaynak
    ON stok_hareketleri(kaynak_lokasyon_id);


CREATE INDEX IF NOT EXISTS idx_stok_hareketleri_hedef
    ON stok_hareketleri(hedef_lokasyon_id);


CREATE INDEX IF NOT EXISTS idx_urun_gorselleri_stok_kodu
    ON urun_gorselleri(stok_kodu);


CREATE INDEX IF NOT EXISTS idx_urun_gorselleri_ana_gorsel
    ON urun_gorselleri(stok_kodu, ana_gorsel_mi);


-- Bir ürünün yalnızca bir aktif ana görseli olabilir.
CREATE UNIQUE INDEX IF NOT EXISTS uq_urun_tek_ana_gorsel
    ON urun_gorselleri(stok_kodu)
    WHERE ana_gorsel_mi = TRUE
      AND aktif_mi = TRUE;