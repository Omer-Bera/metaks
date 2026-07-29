BEGIN;

DROP FUNCTION IF EXISTS stok_hareketi_kaydet(UUID, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER, TEXT);

ALTER TABLE stok_hareketleri
    DROP CONSTRAINT IF EXISTS uq_stok_hareketleri_istemci_kimligi;

ALTER TABLE stok_hareketleri
    DROP COLUMN IF EXISTS istemci_islem_kimligi;

COMMIT;
