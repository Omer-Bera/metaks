-- =========================================================
-- Migration 006: defterdeki test hareketlerini temizle
--
-- stok_hareketleri'ndeki 30 satırın TAMAMI test kaydı; defterde korunacak
-- tek bir gerçek iş hareketi yok. Devam eden depo sayımının verisi
-- veritabanında değil, Excel'de tutuluyor (bkz. depo-web-arayuz/CLAUDE.md).
--
--   9-37  (2026-07-29) Appsmith StokIslemi denemeleri — her GİRİŞ'in peşinde
--         bir ÇIKIŞ, hepsi yuvarlak rakamlar, hepsi net 0'a iniyor.
--   45-53 (2026-07-30) Django stok işlemi modülünün uçtan uca doğrulaması —
--         açıklamalarından ayırt ediliyor ("mukerrer gonderim testi",
--         "Django arayüzü ilk gerçek kayıt denemesi").
--
-- NEDEN ŞİMDİ: bu kayıtlar gerçekte var olmayan dört lokasyonu (Ana Depo,
-- Sevkiyat Alanı, Fason Atölye 1, Depo 1) yerinde tutuyor. İki FK de
-- ON DELETE RESTRICT olduğu için defter temizlenmeden o lokasyonlar
-- silinemiyor — Django'nun yeni lokasyon silme ekranı da onlarda haklı
-- olarak "Sil" göstermiyor. Kullanıcı kararı (2026-07-31): hepsi silinsin,
-- defter sıfırdan başlasın.
--
-- Lokasyonların kendisi BU MIGRATION'IN KAPSAMINDA DEĞİL: onlar Django'nun
-- /yonetim/lokasyonlar/ ekranından silinecek (özelliğin doğrulaması da o).
--
-- ETKİ: v_toplam_stok, v_fiziksel_stok ve v_lokasyon_stok_ozet hareketlerden
-- türediği için kendiliğinden boşalır. urunler'e dokunulmuyor.
--
-- GERİ ALMA: 006_test_hareketlerini_temizle_rollback.sql — 30 satırı
-- hareket_id'leriyle birlikte aynen geri yazar.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1) Emniyet: bu dosya 30 satırlık BİLİNEN bir defter için yazıldı.
--    Araya gerçek bir kayıt girdiyse sayı tutmaz ve migration durur —
--    aksi hâlde aşağıdaki id listesi sessizce eksik çalışır ve gerçek
--    veriyle dolu bir defterde yanlış bir izlenim bırakırdı.
-- ---------------------------------------------------------
DO $$
DECLARE
    bulunan INTEGER;
BEGIN
    SELECT count(*) INTO bulunan FROM stok_hareketleri;
    IF bulunan <> 30 THEN
        RAISE EXCEPTION
            'Defterde % satır var, beklenen 30. Araya yeni kayıt girmiş olabilir; '
            'migration durduruldu — önce satırları gözden geçirin.', bulunan;
    END IF;
END $$;

-- ---------------------------------------------------------
-- 2) Silme. id'ler açıkça yazılıyor (TRUNCATE ya da koşulsuz DELETE değil):
--    hangi satırın gittiği dosyadan okunabilsin, 1. adımdaki sayımla
--    birebir eşleşsin diye.
-- ---------------------------------------------------------
DELETE FROM stok_hareketleri
WHERE hareket_id IN (
     9, 10, 11, 12, 13, 14, 15, 16,          -- 29 Tem: GİRİŞ/ÇIKIŞ çiftleri
    23, 24, 25, 26, 29, 30, 31, 32, 33,      -- 29 Tem: DÜZELTME/TRANSFER denemeleri
    34, 35, 36, 37,                          -- 29 Tem: istemci kimliği testleri
    45, 46, 47, 48, 49,                      -- 30 Tem: Django GİRİŞ/TRANSFER/SAYIM
    50, 51, 52, 53                           -- 30 Tem: mükerrer gönderim testleri
);

-- ---------------------------------------------------------
-- 3) Sequence sıfırlanıyor: defter boşaldığına göre ilk gerçek hareket
--    1 numarayı almalı, 54'ü değil.
-- ---------------------------------------------------------
ALTER SEQUENCE stok_hareketleri_hareket_id_seq RESTART WITH 1;

COMMIT;
