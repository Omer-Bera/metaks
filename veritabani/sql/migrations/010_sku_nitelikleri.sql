-- =========================================================
-- Migration 010: SKU nitelik modeli — lak/vernik/işçilik ve montaj hali adı
--
-- İki iş yapar:
--   1) SKU kimliğine üç yeni ikili nitelik ekler (lak, vernik, işçilik) ve
--      tekillik indeksini bu üç kolonu da kapsayacak şekilde yeniden kurar;
--   2) montaj hali değerlerindeki adlandırma hatasını düzeltir: 'HAM' -> 'DEMONTE'.
--      Bu projede "ham" KAPLANMAMIŞ demektir (kaplamalar tablosundaki 'ham'
--      satırı). Aynı kelimenin montaj hali için de kullanılması hem ekranda hem
--      SQL'de iki ayrı anlamı karıştırıyordu.
--
-- Boya ve mine rengi AYNEN KORUNUR: boya_renk_id / mine_renk_id kolonları ve
-- tekillik indeksindeki yerleri değişmez. Yeni nitelikler ikili olduğu için
-- ayrı bir nitelik/EAV tablosu açılmaz.
--
-- ---------------------------------------------------------
-- stok_kalemi_kaydet() neden ALTER FUNCTION ... RENAME ile değiştiriliyor
-- ---------------------------------------------------------
-- Fonksiyonun imzası üç yeni BOOLEAN parametreyle değiştiği için
-- `CREATE OR REPLACE` yetmez: PostgreSQL onu ayrı bir aşırı yükleme (overload)
-- olarak yaratır ve 6 parametreli ESKİ gövde çağrılabilir kalırdı. Eski gövde
-- montaj halini 'HAM' diye doğruluyor; 010 sonrası CHECK bu değeri kabul
-- etmediği için o yol ya sessizce yanlış SKU üretir ya da anlaşılmaz bir CHECK
-- hatası verir.
--
-- Bunun yerine 008'in `stok_hareketi_kaydet` için kullandığı desen izleniyor:
-- eski fonksiyon `stok_kalemi_kaydet_v008` adına RENAME edilir (gövde
-- kaybolmaz, ama artık eski adıyla çağrılamaz), yeni imza sıfırdan CREATE
-- edilir. Rollback yeni fonksiyonu DROP edip adı geri alır; böylece ~90
-- satırlık 008 gövdesini rollback dosyasına kopyalamak gerekmez.
--
-- Yeni üç BOOLEAN parametrenin DEFAULT'u YOKTUR. Sebebi bilinçli: varsayılan
-- verilseydi güncellenmemiş bir çağrı sessizce "laksız/verniksiz/işçiliksiz"
-- kaydederdi. Varsayılansız imzada eski 6 parametreli çağrı tip hatasıyla
-- gürültülü biçimde patlar.
--
-- ---------------------------------------------------------
-- Kapsam notu — stok_hareketi_kaydet() sarmalayıcısı
-- ---------------------------------------------------------
-- 008'in uyumluluk sarmalayıcısı `stok_hareketi_kaydet()` gövdesinde
-- `WHEN p_montaj IS FALSE THEN 'HAM'` literali taşıyor. 010'dan sonra
-- montaj_durumu hiçbir satırda 'HAM' olamayacağı için bu dal HİÇBİR ZAMAN
-- eşleşmez ve sarmalayıcı "eşleşen SKU yok" diye hata verirdi. Adlandırma
-- düzeltmesinin parçası olduğu için literal burada da 'DEMONTE' yapılıyor;
-- imza değişmediğinden `CREATE OR REPLACE` yeterlidir. Rollback 008 gövdesini
-- ('HAM' literaliyle) geri yazar.
--
-- ---------------------------------------------------------
-- Uygulama öncesi ölçülen durum (2026-08-06, salt-okunur)
-- ---------------------------------------------------------
--   stok_kalemleri: 2.973 satır, TAMAMI nitelik_durumu='BELIRSIZ' ve
--     montaj_durumu='BELIRSIZ'. 'HAM' montaj halinde TEK BİR SATIR YOK,
--     yani aşağıdaki UPDATE bugün 0 satır dokunur.
--   kaplamalar: 'ham' satırı kaplama_id=12, aktif_mi=TRUE ve HİÇ KULLANILMIYOR
--     (stok_kalemleri 0, stok_hareketleri 0, urunler 0 satır).
--   Bu iki gerçek hem yerel Docker hem Raspberry Pi kopyasında aynı.
--
-- Test notu: `sql/tests/008_stok_urun_modeli_test.sql` hem eski 6 parametreli
-- imzayı hem 'HAM' değerini kullanır; 010 uygulanmış bir kopyada BEKLENDİĞİ
-- GİBİ hata verir. 010 sonrası kabul testi
-- `sql/tests/010_sku_nitelikleri_test.sql` dosyasıdır.
--
-- Ortak veritabanına uygulamadan önce AGENTS.md uyarıları gereği yedek,
-- disposable kopya testi ve kullanıcı onayı zorunludur.
-- =========================================================

