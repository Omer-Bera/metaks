-- =========================================================
-- Migration 004: numune lokasyonları — raf düzeyinde hiyerarşi
--
-- İhtiyaç: "bu ürünün numunesi nerede?" sorusunun kütüphanede kitap bulur
-- gibi cevaplanabilmesi ("Numune Dolabı 1 · Raf 3"). Numune ayrı bir varlık
-- olarak değil, var olan lokasyonlar + stok_hareketleri mekanizmasının
-- üzerine oturuyor: numune, ürünün bir adedinin bir yerde durmasıdır ve
-- "depodan numune dolabına taşındı" tam olarak bir TRANSFER'dir. Bu sayede
-- numune ödünç alınıp geri konduğunda hareket kaydı bedavaya geliyor.
-- (docs/INFO.md Faz 8 notu ayrı varlık öneriyordu; oradaki gerekçe
-- urunler üzerinde bir KOLON olmasını eliyor, bunu elemiyor.)
--
-- Bu dosya HENÜZ UYGULANMADI. Ortak veritabanına karşı çalıştırmadan
-- önce kullanıcı onayı gerekir.
--
-- ⚠️ BU MIGRATION BİLEREK ETKİSİZDİR: hiçbir NUMUNE lokasyonu
-- OLUŞTURMAZ, sadece oluşturulabilmesinin önünü açar. Uygulandığı anda
-- lokasyon açılır listeleri hâlâ bugünkü 5 satırı döner ve v_toplam_stok
-- birebir aynı sonucu verir (uygulama öncesi doğrulandı: iki tanım
-- arasında 0 fark satırı, 8 satır / 478 adet). Gerçek numune dolap/raf
-- satırları AYRI bir adımda, arayüzler düzeltildikten SONRA girilecek —
-- bkz. aşağıdaki "UYGULAMA SIRASI".
--
-- UYGULAMA SIRASI (bu sıra önemlidir):
--   1. Bu migration (etkisiz, güvenli)
--   2. Arayüzlerin lokasyon sorguları v_lokasyonlar_detay'a taşınıp
--      yaprak filtresi eklenir:
--        - Appsmith: StokIslemi/LokasyonlariGetir,
--                    LokasyonYonetimi/LokasyonlarListele
--        - Django:   katalog/views.py:651 (stok işlem formu),
--                    katalog/views.py:431 (hareket geçmişi filtresi)
--   3. ANCAK O ZAMAN numune dolap/raf satırları girilir.
--   Adım 3 önce yapılırsa devam eden sayımın yapıldığı ekranın lokasyon
--   kutusu onlarca satırla dolar.
--
-- NOT: numune rafları stok işlemi ekranından TİPE göre dışlanmamalıdır.
-- Numune dolabını açıp 3 adet bulan kişi bunu ancak numune rafını
-- seçebilirse yazabilir — dışlamak çözülmek istenen problemi ortadan
-- kaldırır. Doğru filtre "yaprak mı" (dolaplar çıkar, raflar kalır);
-- liste şişmesi sıralama + arama ile çözülür, dışlama ile değil.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1) Yeni lokasyon tipi: NUMUNE
-- ---------------------------------------------------------
ALTER TABLE lokasyonlar DROP CONSTRAINT lokasyonlar_tip_check;

ALTER TABLE lokasyonlar ADD CONSTRAINT lokasyonlar_tip_check
    CHECK (tip IN ('DAHILI', 'FASON', 'NUMUNE'));

-- ---------------------------------------------------------
-- 2) Hiyerarşi (dolap → raf) ve kısa adres kolonu
--    Mevcut 8 lokasyon ust_lokasyon_id=NULL, kod=NULL kalır; hiçbiri
--    etkilenmez. Düz isimlendirme ("Numune Dolabı 1 – Raf 3" tek satır)
--    yerine hiyerarşi seçildi çünkü dolap sayısı belirsiz ve yeniden
--    düzenlenecek: düz isimde bir dolabı yeniden adlandırmak N satır
--    güncellemek demek, hiyerarşide tek satır.
-- ---------------------------------------------------------
ALTER TABLE lokasyonlar
    ADD COLUMN ust_lokasyon_id INTEGER NULL,
    ADD COLUMN kod VARCHAR(20) NULL;

-- Kısa adres (N1, N1-R3) tekil olmalı ama zorunlu değil — mevcut depo
-- lokasyonlarının kodu yok ve olması da gerekmiyor.
CREATE UNIQUE INDEX uq_lokasyonlar_kod
    ON lokasyonlar (kod) WHERE kod IS NOT NULL;

