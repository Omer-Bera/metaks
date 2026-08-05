-- =========================================================
-- Migration 009 ROLLBACK: tohumlanan renk ve hammadde satırlarını geri al
--
-- Silme iki kez daraltılıyor, ikisi de bilinçli:
--
-- 1) TAM AD eşleşmesi (lower() DEĞİL). `uq_renkler_adi_ci` harf duyarsız olduğu
--    için ileri migration'ın `Siyah` satırı, tabloda zaten `siyah` varsa hiç
--    eklenmemiştir. lower() ile silseydik bizim eklemediğimiz o satırı
--    düşürürdük — rollback kendi yazmadığı veriyi silmemeli.
--
-- 2) REFERANS kontrolü. Renk FK'ları `ON DELETE RESTRICT`; bir renk SKU'ya
--    bağlandıysa düz DELETE bütün transaction'ı hataya düşürürdü. Hammaddede
--    kısıt RESTRICT değil ama sonuç aynı ölçüde istenmez. Kullanılmaya başlanmış
--    referans satırı yerinde bırakılıyor: tohumlamayı geri almak, o satıra
--    dayanan ürün/SKU verisini bozmayı gerektirmez.
--
-- Yani bu rollback "tabloyu boşaltmaz", yalnız hâlâ kullanılmayan tohum
-- satırlarını kaldırır. Tamamen boş bir tablo bekleniyorsa önce ilgili SKU/ürün
-- verisi temizlenmelidir.
-- =========================================================

BEGIN;

DELETE FROM renkler r
WHERE r.renk_adi IN (
        'Siyah', 'Beyaz', 'Kırmızı', 'Lacivert', 'Sarı', 'Antik Sarı', 'Füme',
        'Gri', 'Kahverengi', 'Yeşil', 'Mavi', 'Pembe', 'Bordo'
      )
  AND NOT EXISTS (
        SELECT 1 FROM stok_kalemleri sk
        WHERE sk.boya_renk_id = r.renk_id OR sk.mine_renk_id = r.renk_id
      );

DELETE FROM hammaddeler h
WHERE h.hammadde_adi IN (
        'Zamak', 'Pirinç', 'Demir', 'Plastik', 'Alüminyum',
        'Paslanmaz Çelik', 'Sac'
      )
  AND NOT EXISTS (
        SELECT 1 FROM urunler u WHERE u.hammadde_id = h.hammadde_id
      );

COMMIT;
