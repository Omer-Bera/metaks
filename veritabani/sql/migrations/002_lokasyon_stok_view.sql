-- =========================================================
-- Migration 002: lokasyon bazlı stok miktarı view'ları
-- Appsmith Ürünler/Katalog sayfası için — bkz. docs/aktif-urun-veri-sozlesmesi.md
--
-- Bu dosya HENÜZ UYGULANMADI. Ortak veritabanına karşı çalıştırmadan
-- önce kullanıcı onayı gerekir.
--
-- Not: stok_hareketleri ve lokasyonlar şu an BOŞ (Faz 4 yükleyici script'i
-- henüz yazılmadı, bkz. CLAUDE.md). Bu view'lar bugün 0 satır döner —
-- bu beklenen bir durumdur, hata değildir. View'ların amacı, sayım
-- verisi yüklendiğinde Appsmith'in değişmeden çalışacağı sabit bir
-- sözleşme sağlamak.
--
-- Hiçbir mevcut tabloyu değiştirmez, sadece view ekler — geri almak
-- için DROP VIEW yeterli (aşağıdaki rollback dosyasına bakın).
-- =========================================================

BEGIN;

-- Lokasyon başına net miktar. Kabul edilen işaret kuralı (varsayım —
-- Faz 4 yükleyicisi yazılırken bu kuralla tutarlı veri üretilmeli):
--   hedef_lokasyon_id dolu  -> +miktar (GIRIS, TRANSFER'in varış ucu,
--                               SAYIM_DEVRI açılış bakiyesi)
--   kaynak_lokasyon_id dolu -> -miktar (CIKIS, TRANSFER'in çıkış ucu)
--   DUZELTME: azaltma gerekiyorsa kaynak_lokasyon_id dolu + pozitif
--             miktar girilir (CIKIS gibi davranır); artırma gerekiyorsa
--             hedef_lokasyon_id dolu + pozitif miktar (GIRIS gibi).
CREATE OR REPLACE VIEW v_lokasyon_stok_ozet AS
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

-- Lokasyonlar toplanmış, ürün başına tek bir "toplam mevcut miktar".
CREATE OR REPLACE VIEW v_toplam_stok AS
SELECT
    stok_kodu,
    SUM(mevcut_miktar) AS toplam_miktar
FROM v_lokasyon_stok_ozet
GROUP BY stok_kodu;

COMMIT;