-- ---------------------------------------------------------
-- 3) Derinlik bilerek 2 seviye ile sınırlı (dolap → raf).
--    Genel amaçlı ağaç kurulmuyor: ihtiyaç yok ve recursive CTE'yi her
--    sorguya bulaştırırdı. Bunu yorum/gelenek olarak bırakmak yerine
--    şemada zorluyoruz — trigger'sız, tamamen bildirimsel, çalışma
--    maliyeti sıfır. Aşağıdaki iki kolon iç tesisattır; arayüzler
--    bunları hiç okumamalı (v_lokasyonlar_detay'ı kullanın).
--
--    Mekanizma: bileşik FK varsayılan MATCH SIMPLE ile çalışır — kök
--    satırda ust_kok_mu NULL olduğu için kısıt uygulanmaz; alt satırda
--    ust_kok_mu TRUE olduğu için ebeveyn mutlaka kok_mu=TRUE olan bir
--    satır olmak zorunda kalır, yani ebeveyn kendisi kök olmalıdır.
-- ---------------------------------------------------------
ALTER TABLE lokasyonlar
    ADD COLUMN kok_mu BOOLEAN
        GENERATED ALWAYS AS (ust_lokasyon_id IS NULL) STORED,
    ADD COLUMN ust_kok_mu BOOLEAN
        GENERATED ALWAYS AS (CASE WHEN ust_lokasyon_id IS NULL THEN NULL ELSE TRUE END) STORED;

ALTER TABLE lokasyonlar
    ADD CONSTRAINT uq_lokasyonlar_id_kok UNIQUE (lokasyon_id, kok_mu);

ALTER TABLE lokasyonlar
    ADD CONSTRAINT lokasyonlar_ust_lokasyon_fkey
    FOREIGN KEY (ust_lokasyon_id, ust_kok_mu)
    REFERENCES lokasyonlar (lokasyon_id, kok_mu)
    ON DELETE RESTRICT;
-- ON UPDATE CASCADE bilerek yok: Postgres üretilmiş kolon içeren bir FK'da
-- ON UPDATE aksiyonuna izin vermiyor (üretilmiş kolon yazılamadığı için).
-- Gerek de yok — lokasyon_id hiç değişmeyen bir serial birincil anahtar.
-- ON DELETE RESTRICT ise rafları olan bir dolabın silinmesini engelliyor
-- (lokasyonlar zaten LokasyonSil ile pasife alınıyor, silinmiyor).

-- ---------------------------------------------------------
-- 4) Ad tekilliği ebeveyn kapsamına alınıyor.
--    Mevcut uq_lokasyonlar_ad_tip (lokasyon_adi, tip) hiyerarşiyi
--    bloke ediyordu: Dolap 1'in "Raf 3"ü ile Dolap 2'nin "Raf 3"ü aynı
--    çifte düşüyor. COALESCE(ust_lokasyon_id, -1) ile kökler için eski
--    davranış birebir korunur (kök adları tip içinde hâlâ tekil),
--    kardeş raflar ise yalnızca kendi dolapları içinde tekil olur.
-- ---------------------------------------------------------
ALTER TABLE lokasyonlar DROP CONSTRAINT uq_lokasyonlar_ad_tip;

CREATE UNIQUE INDEX uq_lokasyonlar_ust_ad_tip
    ON lokasyonlar (COALESCE(ust_lokasyon_id, -1), lokasyon_adi, tip);

CREATE INDEX idx_lokasyonlar_ust ON lokasyonlar (ust_lokasyon_id);

-- ---------------------------------------------------------
-- 5) v_lokasyonlar_detay — açılır listelerin TEK kaynağı.
--    Hem Appsmith hem Django buradan okumalı. yaprak_mi tanımı
--    stok_hareketi_kaydet()'in içindeki kontrolle BİREBİR aynı olmalı
--    (aksi halde UI'da seçilebilen ama fonksiyonun reddettiği bir
--    lokasyon oluşur) — ikisi de "hiç alt lokasyonu yok" der, aktiflik
--    durumuna bakmaz. Bakmama tercihi bilinçli: bütün rafları pasife
--    almanın dolabı yeniden stok tutabilir hale getirmesi öngörülemez
--    bir davranış olurdu.
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_lokasyonlar_detay AS
SELECT
    l.lokasyon_id,
    l.lokasyon_adi,
    l.kod,
    l.tip,
    l.aktif_mi,
    l.ust_lokasyon_id,
    ust.lokasyon_adi AS ust_lokasyon_adi,
    ust.kod          AS ust_kod,
    CASE
        WHEN ust.lokasyon_id IS NULL THEN l.lokasyon_adi::TEXT
        ELSE ust.lokasyon_adi || ' · ' || l.lokasyon_adi
    END AS tam_ad,
    NOT EXISTS (
        SELECT 1 FROM lokasyonlar c WHERE c.ust_lokasyon_id = l.lokasyon_id
    ) AS yaprak_mi
FROM lokasyonlar l
LEFT JOIN lokasyonlar ust ON ust.lokasyon_id = l.ust_lokasyon_id;

