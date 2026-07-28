-- =========================================================
-- 1. REFERANS LOOKUP TABLOLARI
-- =========================================================

CREATE TABLE IF NOT EXISTS kategoriler (
    kategori_id SERIAL PRIMARY KEY,
    kategori_adi VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS hammaddeler (
    hammadde_id SERIAL PRIMARY KEY,
    hammadde_adi VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS kaplamalar (
    kaplama_id SERIAL PRIMARY KEY,
    kaplama_adi VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lokasyonlar (
    lokasyon_id SERIAL PRIMARY KEY,
    lokasyon_adi VARCHAR(100) NOT NULL,
    tip VARCHAR(50) NOT NULL -- 'Dahili' veya 'Fason'
);


-- =========================================================
-- 2. ANA VERİ TABLOSU (MASTER DATA - URUNLER)
-- =========================================================

CREATE TABLE IF NOT EXISTS urunler (
    stok_kodu VARCHAR(100) PRIMARY KEY,
    kategori_id INT REFERENCES kategoriler(kategori_id),
    hammadde_id INT NULL REFERENCES hammaddeler(hammadde_id),
    kaplama_id INT NULL REFERENCES kaplamalar(kaplama_id),
    
    -- Parent-Child (Ana Ürün - Yan Parça) İlişkisi
    parent_stok_kodu VARCHAR(100) NULL REFERENCES urunler(stok_kodu) ON DELETE SET NULL,
    urun_tipi VARCHAR(20) DEFAULT 'ANA_URUN' CHECK (urun_tipi IN ('ANA_URUN', 'ALT_PARCA')),
    
    -- Fiziksel ve Teknik Ölçüler
    olcu_mm NUMERIC(6,2) NULL,
    boy_ligne NUMERIC(5,2) NULL,
    boya_mine VARCHAR(100) NULL,
    gramaj_gr DECIMAL(10,2) NULL,
    montaj_durumu VARCHAR(50) NULL, -- 'Monte', 'Demonte', 'Sıvamalı'
    aciklama TEXT NULL,
    kritik_stok_esigi INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 3. HAREKET (LEDGER) TABLOSU
-- =========================================================

CREATE TABLE IF NOT EXISTS stok_hareketleri (
    hareket_id SERIAL PRIMARY KEY,
    stok_kodu VARCHAR(100) REFERENCES urunler(stok_kodu),
    gecici_kod VARCHAR(50) NULL, -- Excel'deki T-001 vb. kodlar için
    miktar INT NOT NULL,
    hedef_lokasyon_id INT REFERENCES lokasyonlar(lokasyon_id),
    islem_tipi VARCHAR(50) NOT NULL, -- 'Sayım Devri', 'Çıkış', 'Transfer'
    islem_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 4. PERFORMANS İNDEKSLERİ
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_urunler_kategori ON urunler(kategori_id);
CREATE INDEX IF NOT EXISTS idx_urunler_parent ON urunler(parent_stok_kodu);
CREATE INDEX IF NOT EXISTS idx_stok_hareketleri_kodu ON stok_hareketleri(stok_kodu);