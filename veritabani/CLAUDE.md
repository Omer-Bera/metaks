# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

METAKS DB is a data-engineering project (not a running application) that cleans, standardizes, and migrates a metal/textile hardware catalog (rivets, buckles, buttons, etc. — "toka", "düğme", "kalıp") from a messy source Excel export into a PostgreSQL database, and matches the catalog's embedded product images to stock codes. All code, data, and console output are in Turkish. There is no git repository initialized here yet.

## Environment & commands

- Python venv lives in `venv/`. Activate with `source venv/bin/activate`. There is no `requirements.txt`; key installed packages are `pandas`, `openpyxl`, `psycopg2-binary`, `SQLAlchemy` (see `venv/bin/pip freeze` for the full list).
- Start the database: `docker compose up -d` (container `depo-postgres`, Postgres 16). Stop: `docker compose down`.
- The compose file mounts **`sql/01_schema.sql`** as the init script (`docker-entrypoint-initdb.d`) — that file is the authoritative, current schema. The root-level `init_db.sql` is an older/simpler version that is *not* wired into docker-compose; treat it as legacy unless asked to reconcile the two.
- DB connection used by all scripts: `host=localhost port=5433 dbname=depo_sistemi user=depo_admin password=supergizlisifre` (credentials are hardcoded in each script, e.g. `scripts/database/yukle.py`).
- Connect manually: `docker exec -it depo-postgres psql -U depo_admin -d depo_sistemi`.
- No test suite, linter, or build step exists in this repo — it's a one-shot batch pipeline run manually, step by step.

## Critical gotcha: scripts assume flat, co-located files

The repo was reorganized into `data/`, `scripts/{cleaning,normalization,maintenance,database,images}/`, `images/`, `reports/` subfolders, but the scripts' hardcoded paths were **not** updated for that reorg:

- Older cleaning scripts (`scripts/cleaning/temizle.py`, `olcu_temizle.py`, `duzelt.py`) and `scripts/maintenance/kalip_yedekle.py`, `scripts/cleaning/ayir.py` use bare relative filenames (e.g. `pd.read_excel('temiz_urunler_stoklu.xlsx')`) — they must be run from a directory that actually contains that file (or the file copied next to the script).
- Newer normalization/maintenance/database scripts define `BASE_DIR = Path(__file__).resolve().parent` and read/write files **next to the script itself** (e.g. `scripts/database/yukle.py` expects `scripts/database/temiz_urunler_final.xlsx`), not in `data/processed/` or `data/interim/` where the real data actually lives.
- `scripts/images/gorsel_esle_duzeltilmis_v2.py` writes its output folder as `<path-to-input-excel>/urun_gorselleri_stoklu_duzeltilmis/` (sibling of whatever Excel file you pass it), not into `images/`.

**Before running any script**, check its `GIRIS_DOSYASI`/`EXCEL_DOSYASI`/`BASE_DIR` (or bare filename) constants against where the real file currently lives under `data/`, and either copy the input alongside the script or update the constant — then move the output back into the correct `data/` subfolder afterward. Don't assume a script will "just find" its input from the new folder layout.

## Data pipeline architecture

The catalog moves through two chained stages of scripts, each reading the previous stage's output Excel and writing a new one plus (for the newer scripts) a `_raporu.xlsx` audit report:

**Stage 1 — cleaning (`scripts/cleaning/`, `scripts/maintenance/kalip_yedekle.py`)**
```
urun_listesi_temiz.xlsx (raw, no images)
  → temizle.py        splits complex/multi-code rows into karisik_urunler.xlsx,
                        standardizes ~34 category names, builds parent-child links
  → olcu_temizle.py    parses "ÜRÜN DETAYI (mm)"/"(Boy)" text into numeric olcu_mm/boy_ligne;
                        anything that isn't a clean number falls back into the description
  → duzelt.py           de-duplicates repeated " | "-joined segments in ÜRÜN AÇIKLAMASI
  → kalip_yedekle.py    extracts ÜRÜN GÖZ SAYISI (mold cavity count) into kalip_bilgileri_yedek.xlsx
                        (this attribute is deliberately kept OUT of urunler — see below)
  → ayir.py             splits rows into temiz_urunler_standart.xlsx (clean measurements)
                        vs temiz_urunler_olcu_duzenlenecek.xlsx (needs manual fixing)
```