-- ---------------------------------------------------------
-- 6) v_lokasyon_stok_ozet'e görüntüleme kolonları ekleniyor.
--    Mevcut kolonların adı/sırası/tipi korunuyor, yeni kolonlar sona
--    ekleniyor — Appsmith sorguları ve Django'nun LokasyonStok modeli
--    isimle seçtiği için etkilenmez.
--    Bu view'ın kendisi NUMUNE'yi DIŞLAMAZ: "numunem nerede?" sorusunun
--    cevabı tam olarak buradaki satırdır.
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_lokasyon_stok_ozet AS
SELECT
    hareket.stok_kodu,
    hareket.lokasyon_id,
    d.lokasyon_adi,
    d.tip AS lokasyon_tipi,
    SUM(hareket.net_miktar) AS mevcut_miktar,
    d.kod    AS lokasyon_kodu,
    d.tam_ad AS lokasyon_tam_adi
FROM (
    SELECT stok_kodu, hedef_lokasyon_id AS lokasyon_id, miktar AS net_miktar
    FROM stok_hareketleri
    WHERE hedef_lokasyon_id IS NOT NULL
    UNION ALL
    SELECT stok_kodu, kaynak_lokasyon_id AS lokasyon_id, -miktar AS net_miktar
    FROM stok_hareketleri
    WHERE kaynak_lokasyon_id IS NOT NULL
) hareket
JOIN v_lokasyonlar_detay d ON d.lokasyon_id = hareket.lokasyon_id
GROUP BY hareket.stok_kodu, hareket.lokasyon_id, d.lokasyon_adi, d.tip, d.kod, d.tam_ad;

-- ---------------------------------------------------------
-- 7) v_toplam_stok artık "SATILABİLİR stok" demek — NUMUNE hariç.
--
--    Bu, var olan bir view'ın anlamını değiştirmektir; normalde
--    kaçınılması gereken bir şey. Burada savunulabilir çünkü:
--      (a) henüz hiç NUMUNE lokasyonu yok, yani bugün sonucu HİÇ
--          değiştirmiyor (uygulama öncesi doğrulandı: 0 fark satırı),
--      (b) view'ın dört tüketicisinin DÖRDÜ de zaten "satılabilir stok"
--          anlamında kullanıyor:
--            Appsmith YonetimAnaSayfasi/OzetIstatistikler (toplam miktar)
--            Appsmith YonetimAnaSayfasi/OzetIstatistikler (kritik sayısı)
--            Appsmith StokOzet/StokOzetGetir (kritik karşılaştırması)
--            Appsmith UrunlerKatalog/KatalogUrunleriGetir ("stokta olanlar")
--          Alternatif (v_toplam_stok fiziksel kalsın, satılabilir yeni
--          view olsun) bu dördünün de düzeltilmesini gerektirirdi ve
--          düzeltilmeyen biri sessizce yanlış cevap verirdi.
--    Vitrindeki 2 numune yüzünden bir ürünün "kritik değil" görünmesi
--    yanlış olurdu; bu tanım onu engelliyor.
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_toplam_stok AS
SELECT
    stok_kodu,
    SUM(mevcut_miktar) AS toplam_miktar
FROM v_lokasyon_stok_ozet
WHERE lokasyon_tipi <> 'NUMUNE'
GROUP BY stok_kodu;

-- ---------------------------------------------------------
-- 8) Fiziksel toplam (numuneler dahil) — "elimizde kaç adet var"
--    sorusunun cevabı. Sayım mutabakatı için.
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_fiziksel_stok AS
SELECT
    stok_kodu,
    SUM(mevcut_miktar) AS toplam_miktar
FROM v_lokasyon_stok_ozet
GROUP BY stok_kodu;

-- ---------------------------------------------------------
-- 9) "Bu ürünün numunesi nerede?" — ekranın doğrudan bağlanacağı view.
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_numune_konumlari AS
SELECT
    stok_kodu,
    lokasyon_id,
    lokasyon_kodu,
    lokasyon_tam_adi,
    mevcut_miktar
FROM v_lokasyon_stok_ozet
WHERE lokasyon_tipi = 'NUMUNE'
  AND mevcut_miktar > 0;

-- ---------------------------------------------------------
-- 10) stok_hareketi_kaydet(): sadece yaprak lokasyona yazılabilir.
--     "Numune Dolabı 1"e stok yazmak anlamsız; raflara yazılmalı.
--     Yeni bir kolon yerine buraya konuldu çünkü yazmanın tek kapısı
--     zaten burası. Bugün hiçbir lokasyonun alt lokasyonu olmadığı için
--     bu kontrol bugün asla tetiklenemez — devam eden sayımı etkilemez.
--     Fonksiyonun geri kalanı 003'teki haliyle birebir aynıdır.
-- ---------------------------------------------------------
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
    v_ust_ad VARCHAR;
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

    -- YENİ (004): sadece yaprak lokasyona hareket yazılabilir. Alt
    -- lokasyonu olan bir lokasyon (örn. "Numune Dolabı 1") kaynak ya da
    -- hedef olarak verilirse reddedilir. v_lokasyonlar_detay.yaprak_mi
    -- ile birebir aynı tanım.
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
