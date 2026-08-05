-- =========================================================
-- Migration 009: standart renk ve hammadde başlangıç verisi
--
-- Sorun: `renkler` ve `hammaddeler` referans tabloları boş. Renk tablosu
-- migration 008 ile geldi ve yalnız `stok_kalemi_kaydet()` serbest metinden bir
-- renk türettiğinde dolan bir tablo; hammadde tablosu baz şemadan beri var ama
-- 2.973 ürünün hiçbirinde dolu değil (bkz. docs/INFO.md). Sonuç olarak ürün
-- formundaki "Hammadde" seçimi ile stok listesindeki "Boya rengi" / "Mine rengi"
-- gelişmiş filtreleri boş açılıyor — personelin yazım biçimini kendi uydurması
-- gerekiyor ve aynı renk üç farklı yazımla üç ayrı satır olabiliyor.
--
-- Bu migration YALNIZCA veri ekler: tablo, kolon, kısıt veya view değiştirmez.
-- İki INSERT de `ON CONFLICT DO NOTHING` ile yazıldığı için elle girilmiş
-- satırların üzerine yazmaz ve migration tekrar çalıştırılabilir.
--
-- Renk tekilliği `uq_renkler_adi_ci` ile büyük/küçük harf DUYARSIZ (migration
-- 008): tabloda `siyah` varsa buradaki `Siyah` yeni satır açmaz, mevcut satır
-- korunur. Hammaddede kısıt düz UNIQUE'tir, yani orada eşleşme harf duyarlıdır.
--
-- Yazım biçimi bilinçli olarak baş harfi büyük: iki liste de doğrudan açılır
-- listede gösteriliyor. `kaplamalar` (migration 007) küçük harfle yüklenmişti;
-- o tablo dokunulmadan bırakıldı — yerinde bir düzeltme değil, görünen 11 rengin
-- adını değiştirmek olurdu ve o adlar defterdeki kovalarla eşleşiyor.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1) Standart renkler (boya ve mine için ortak liste)
-- ---------------------------------------------------------
INSERT INTO renkler (renk_adi) VALUES
    ('Siyah'),
    ('Beyaz'),
    ('Kırmızı'),
    ('Lacivert'),
    ('Sarı'),
    ('Antik Sarı'),
    ('Füme'),
    ('Gri'),
    ('Kahverengi'),
    ('Yeşil'),
    ('Mavi'),
    ('Pembe'),
    ('Bordo')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------
-- 2) Standart hammadde çeşitleri
-- ---------------------------------------------------------
INSERT INTO hammaddeler (hammadde_adi) VALUES
    ('Zamak'),
    ('Pirinç'),
    ('Demir'),
    ('Plastik'),
    ('Alüminyum'),
    ('Paslanmaz Çelik'),
    ('Sac')
ON CONFLICT DO NOTHING;

COMMIT;
