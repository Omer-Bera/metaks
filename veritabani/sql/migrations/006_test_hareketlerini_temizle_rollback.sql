-- =========================================================
-- Migration 006 ROLLBACK: silinen test hareketlerini geri yaz
--
-- 006'nın sildiği 30 satırın tamamı, hareket_id'leri ve
-- istemci_islem_kimligi'leriyle birlikte aynen geri gelir — yani
-- uq_stok_hareketleri_istemci_kimligi'nin koruduğu mükerrer gönderim
-- davranışı da silinmeden önceki hâline döner.
--
-- DİKKAT: 006 uygulandıktan sonra Django'nun lokasyon ekranından silinen
-- lokasyonlar varsa bu dosya FK ihlaliyle durur (lokasyon_id 1, 2, 3, 6, 7).
-- O durumda önce lokasyonların geri açılması gerekir; kayıtlar aşağıda:
--   1 Ana Depo (DAHILI, pasif)      2 Sevkiyat Alanı (DAHILI, pasif)
--   3 Fason Atölye 1 (FASON, pasif) 6 Metaks (DAHILI)   7 Depo 1 (DAHILI)
-- =========================================================

BEGIN;

INSERT INTO stok_hareketleri (
    hareket_id, stok_kodu, gecici_kod, miktar,
    kaynak_lokasyon_id, hedef_lokasyon_id, islem_tipi, aciklama,
    islem_tarihi, created_at, istemci_islem_kimligi, yapan_kullanici
) VALUES
    (9, '1210041', NULL, 100, NULL, 3, 'GIRIS', '', '2026-07-29 15:34:02.096491', '2026-07-29 15:34:02.096491', NULL, 'omersalihbera@pm.me'),
    (10, '1210041', NULL, 100, 3, NULL, 'CIKIS', '', '2026-07-29 15:34:09.063235', '2026-07-29 15:34:09.063235', NULL, 'omersalihbera@pm.me'),
    (11, '1104207', NULL, 100, NULL, 1, 'GIRIS', '', '2026-07-29 15:37:05.128172', '2026-07-29 15:37:05.128172', NULL, 'omersalihbera@pm.me'),
    (12, '1104207', NULL, 100, 1, NULL, 'CIKIS', '', '2026-07-29 15:37:11.445475', '2026-07-29 15:37:11.445475', NULL, 'omersalihbera@pm.me'),
    (13, '1005910', NULL, 1000, NULL, 1, 'GIRIS', '', '2026-07-29 15:51:17.830102', '2026-07-29 15:51:17.830102', NULL, 'omersalihbera@pm.me'),
    (14, '1005910', NULL, 1000, 1, NULL, 'CIKIS', '', '2026-07-29 15:51:21.572066', '2026-07-29 15:51:21.572066', NULL, 'omersalihbera@pm.me'),
    (15, '1021112', NULL, 10000, NULL, 1, 'GIRIS', '', '2026-07-29 15:53:34.670382', '2026-07-29 15:53:34.670382', NULL, 'omersalihbera@pm.me'),
    (16, '1021112', NULL, 10000, 1, NULL, 'CIKIS', '', '2026-07-29 15:53:37.359595', '2026-07-29 15:53:37.359595', NULL, 'omersalihbera@pm.me'),
    (23, '1039024', NULL, 1000, NULL, 1, 'DUZELTME', '', '2026-07-29 16:18:21.966835', '2026-07-29 16:18:21.966835', NULL, 'omersalihbera@pm.me'),
    (24, '1039024', NULL, 1000, 1, NULL, 'DUZELTME', '', '2026-07-29 16:18:25.238426', '2026-07-29 16:18:25.238426', NULL, 'omersalihbera@pm.me'),
    (25, '1039024', NULL, 1000, NULL, 1, 'DUZELTME', '', '2026-07-29 16:18:30.820037', '2026-07-29 16:18:30.820037', NULL, 'omersalihbera@pm.me'),
    (26, '1039024', NULL, 1000, 1, 3, 'TRANSFER', '', '2026-07-29 16:18:35.253512', '2026-07-29 16:18:35.253512', NULL, 'omersalihbera@pm.me'),
    (29, '1039024', NULL, 1000, 3, 1, 'TRANSFER', '', '2026-07-29 16:18:50.758516', '2026-07-29 16:18:50.758516', NULL, 'omersalihbera@pm.me'),
    (30, '1039024', NULL, 1000, 1, NULL, 'DUZELTME', '', '2026-07-29 16:19:05.817672', '2026-07-29 16:19:05.817672', NULL, 'omersalihbera@pm.me'),
    (31, '1005910', NULL, 1000, NULL, 1, 'DUZELTME', '', '2026-07-29 16:26:54.215428', '2026-07-29 16:26:54.215428', NULL, 'omersalihbera@pm.me'),
    (32, '1005910', NULL, 1000, 1, 2, 'TRANSFER', '', '2026-07-29 16:27:19.411189', '2026-07-29 16:27:19.411189', NULL, 'omersalihbera@pm.me'),
    (33, '1005910', NULL, 1000, 2, NULL, 'DUZELTME', '', '2026-07-29 16:27:41.327835', '2026-07-29 16:27:41.327835', NULL, 'omersalihbera@pm.me'),
    (34, '100012', NULL, 1000, NULL, 1, 'GIRIS', '', '2026-07-29 16:32:24.181038', '2026-07-29 16:32:24.181038', 'fc8638d3-967a-4692-bf93-fbd956fcfb6b'::uuid, 'omersalihbera@pm.me'),
    (35, '100012', NULL, 1000, 1, 2, 'TRANSFER', '', '2026-07-29 16:32:30.41942', '2026-07-29 16:32:30.41942', '14b1a87d-2c02-4271-9363-b02f9450f522'::uuid, 'omersalihbera@pm.me'),
    (36, '100012', NULL, 1000, 2, 1, 'TRANSFER', '', '2026-07-29 16:32:38.351296', '2026-07-29 16:32:38.351296', '6a751252-6783-4d5f-a3b8-c6d5b56c25a0'::uuid, 'omersalihbera@pm.me'),
    (37, '100012', NULL, 1000, 1, NULL, 'DUZELTME', '', '2026-07-29 16:32:45.172812', '2026-07-29 16:32:45.172812', 'd7f186ab-83fe-4d86-b9ce-aa097afdc35f'::uuid, 'omersalihbera@pm.me'),
    (45, '1001020', NULL, 1000, NULL, 6, 'DUZELTME', NULL, '2026-07-30 14:27:57.207478', '2026-07-30 14:27:57.207478', '8d6ade35-1b43-4fbb-b165-05f83980b793'::uuid, 'omersalihbera@pm.me'),
    (46, '1001020', NULL, 1000, 6, NULL, 'DUZELTME', NULL, '2026-07-30 14:28:10.473347', '2026-07-30 14:28:10.473347', '6576388c-f048-424d-9b14-530b0d307abb'::uuid, 'omersalihbera@pm.me'),
    (47, '1001013', NULL, 500, NULL, 6, 'GIRIS', 'Django arayüzü ilk gerçek kayıt denemesi', '2026-07-30 14:36:20.826428', '2026-07-30 14:36:20.826428', '0132b23d-3a11-4643-932b-48f1ed08fc6d'::uuid, 'omersalihbera@pm.me'),
    (48, '1001013', NULL, 200, 6, 7, 'TRANSFER', NULL, '2026-07-30 14:36:21.206536', '2026-07-30 14:36:21.206536', '830b1a2f-d3d4-40f2-9e5c-d45813f3a3f8'::uuid, 'omersalihbera@pm.me'),
    (49, '1001013', NULL, 50, 6, NULL, 'SAYIM_DEVRI', NULL, '2026-07-30 14:36:21.461973', '2026-07-30 14:36:21.461973', 'cd6186ee-96a5-4715-ab65-fba35f4633f8'::uuid, 'omersalihbera@pm.me'),
    (50, '1001013', NULL, 7, NULL, 6, 'GIRIS', 'mukerrer gonderim testi', '2026-07-30 14:37:51.894006', '2026-07-30 14:37:51.894006', '47eb66a2-1405-4b48-a9e2-8e19d6da1039'::uuid, 'omersalihbera@pm.me'),
    (51, '1001013', NULL, 7, NULL, 6, 'GIRIS', 'mukerrer gonderim testi', '2026-07-30 14:39:11.31769', '2026-07-30 14:39:11.31769', '93e1ca22-5298-4c5b-86d2-ef2f84eecd9d'::uuid, 'omersalihbera@pm.me'),
    (52, '1001013', NULL, 7, NULL, 6, 'GIRIS', 'mukerrer testi 1785422409120', '2026-07-30 14:40:12.728955', '2026-07-30 14:40:12.728955', 'c5af9967-6e04-404d-9a26-7514fe29c2c7'::uuid, 'omersalihbera@pm.me'),
    (53, '1001013', NULL, 7, NULL, 6, 'GIRIS', 'mukerrer testi 1785422496239', '2026-07-30 14:41:40.245829', '2026-07-30 14:41:40.245829', 'cc40eb64-2ce7-4137-a580-c74e78825fd9'::uuid, 'omersalihbera@pm.me');

-- Sequence, açıkça yazılan id'lerin üstüne alınıyor; yoksa sonraki INSERT
-- 1'den başlayıp mevcut satırlarla çakışırdı.
SELECT setval('stok_hareketleri_hareket_id_seq', 53, true);

COMMIT;