BEGIN;

-- ---------------------------------------------------------
-- 1) Üç yeni ikili nitelik
-- ---------------------------------------------------------
ALTER TABLE stok_kalemleri
    ADD COLUMN lak_mi     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN vernik_mi  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN iscilik_mi BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN stok_kalemleri.lak_mi IS
'SKU kimliğinin parçası: kalem laklı mı? DİKKAT — nitelik_durumu=''BELIRSIZ''
(miras) satırlardaki FALSE değeri BİLGİ DEĞİLDİR, yalnızca kolon
varsayılanıdır. Tekillik indeksi WHERE nitelik_durumu=''TANIMLI'' olduğu için
bu satırlarda kimliğe girmez. Belirsizliği kaplama_id IS NULL''ın taşıdığıyla
aynıdır: miras SKU''ların lak bilgisi YOKTUR, "laksız" değildir. Bu FALSE''ı
"laksız" diye okuyan bir filtre miras SKU''lar hakkında yalan söyler.';

COMMENT ON COLUMN stok_kalemleri.vernik_mi IS
'SKU kimliğinin parçası: kalem vernikli mi? DİKKAT — nitelik_durumu=''BELIRSIZ''
(miras) satırlardaki FALSE değeri BİLGİ DEĞİLDİR, yalnızca kolon
varsayılanıdır. Tekillik indeksi WHERE nitelik_durumu=''TANIMLI'' olduğu için
bu satırlarda kimliğe girmez. Belirsizliği kaplama_id IS NULL''ın taşıdığıyla
aynıdır: miras SKU''ların vernik bilgisi YOKTUR, "verniksiz" değildir. Bu
FALSE''ı "verniksiz" diye okuyan bir filtre miras SKU''lar hakkında yalan
söyler.';

COMMENT ON COLUMN stok_kalemleri.iscilik_mi IS
'SKU kimliğinin parçası: kalem üzerinde işçilik var mı? DİKKAT —
nitelik_durumu=''BELIRSIZ'' (miras) satırlardaki FALSE değeri BİLGİ DEĞİLDİR,
yalnızca kolon varsayılanıdır. Tekillik indeksi WHERE
nitelik_durumu=''TANIMLI'' olduğu için bu satırlarda kimliğe girmez.
Belirsizliği kaplama_id IS NULL''ın taşıdığıyla aynıdır: miras SKU''ların
işçilik bilgisi YOKTUR, "işçiliksiz" değildir. Bu FALSE''ı "işçiliksiz" diye
okuyan bir filtre miras SKU''lar hakkında yalan söyler.';

-- ---------------------------------------------------------
-- 2) Tekillik indeksi üç yeni kolonu da kapsar
--    Kısmi indeks koşulu AYNEN korunur: miras (BELIRSIZ) satırlar hâlâ
--    indekse girmez, yani 2.973 miras SKU birbirini engellemez.
-- ---------------------------------------------------------
DROP INDEX uq_stok_kalemleri_nitelik;

CREATE UNIQUE INDEX uq_stok_kalemleri_nitelik
    ON stok_kalemleri (
        urun_kodu,
        COALESCE(kaplama_id, -1),
        COALESCE(boya_renk_id, -1),
        COALESCE(mine_renk_id, -1),
        montaj_durumu,
        lak_mi,
        vernik_mi,
        iscilik_mi
    )
    WHERE nitelik_durumu = 'TANIMLI';

-- ---------------------------------------------------------
-- 3) montaj_durumu: 'HAM' -> 'DEMONTE'
--    Sıra zorunlu: önce CHECK düşer, sonra satırlar güncellenir, sonra yeni
--    CHECK eklenir. Kısıt adı 008'deki otomatik adla aynı tutuluyor ki
--    rollback simetrik olsun.
-- ---------------------------------------------------------
ALTER TABLE stok_kalemleri
    DROP CONSTRAINT stok_kalemleri_montaj_durumu_check;

UPDATE stok_kalemleri SET montaj_durumu = 'DEMONTE' WHERE montaj_durumu = 'HAM';

ALTER TABLE stok_kalemleri
    ADD CONSTRAINT stok_kalemleri_montaj_durumu_check
    CHECK (montaj_durumu IN ('BELIRSIZ', 'DEMONTE', 'YARI_MONTE', 'MONTE'));

