-- =========================================================
-- Migration 005: urun_kaydet() — ürün ekleme/güncellemenin tek kapısı
--
-- Django'nun ürün ekleme/düzenleme ekranı ve Appsmith aynı iş kuralını
-- paylaşsın diye, stok_hareketi_kaydet() ile AYNI desende yazıldı:
-- kural veritabanında tek yerde durur, Türkçe RAISE EXCEPTION mesajları
-- doğrudan son kullanıcıya gösterilebilir, arayüz katmanı yalnızca
-- parametre geçirip dönen mesajı taşır.
--
-- Bu dosya HENÜZ UYGULANMADI. Ortak veritabanına karşı çalıştırmadan
-- önce kullanıcı onayı gerekir.
--
-- NEDEN ZORUNLU (ölçüldü, 2026-07-30):
--   urunler'e sade bir INSERT ürünü "görünmez" bırakmıyor, DOĞRUDAN
--   PATLIYOR:
--     INSERT INTO urunler (stok_kodu) VALUES ('X');
--     ERROR: new row for relation "urunler" violates check constraint
--            "chk_urunler_katalog_durumu_aktif_mi_tutarli"
--   Çünkü aktif_mi DEFAULT TRUE ile katalog_durumu DEFAULT 'PASIF'
--   birbiriyle çelişiyor ve CHECK ikisinin birlikte hareket etmesini
--   şart koşuyor. Yani ORM'den gelen her kısmi INSERT hata verir.
--   Bu migration varsayılanı da düzeltiyor (aşağıda 2. madde).
--
-- KAPSAM DIŞI: stok_kodu değiştirme. stok_kodu birincil anahtar ve dört
-- ayrı FK'nın hedefi; yeniden adlandırma ayrı bir iştir, bu fonksiyon
-- GUNCELLE modunda stok_kodu'nu kimlik olarak kullanır, değiştirmez.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1) Denetim izi. Mevcut 2973 satır NULL kalır — o ürünleri kimin
--    oluşturduğunu gerçekten bilmiyoruz (toplu pipeline yüklemesiyle
--    geldiler), uydurmak yanlış olurdu. NULL "bilinmiyor" demek.
--    updated_at kolonu zaten vardı ama hiçbir şey bakımını yapmıyordu
--    (2973/2973 satırda created_at'e eşit); bundan sonra urun_kaydet()
--    GUNCELLE modunda dokunuyor.
-- ---------------------------------------------------------
ALTER TABLE urunler
    ADD COLUMN olusturan_kullanici   VARCHAR(255) NULL,
    ADD COLUMN guncelleyen_kullanici VARCHAR(255) NULL;

-- ---------------------------------------------------------
-- 2) Çelişen varsayılanı düzelt: katalog_durumu varsayılanı 'PASIF'
--    olduğu için aktif_mi varsayılanı da FALSE olmalı; bugünkü TRUE
--    değeri CHECK ile çelişiyor ve varsayılanlara güvenen her INSERT'i
--    patlatıyor. Değişiklik risksiz: bugün o varsayılan kombinasyonuyla
--    satır eklenmesi zaten imkânsız. scripts/database/yukle.py aktif_mi'yi
--    açıkça yazdığı için etkilenmez (doğrulandı).
-- ---------------------------------------------------------
ALTER TABLE urunler ALTER COLUMN aktif_mi SET DEFAULT FALSE;

-- ---------------------------------------------------------
-- 3) Yardımcı: bir ürünün bir sonraki görsel sıra numarası.
--    Django dosyayı DB'ye yazmadan ÖNCE diske yazacağı için (bkz.
--    aşağıdaki "DOSYA SIRASI" notu) dosya adını kurabilmek adına bu
--    numaraya önceden ihtiyaç duyuyor.
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION urun_sonraki_gorsel_sirasi(p_stok_kodu VARCHAR)
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(MAX(sira_no), 0) + 1
    FROM urun_gorselleri
    WHERE stok_kodu = p_stok_kodu;
$$;