**Stage 2 — normalization / final prep (`scripts/normalization/`, `scripts/maintenance/`)**
```
temiz_urunler_standart.xlsx
  → birlesik_stok_kodlarini_duzelt.py   fixes merged/combined stock codes
  → ayni_urun_tekrarlarini_sil.py        drops true duplicate rows (same code+category+measurements)
  → secili_stok_tekrarlarini_sil.py      manually curated dedup for a hardcoded set of stock codes
  → final_excel_hazirla.py               hand-codes special multi-variant products (e.g. stock
                                          codes "2108" and "1805012" get split into explicit
                                          ANA_URUN / ALT_PARCA / VARYANT rows), produces
                                          temiz_urunler_final.xlsx
  → scripts/database/yukle.py            validates required columns, unique stock codes, and
                                          parent references, then TRUNCATEs and loads
                                          kategoriler + urunler into PostgreSQL
```
`data/processed/temiz_urunler_final_v1.xlsx` is the checked-in result of that final stage.

**Image pipeline (`scripts/images/`)**
```
urun_listesi.xlsx (~195 MB, has embedded images)
  → gorsel_esle_duzeltilmis_v2.py <path>  parses the OOXML drawing XML directly (not via openpyxl)
                                            to anchor each embedded image to its row/stok kodu,
                                            handles multi-image rows (_1, _2, _3 suffixes),
                                            writes gorsel_esleme_raporu.csv
  → gorsel_stok_kodlarini_guncelle.py     renames image files whose stock code changed during
                                            Stage 2 normalization (using
                                            birlesik_stok_kodu_duzeltme_raporu.xlsx as the map)
  → gorsel_eslesme_raporu.py               cross-checks the final image folder against the
                                            urunler table in Postgres and reports mismatches
```
`images/working/products/` and `images/final/products/` hold the working vs. final-reviewed image sets (2,734 vs. 2,733 files); `reports/excel/gorsel_esleme_raporu.csv`-style reports track the mapping decisions.

## Database schema (`sql/01_schema.sql`)

Design principles (also documented in `README.md`):

- **Master data isolation**: `urunler` holds only immutable physical/identifying attributes (stok_kodu, category, measurements, weight, description). Manufacturing/production data is deliberately excluded.
- **Mold cavity count is out-of-scope for `urunler`** — it's kept in `data/reference/kalip_bilgileri_yedek.xlsx` pending a future `kaliplar` table (Faz 3 in the roadmap).
- **Parent/child/variant relationships**: `urunler.urun_tipi` is `ANA_URUN` (main product) / `ALT_PARCA` (sub-part, e.g. a buckle's separate washer) / `VARYANT` (variant, e.g. old vs. new mold), linked via self-referencing `parent_stok_kodu`. A CHECK constraint enforces that non-`ANA_URUN` rows must have a parent, and a product can't be its own parent.
- **Numeric measurements**: `olcu_mm`, `boy_ligne`, `gramaj_gr` are NUMERIC, not text, to support range queries/sorting.
- **Images** live in `urun_gorselleri`, referencing `urunler.stok_kodu`, with a partial unique index enforcing at most one active "ana_gorsel" (primary image) per product.
- `stok_hareketleri` is a ledger table for future inventory-movement tracking (Faz 4, not yet populated by any script).

## Repository layout

```
data/{raw,interim,processed,reference}/  Excel/CSV at each pipeline stage — see "Data pipeline" above
images/{working,final}/products/         product image files (stok kodu-named)
reports/excel/                           audit reports produced by the normalization/image scripts
reports/logs/                            currently empty
scripts/{cleaning,normalization,maintenance,database,images}/  pipeline scripts, grouped by stage
sql/01_schema.sql                        current DB schema (mounted by docker-compose)
init_db.sql                              legacy schema, not used by docker-compose
docs/INFO.md                             Turkish project README with full roadmap (Faz 2–6)
archive/                                 superseded scripts/data/notebooks kept for reproducibility;
                                          not part of the active pipeline
```

## File protection

These files/folders are load-bearing and should never be deleted or bulk-modified without a backup first (per `docs/INFO.md`): `data/raw/urun_listesi.xlsx` (~195 MB, embedded images — normal Excel saves can corrupt the drawing anchors), `data/interim/temiz_urunler_standart.xlsx`, `data/reference/kalip_bilgileri_yedek.xlsx`, the final product image folder, `sql/01_schema.sql`, and `scripts/database/yukle.py`. Files named `~$*.xlsx` are Excel lock files, not data — only delete them when the corresponding Excel file is confirmed closed.