-- ---------------------------------------------------------
-- 4) stok_kalemi_kaydet(): yeni imza
--    Eski gövde rollback için başka adla saklanır (dosya başındaki gerekçe).
-- ---------------------------------------------------------
ALTER FUNCTION stok_kalemi_kaydet(
    VARCHAR, INTEGER, VARCHAR, VARCHAR, VARCHAR, VARCHAR
) RENAME TO stok_kalemi_kaydet_v008;

CREATE FUNCTION stok_kalemi_kaydet(
    p_urun_kodu VARCHAR,
    p_kaplama_id INTEGER,
    p_boya_renk VARCHAR,
    p_mine_renk VARCHAR,
    p_montaj_durumu VARCHAR,
    p_lak_mi BOOLEAN,
    p_vernik_mi BOOLEAN,
    p_iscilik_mi BOOLEAN,
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
    IF p_montaj_durumu NOT IN ('DEMONTE', 'YARI_MONTE', 'MONTE') THEN
        RAISE EXCEPTION 'Montaj durumu DEMONTE, YARI_MONTE veya MONTE olmalıdır.';
    END IF;
    -- TANIMLI bir SKU'da üç nitelik de açıkça bilinmek zorundadır; NULL
    -- "bilinmiyor" demektir ve bu fonksiyon belirsiz SKU üretmez.
    IF p_lak_mi IS NULL OR p_vernik_mi IS NULL OR p_iscilik_mi IS NULL THEN
        RAISE EXCEPTION 'Lak, vernik ve işçilik nitelikleri boş bırakılamaz; her biri evet/hayır olmalıdır.';
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

    -- Bul-veya-oluştur: eşleşme artık üç yeni kolonu da karşılaştırır.
    -- Buradaki idempotent davranış (atlandi=TRUE ile mevcut SKU'yu döndürmek)
    -- korunmak zorundadır; sonraki faz fason iş emrinde hedef SKU'yu buna
    -- dayanarak türetecek.
    SELECT sk.stok_kalemi_id, sk.sku_kodu INTO v_id, v_sku
    FROM stok_kalemleri sk
    WHERE sk.urun_kodu = p_urun_kodu
      AND sk.nitelik_durumu = 'TANIMLI'
      AND sk.kaplama_id IS NOT DISTINCT FROM p_kaplama_id
      AND sk.boya_renk_id IS NOT DISTINCT FROM v_boya_id
      AND sk.mine_renk_id IS NOT DISTINCT FROM v_mine_id
      AND sk.montaj_durumu = p_montaj_durumu
      AND sk.lak_mi = p_lak_mi
      AND sk.vernik_mi = p_vernik_mi
      AND sk.iscilik_mi = p_iscilik_mi;

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
        boya_renk_id, mine_renk_id, montaj_durumu,
        lak_mi, vernik_mi, iscilik_mi, olusturan_kullanici
    ) VALUES (
        v_sku, p_urun_kodu, 'TANIMLI', p_kaplama_id,
        v_boya_id, v_mine_id, p_montaj_durumu,
        p_lak_mi, p_vernik_mi, p_iscilik_mi, p_yapan_kullanici
    ) RETURNING stok_kalemleri.stok_kalemi_id INTO v_id;

    RETURN QUERY SELECT v_id, v_sku, FALSE, 'Stok varyantı oluşturuldu.'::TEXT;
END;
$$;

-- ---------------------------------------------------------
-- 5) Uyumluluk sarmalayıcısındaki 'HAM' literali
--    İmza değişmediği için CREATE OR REPLACE yeterli. Gövde 008'dekiyle
--    birebir aynıdır; TEK fark montaj eşleştirmesinde 'HAM' -> 'DEMONTE'.
-- ---------------------------------------------------------
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
                                     WHEN p_montaj IS FALSE THEN 'DEMONTE'
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

-- ---------------------------------------------------------
-- 6) kaplamalar: 'ham' satırı pasife alınır
--    SİLİNMEZ: kaplama_id'ye bakan FK'lar ON DELETE RESTRICT ve bu proje
--    soft-delete kullanıyor. Ölçümde satır hiçbir yerde kullanılmıyordu;
--    pasife alındıktan sonra stok_kalemi_kaydet() onu "aktif kaplama"
--    bulamadığı için reddeder, ama geçmiş referanslar bozulmaz.
-- ---------------------------------------------------------
UPDATE kaplamalar SET aktif_mi = FALSE WHERE lower(btrim(kaplama_adi)) = 'ham';

COMMIT;