-- ---------------------------------------------------------
-- 4) urun_kaydet() — ekleme ve güncellemenin tek kapısı.
--
--    TEK FONKSİYON + ZORUNLU p_mod tercihi: sessiz upsert bilerek
--    reddedildi. Ekleme ekranında yanlış yazılan bir stok kodu, sessiz
--    upsert'te mevcut bir ürünü fark edilmeden EZERDİ. p_mod'un zorunlu
--    olması niyeti açık kılıyor; doğrulama bloğu ise tek yerde kalıyor.
--
--    GUNCELLE modu TAM KAYIT (full replace) semantiği taşır: form bütün
--    alanları göndermeli, gönderilmeyen alan NULL'a çekilir. COALESCE'lı
--    "kısmi güncelleme" bilerek seçilmedi — o tasarımda dolu bir alanı
--    bir daha asla boşaltamazsınız.
--
--    AKTİF olma kuralı (kullanıcı kararı, 2026-07-30): TEK şart ana
--    görsel. Kategori/ölçü zorunlu tutulmuyor; mevcut 1780 AKTİF ürünün
--    31'i kategorisiz, 65'i ölçüsüz olduğu için daha sıkı bir kural eski
--    veriyle çelişirdi. Ana görselsiz ürün PASİF kalır — bu bir hata
--    değil, taslak üründür.
--
--    Mükerrer gönderim koruması için ayrı bir UUID'ye gerek yok:
--    stok_kodu birincil anahtar olduğundan doğal idempotency anahtarıdır
--    (EKLE modunda ikinci gönderim anlaşılır bir hata verir).
--
--    DOSYA SIRASI (Django tarafı): önce dosyayı diske yaz, sonra bu
--    fonksiyonu çağır, fonksiyon hata verirse yazdığın dosyayı sil. Ters
--    sırada bir çökme, DB'de var olmayan dosyayı gösteren kırık bir ürün
--    bırakır; bu sırada ise en kötü ihtimalle sahipsiz bir dosya kalır ve
--    onu bulan araç zaten mevcut (scripts/images/gorsel_eslesme_raporu.py).
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION urun_kaydet(
    p_mod                   VARCHAR,
    p_stok_kodu             VARCHAR,
    p_yapan_kullanici       VARCHAR,
    p_kategori_id           INTEGER DEFAULT NULL,
    p_hammadde_id           INTEGER DEFAULT NULL,
    p_kaplama_id            INTEGER DEFAULT NULL,
    p_urun_tipi             VARCHAR DEFAULT 'ANA_URUN',
    p_parent_stok_kodu      VARCHAR DEFAULT NULL,
    p_varyant_adi           VARCHAR DEFAULT NULL,
    p_kalip_versiyonu       VARCHAR DEFAULT NULL,
    p_olcu_mm               NUMERIC DEFAULT NULL,
    p_boy_ligne             NUMERIC DEFAULT NULL,
    p_boya_mine             VARCHAR DEFAULT NULL,
    p_gramaj_gr             NUMERIC DEFAULT NULL,
    p_montaj_durumu         VARCHAR DEFAULT NULL,
    p_aciklama              TEXT    DEFAULT NULL,
    p_kritik_stok_esigi     INTEGER DEFAULT 0,
    p_stok_takip_edilsin_mi BOOLEAN DEFAULT TRUE,
    p_ana_gorsel_dosya_adi  VARCHAR DEFAULT NULL
) RETURNS TABLE (
    stok_kodu      VARCHAR,
    katalog_durumu VARCHAR,
    gorsel_id      BIGINT,
    mesaj          TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_var_mi       BOOLEAN;
    v_gorsel_id    BIGINT := NULL;
    v_durum        VARCHAR;
    v_aktif        BOOLEAN;
    v_sira         INTEGER;
    v_mesaj        TEXT;
BEGIN
    -- ---- Temel parametre doğrulamaları -------------------------------
    IF p_mod IS NULL OR p_mod NOT IN ('EKLE', 'GUNCELLE') THEN
        RAISE EXCEPTION 'Geçersiz mod: "%". Beklenen değerler: EKLE, GUNCELLE.', p_mod;
    END IF;

    IF p_stok_kodu IS NULL OR btrim(p_stok_kodu) = '' THEN
        RAISE EXCEPTION 'Stok kodu zorunludur.';
    END IF;

    IF p_yapan_kullanici IS NULL OR btrim(p_yapan_kullanici) = '' THEN
        RAISE EXCEPTION 'İşlemi yapan kullanıcı bilgisi zorunludur.';
    END IF;

    IF p_kritik_stok_esigi IS NULL OR p_kritik_stok_esigi < 0 THEN
        RAISE EXCEPTION 'Kritik stok eşiği negatif olamaz.';
    END IF;

    -- ---- Mod ile mevcut durumun tutarlılığı --------------------------
    SELECT EXISTS (SELECT 1 FROM urunler u WHERE u.stok_kodu = p_stok_kodu) INTO v_var_mi;

    IF p_mod = 'EKLE' AND v_var_mi THEN
        RAISE EXCEPTION '"%" stok kodu zaten kayıtlı. Mevcut ürünü değiştirmek istiyorsanız düzenleme ekranını kullanın.', p_stok_kodu;
    ELSIF p_mod = 'GUNCELLE' AND NOT v_var_mi THEN
        RAISE EXCEPTION '"%" stok kodlu ürün bulunamadı.', p_stok_kodu;
    END IF;

    -- ---- Referans doğrulamaları (FK'ler zaten korur ama mesajlar
    --      anlaşılır olsun diye önden kontrol ediliyor) ----------------
    IF p_kategori_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM kategoriler k WHERE k.kategori_id = p_kategori_id) THEN
        RAISE EXCEPTION 'Kategori bulunamadı (id: %).', p_kategori_id;
    END IF;

    IF p_hammadde_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM hammaddeler h WHERE h.hammadde_id = p_hammadde_id) THEN
        RAISE EXCEPTION 'Hammadde bulunamadı (id: %).', p_hammadde_id;
    END IF;

    IF p_kaplama_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM kaplamalar kp WHERE kp.kaplama_id = p_kaplama_id) THEN
        RAISE EXCEPTION 'Kaplama bulunamadı (id: %).', p_kaplama_id;
    END IF;

    IF p_urun_tipi IS NULL OR p_urun_tipi NOT IN ('ANA_URUN', 'ALT_PARCA', 'VARYANT') THEN
        RAISE EXCEPTION 'Geçersiz ürün tipi: "%". Beklenen değerler: ANA_URUN, ALT_PARCA, VARYANT.', p_urun_tipi;
    END IF;

    -- ALT_PARCA/VARYANT mutlaka bir üst ürüne bağlanmalı
    -- (tablonun chk_alt_parca_varyant_parent kısıtıyla aynı kural).
    IF p_urun_tipi <> 'ANA_URUN' AND p_parent_stok_kodu IS NULL THEN
        RAISE EXCEPTION '% tipindeki ürün bir ana ürüne bağlanmalıdır (üst stok kodu boş bırakılamaz).', p_urun_tipi;
    END IF;

    IF p_parent_stok_kodu IS NOT NULL THEN
        IF p_parent_stok_kodu = p_stok_kodu THEN
            RAISE EXCEPTION 'Bir ürün kendisinin üst ürünü olamaz.';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM urunler u WHERE u.stok_kodu = p_parent_stok_kodu) THEN
            RAISE EXCEPTION 'Üst ürün bulunamadı: "%".', p_parent_stok_kodu;
        END IF;
    END IF;

    -- ---- Görsel dosya adı doğrulaması --------------------------------
    -- Sadece dosya ADI tutulur (yol değil): nginx bunu doğrudan
    -- http://<host>:8083/urun-gorselleri/<dosya_adi> altında yayınlıyor.
    IF p_ana_gorsel_dosya_adi IS NOT NULL THEN
        IF btrim(p_ana_gorsel_dosya_adi) = '' THEN
            RAISE EXCEPTION 'Görsel dosya adı boş olamaz.';
        END IF;
        IF p_ana_gorsel_dosya_adi LIKE '%/%' OR p_ana_gorsel_dosya_adi LIKE '%\%' THEN
            RAISE EXCEPTION 'Görsel için yol değil sadece dosya adı verilmelidir: "%".', p_ana_gorsel_dosya_adi;
        END IF;
    END IF;

    -- ---- Ürün satırı --------------------------------------------------
    -- Ana görsel verildiyse ürün AKTİF olur, verilmediyse EKLE'de PASİF
    -- taslak olarak doğar. GUNCELLE'de görsel verilmediyse mevcut durum
    -- korunur (var olan görseli olan bir ürün pasife düşmez).
    IF p_ana_gorsel_dosya_adi IS NOT NULL THEN
        v_durum := 'AKTIF';
        v_aktif := TRUE;
    ELSIF p_mod = 'EKLE' THEN
        v_durum := 'PASIF';
        v_aktif := FALSE;
    ELSE
        SELECT u.katalog_durumu, u.aktif_mi INTO v_durum, v_aktif
        FROM urunler u WHERE u.stok_kodu = p_stok_kodu;
    END IF;

    IF p_mod = 'EKLE' THEN
        INSERT INTO urunler (
            stok_kodu, kategori_id, hammadde_id, kaplama_id,
            parent_stok_kodu, urun_tipi, varyant_adi, kalip_versiyonu,
            olcu_mm, boy_ligne, boya_mine, gramaj_gr, montaj_durumu,
            aciklama, kritik_stok_esigi, stok_takip_edilsin_mi,
            aktif_mi, katalog_durumu, olusturan_kullanici, guncelleyen_kullanici
        ) VALUES (
            p_stok_kodu, p_kategori_id, p_hammadde_id, p_kaplama_id,
            p_parent_stok_kodu, p_urun_tipi, p_varyant_adi, p_kalip_versiyonu,
            p_olcu_mm, p_boy_ligne, p_boya_mine, p_gramaj_gr, p_montaj_durumu,
            p_aciklama, p_kritik_stok_esigi, p_stok_takip_edilsin_mi,
            v_aktif, v_durum, p_yapan_kullanici, NULL
        );
    ELSE
        UPDATE urunler u SET
            kategori_id           = p_kategori_id,
            hammadde_id           = p_hammadde_id,
            kaplama_id            = p_kaplama_id,
            parent_stok_kodu      = p_parent_stok_kodu,
            urun_tipi             = p_urun_tipi,
            varyant_adi           = p_varyant_adi,
            kalip_versiyonu       = p_kalip_versiyonu,
            olcu_mm               = p_olcu_mm,
            boy_ligne             = p_boy_ligne,
            boya_mine             = p_boya_mine,
            gramaj_gr             = p_gramaj_gr,
            montaj_durumu         = p_montaj_durumu,
            aciklama              = p_aciklama,
            kritik_stok_esigi     = p_kritik_stok_esigi,
            stok_takip_edilsin_mi = p_stok_takip_edilsin_mi,
            aktif_mi              = v_aktif,
            katalog_durumu        = v_durum,
            guncelleyen_kullanici = p_yapan_kullanici,
            updated_at            = CURRENT_TIMESTAMP
        WHERE u.stok_kodu = p_stok_kodu;
    END IF;

    -- ---- Ana görsel ---------------------------------------------------
    -- Sıra önemli: uq_urun_tek_ana_gorsel kısmi tekil indeksi bir ürün
    -- için en fazla bir aktif ana görsele izin veriyor, o yüzden ÖNCE
    -- eskiler indiriliyor, SONRA yenisi yükseltiliyor.
    IF p_ana_gorsel_dosya_adi IS NOT NULL THEN
        UPDATE urun_gorselleri g
        SET ana_gorsel_mi = FALSE
        WHERE g.stok_kodu = p_stok_kodu
          AND g.ana_gorsel_mi
          AND g.dosya_adi IS DISTINCT FROM p_ana_gorsel_dosya_adi;

        v_sira := urun_sonraki_gorsel_sirasi(p_stok_kodu);

        -- Aynı dosya adı daha önce kayıtlıysa yeni satır açılmaz, o satır
        -- yeniden ana görsel yapılır.
        -- ON CONFLICT hedefi kolon listesiyle değil KISIT ADIYLA veriliyor:
        -- kolon listesi bir ifade olarak çözümlendiği için "stok_kodu"
        -- fonksiyonun RETURNS TABLE çıktı değişkeniyle çakışıyor
        -- ("column reference stok_kodu is ambiguous").
        INSERT INTO urun_gorselleri (stok_kodu, dosya_adi, ana_gorsel_mi, sira_no, aktif_mi)
        VALUES (p_stok_kodu, p_ana_gorsel_dosya_adi, TRUE, v_sira, TRUE)
        ON CONFLICT ON CONSTRAINT uq_urun_gorselleri_dosya DO UPDATE
            SET ana_gorsel_mi = TRUE, aktif_mi = TRUE
        RETURNING urun_gorselleri.gorsel_id INTO v_gorsel_id;
    END IF;

    IF p_mod = 'EKLE' AND v_durum = 'AKTIF' THEN
        v_mesaj := format('"%s" eklendi ve katalogda yayına alındı.', p_stok_kodu);
    ELSIF p_mod = 'EKLE' THEN
        v_mesaj := format('"%s" taslak olarak eklendi. Ana görsel yüklenene kadar katalogda görünmez.', p_stok_kodu);
    ELSIF v_durum = 'AKTIF' THEN
        v_mesaj := format('"%s" güncellendi.', p_stok_kodu);
    ELSE
        v_mesaj := format('"%s" güncellendi. Ana görseli olmadığı için katalogda hâlâ görünmüyor.', p_stok_kodu);
    END IF;

    RETURN QUERY SELECT p_stok_kodu, v_durum, v_gorsel_id, v_mesaj;
END;
$$;

COMMIT;
