# AGENTS.md — METAKS veri ve şema katmanı

This file applies to everything under `veritabani/`. Read the repository-root
`AGENTS.md` first. The Django application is under `web/` and has separate
instructions.

## Scope

This directory owns:

- the Excel cleaning and normalization pipeline;
- the PostgreSQL base schema and numbered migrations;
- database import, export, search, image-matching, and backup scripts;
- the product-image files shared with Django and nginx.

Code, data columns, database messages, and user-facing output are Turkish. Keep
new operational documentation concise and prefer durable rules over live row
counts. Point-in-time state and the roadmap belong in `docs/INFO.md`.

## Environment and commands

The pipeline and Django use different virtual environments. Do not mix them.

```bash
cd veritabani
python3 -m venv venv
venv/bin/pip install -r requirements.txt
source venv/bin/activate
```

Run Compose from this directory:

```bash
docker compose up -d
docker compose ps
docker compose down
```

`docker-compose.yml` deliberately pins `name: metaks_db`. Do not remove or
rename it: the existing PostgreSQL volume is named with that prefix. The
services are PostgreSQL (`depo-postgres`, host port 5433) and the read-only nginx
image server (`depo-gorsel-sunucu`, host port 8083).

`TAILSCALE_BIND_ADDRESS` can be set in the ignored `.env`; `.env.example`
documents the local default and Raspberry Pi setting. Do not expose these ports
to the public internet.

## Schema authority and migrations

The schema authority is the ordered combination of:

1. `sql/01_schema.sql` — the base schema installed into a new PostgreSQL volume;
2. `sql/migrations/` — numbered forward migrations applied in order.

`01_schema.sql` alone is not a complete representation of the live schema. It
does not contain the objects introduced by migrations 001–007. Compose mounts
only the base file into `docker-entrypoint-initdb.d`; it does not apply numbered
migrations automatically.

Each migration normally has `00N_description.sql` and
`00N_description_rollback.sql`, both transaction-wrapped. Before changing or
applying one:

- inspect the live schema and data preconditions;
- take a current backup;
- test forward and rollback paths on a disposable/restored copy or safely inside
  a transaction when the script permits it;
- verify affected columns, constraints, views, functions, row totals, and
  invariants after application;
- obtain the user's explicit approval before changing the shared database.

Migration `006_test_hareketlerini_temizle.sql` is a historical data-cleanup
migration, not schema bootstrap. It deletes exactly 30 known test movements and
guards for that exact precondition. Never apply it blindly to a fresh database
or to a ledger containing real data. On a fresh empty bootstrap it should be
skipped; apply 007 only after confirming the intended prior schema is present.

A fresh reconstruction is not a blind `001`-through-`007` loop. Migration 001
backfills catalog state from product/image rows, while the legacy loaders do not
write `katalog_durumu`. The proven high-level order is: install the base schema,
load products, load image metadata, apply 001–005, skip the historical 006, then
apply 007. Revalidate this order and every data precondition on a disposable
copy before using it; restoring a verified dump is the preferred setup path.

Django must never run migrations against the `depo_sistemi` database. Every
model mapped to this schema is `managed = False`; Django's own migrations target
the separate `metaks_web` database.

## Database write gates

Business rules live in PostgreSQL. Application code passes parameters and shows
the Turkish result/error message; it must not duplicate those rules.

- Never `INSERT` directly into `stok_hareketleri`. After migration 008 use
  `stok_islemi_kaydet()`; `stok_hareketi_kaydet()` is only the legacy wrapper.
- Never directly `INSERT` or `UPDATE` `urunler`. Use `urun_kaydet()`.
- `stok_islemi_kaydet()` owns document and request idempotency, purpose/ledger
  consistency, location and detailed-balance checks, count differences, SKU/lot/
  status semantics, corrections, and subcontracting transaction atomicity.
- `urun_kaydet()` owns create/update intent, product relationships, audit fields,
  catalog state, and primary-image metadata.
- Read contracts and exact fields are documented in
  `docs/aktif-urun-veri-sozlesmesi.md` and, after migration 008,
  `docs/stok-urun-veri-sozlesmesi.md`.

Location management is the limited exception: Django writes `lokasyonlar`
directly, while PostgreSQL constraints enforce hierarchy and uniqueness. Read
locations through `v_lokasyonlar_detay`, and offer only active leaf rows for
stock movements.

## Data pipeline

The active stages, relative to this directory, are:

```text
data/interim/urun_listesi_temiz.xlsx
  -> scripts/cleaning/temizle.py
  -> scripts/cleaning/olcu_temizle.py
  -> scripts/cleaning/duzelt.py
  -> scripts/maintenance/kalip_yedekle.py
  -> scripts/cleaning/ayir.py

data/interim/temiz_urunler_standart.xlsx
  -> scripts/normalization/birlesik_stok_kodlarini_duzelt.py
  -> scripts/maintenance/ayni_urun_tekrarlarini_sil.py
  -> scripts/maintenance/secili_stok_tekrarlarini_sil.py
  -> data/interim/temiz_urunler_tekrarsiz_v2.xlsx

data/interim/karisik_urunler.xlsx
  -> scripts/normalization/karisik_urunleri_coz.py
  -> scripts/normalization/karisik_urunleri_birlestir.py
  -> scripts/normalization/final_excel_hazirla.py
  -> data/processed/temiz_urunler_final_v2.xlsx
  -> scripts/database/yukle.py
```

The mixed-stock-code rule is a business rule, not an implementation guess. Read
`docs/karisik_stok_kodu_kurali.md` before changing that stage. Derived stock
codes concatenate family and token with no separator (`108` + `617` = `108617`).

Several older cleaning/normalization scripts still use bare filenames or
script-relative paths. Their outputs already exist. Before rerunning an old
stage, inspect its path constants and run it only against a protected copy; do
not assume it understands the current `data/` layout.

`scripts/database/yukle.py` validates, then truncates and reloads catalog tables.
Treat it as destructive: confirm the input file and backup the database first.

## Images, exports, and backups

`images/final/products/` is one shared directory:

- nginx mounts it read-only and serves product images;
- Django writes new uploads to it from the host;
- database rows store only the filename, not a URL or filesystem path.

Do not rename, overwrite, bulk-edit, or merge image directories casually. New
uploads must write the file first, call `urun_kaydet()` second, and remove the new
file if the database call fails.

Useful generated outputs:

- `scripts/database/csv_guncelle.py` refreshes searchable CSV exports;
- `scripts/database/tablolari_disa_aktar.py` creates the current DB workbook;
- `scripts/images/urun_katalogu_olustur.py` creates the ignored illustrated
  catalog workbook;
- `scripts/maintenance/yedek_al.sh` dumps both databases and copies product
  images. Set `BACKUP_DEST` to a separate disk/NAS for a real backup.

## Protected files and test traps

Do not delete or bulk-modify these without a verified backup:

```text
data/raw/urun_listesi.xlsx
data/processed/temiz_urunler_final_v2.xlsx
data/reference/kalip_bilgileri_yedek.xlsx
images/final/products/
sql/01_schema.sql
scripts/database/yukle.py
```

The raw workbook contains embedded images; saving it in Excel can move drawing
anchors. A root-level `urun_listesi.xlsx` may be the user's live working copy and
is ignored; leave it alone unless explicitly asked. `~$*.xlsx` files are Excel
lock files and may be removed only after confirming the workbook is closed.

This layer has no automated test suite. Use targeted validation proportional to
risk: compile/import changed Python, run non-destructive report scripts on copies,
compare row counts/checksums, and validate SQL against a disposable or restored
database. Never use the shared live database as an unbounded test fixture.
