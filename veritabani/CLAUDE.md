# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

METAKS DB is a data-engineering project (not a running application) that cleans, standardizes, and migrates a metal/textile hardware catalog (rivets, buckles, buttons, etc. — "toka", "düğme", "kalıp") from a messy source Excel export into a PostgreSQL database, and links the catalog's embedded product images to stock codes. All code, data, and console output are in Turkish. Current point-in-time state (row counts, coverage stats) lives in `docs/INFO.md`, not here — check that file for "what does the DB currently contain," this file is about how the pipeline works.

## Environment & commands

- Python venv lives in `venv/`. Activate with `source venv/bin/activate`. There is no `requirements.txt`; key packages: `pandas`, `openpyxl`, `psycopg2-binary`, `Pillow` (for thumbnail generation), `SQLAlchemy` (see `venv/bin/pip freeze` for the full list).
- Start everything: `docker compose up -d` — brings up three services: `veritabani` (Postgres 16, container `depo-postgres`), `nocodb` (container `depo-nocodb`, port 8080 — evaluated then abandoned, see "UI / arayüz katmanı" below), `appsmith` (container `depo-appsmith`, port 8082 — the active low-code UI layer). Stop: `docker compose down`.
- The compose file mounts **`sql/01_schema.sql`** as the init script — that file is the authoritative, current schema. The root-level `init_db.sql` is an older/simpler version, not wired into docker-compose; legacy.
- DB connection used by all scripts: `host=localhost port=5433 dbname=depo_sistemi user=depo_admin password=supergizlisifre` (credentials hardcoded per-script).
- Connect manually: `docker exec -it depo-postgres psql -U depo_admin -d depo_sistemi`.
- No test suite, linter, or build step — this is a manually-run, step-by-step batch pipeline.
- **Git**: this is now a git repo (initialized 2026-07-28). Local repo-scoped `user.name`/`user.email` are set (not global). Global git config has SSH commit signing enabled (`gpg.format=ssh`) via a 1Password SSH agent; if `SSH_AUTH_SOCK` in the shell doesn't point at 1Password's agent socket, commits fail with "no SSH private key found" — ask the user before falling back to `git commit --no-gpg-sign` (only do this with explicit permission, never silently).

## Critical: stok kodu format for derived/split products

When a "karışık" (combined) stock-code cell gets split into individual products (see below), the resulting stok kodu is **the family number and the token concatenated directly, with NO separator** — e.g. family `108` + token `617` → `108617`. This was verified 2026-07-29 against 282 real pre-existing examples in the catalog (e.g. `689212` = family `689` + category digit `2` + size `12` → an actual RİVET, 12mm product) and against `urun_listesi.xlsx` itself. An earlier attempt used a hyphen (`108-617`) — that was wrong and was corrected; if you see hyphenated codes anywhere, they're stale. This matters operationally too: warehouse staff doing physical stock counts write the full concatenated code (not the bare token), so this format is what any future count-file integration needs to match against.

## Data pipeline architecture

The catalog moves through three chained stages, each reading the previous stage's output and writing a new file plus (for newer scripts) a `_raporu.xlsx` audit report.

**Stage 1 — cleaning (`scripts/cleaning/`, `scripts/maintenance/kalip_yedekle.py`)**

```text
urun_listesi_temiz.xlsx (raw, no images)
  → temizle.py        splits complex/multi-code rows into karisik_urunler.xlsx (857 rows),
                        standardizes ~34 category names, builds parent-child links
  → olcu_temizle.py    parses "ÜRÜN DETAYI (mm)"/"(Boy)" text into numeric olcu_mm/boy_ligne
  → duzelt.py           de-duplicates repeated " | "-joined segments in ÜRÜN AÇIKLAMASI
  → kalip_yedekle.py    extracts ÜRÜN GÖZ SAYISI (mold cavity count) into kalip_bilgileri_yedek.xlsx
  → ayir.py             splits into temiz_urunler_standart.xlsx (clean) vs
                        temiz_urunler_olcu_duzenlenecek.xlsx (needs manual fixing, never processed further — archived, see below)

```

**Stage 2 — normalization (`scripts/normalization/`, `scripts/maintenance/`)**

```text
temiz_urunler_standart.xlsx
  → birlesik_stok_kodlarini_duzelt.py   fixes merged/combined stock codes
  → ayni_urun_tekrarlarini_sil.py        drops true duplicate rows
  → secili_stok_tekrarlarini_sil.py      manually curated dedup for hardcoded stock codes
  → temiz_urunler_tekrarsiz_v2.xlsx

```

**Stage 3 — karışık (combined-code) resolution, added 2026-07-29 (`scripts/normalization/`)**

```text
karisik_urunler.xlsx (857 rows, multi-code cells like "108/109;112;617;620;015;017;023")
  → karisik_urunleri_coz.py       decodes each cell: first code = family/grouping key (not a
                                    real product), each subsequent token = [1-digit category][size],
                                    cross-validated against the row's own mm-list per category
                                    subgroup. See docs/karisik_stok_kodu_kurali.md for the full
                                    decode rule and the empirically-derived digit→category map.
                                    ~84% auto-resolved -> karisik_urunler_cozulmus.xlsx;
                                    rest -> reports/excel/karisik_urun_cozme_raporu.xlsx
                                    (Elle_Bakilmasi_Gereken sheet). Also guards against a resolved
                                    code colliding with an already-existing standalone product
                                    (rare; routes the collision to manual review instead of
                                    overwriting either side).
  → karisik_urunleri_birlestir.py  merges resolved variants into temiz_urunler_tekrarsiz_v2.xlsx
                                    -> temiz_urunler_karisik_dahil.xlsx
  → final_excel_hazirla.py         hand-codes special multi-variant products (stock codes "2108"
                                    and "1805012" split into ANA_URUN/ALT_PARCA/VARYANT rows),
                                    produces data/processed/temiz_urunler_final_v2.xlsx
  → scripts/database/yukle.py      validates + TRUNCATEs + loads kategoriler + urunler into Postgres

```

**Image pipeline (`scripts/images/`, `scripts/database/`)**

```text
urun_listesi.xlsx (~195 MB, embedded images)
  → gorsel_esle_duzeltilmis_v2.py <path>  parses OOXML drawing XML directly to anchor each
                                            embedded image to its row/stok kodu, writes
                                            gorsel_esleme_raporu.csv into images/working/products/
  → gorsel_stok_kodlarini_guncelle.py     renames images whose stock code changed during Stage 2
  → gorsel_eslesme_raporu.py               cross-checks images/final/products/ against urunler,
                                            writes reports/excel/gorsel_eslesme_raporu.xlsx
                                            (Eslesen_Gorseller / Eslesmeyen_Gorseller / etc. sheets)
  → scripts/database/gorselleri_yukle.py   loads the Eslesen_Gorseller sheet into urun_gorselleri;
                                            ana_gorsel_mi/sira_no derived from the "_N" suffix in
                                            the filename (sira=1 → primary image)

```

**Archiving pass (`scripts/maintenance/eski_urunleri_arsivle.py`), added 2026-07-28**
Business decision: rather than chase a long tail of legacy/low-value records, unresolved karışık variants, never-processed `temiz_urunler_olcu_duzenlenecek.xlsx` rows, stoksuz rows, and images whose filename never resolved to any DB product were moved (not deleted) to `data/reference/arsivlenen_eski_urunler.xlsx` and `images/arsiv/products/`. Re-running this script is idempotent — it scans `images/arsiv/products/` directly for its report rather than trusting the (post-move-empty) `Eslesmeyen_Gorseller` sheet.

**Search/export tooling (`scripts/database/`), added 2026-07-29**

```text
csv_guncelle.py         exports urunler/urun_gorselleri (from DB) + archived data (from the
                          xlsx above) to CSV under data/processed/ and data/reference/ — fast to
                          grep/search, regenerate whenever the DB changes
urun_ara.py <kod>        searches those CSVs for a stock code: active DB? has image? archived
                          (and why)? — run csv_guncelle.py first if stale
tablolari_disa_aktar.py  full Excel dump of current urunler/urun_gorselleri/kategoriler ->
                          reports/excel/veritabani_guncel_durum.xlsx (the actual 1:1 DB mirror;
                          data/processed/temiz_urunler_final_v2.xlsx is the pre-load *source*,
                          not guaranteed identical to live DB state after ad-hoc changes)
urun_katalogu_olustur.py builds data/processed/urun_katalogu_gorselli.xlsx: DB products that
                          have an image, with a thumbnail (120px, via Pillow) embedded per row —
                          a lightweight recreation of urun_listesi.xlsx's stok-kodu+photo layout

```

## UI / arayüz katmanı (Faz 5, başladı 2026-07-29)

`docker-compose.yml` artık Postgres'e ek olarak iki düşük-kod (low-code) arayüz servisi tanımlıyor — ürün arama, stok giriş-çıkış ve yönetici paneli ekranları için değerlendirilenler:

- **NocoDB terk edildi**: `NC_ALLOW_LOCAL_HOSTS=true` set edilmesine ve `veritabani:5432`'ye ham TCP bağlantısının çalıştığı doğrulanmasına rağmen ("Connection to internal hosts is not allowed") uygulama seviyesindeki SSRF koruması aşılamadı — kaynağı obfuscated/minified bulunduğundan pratik bir çözüm yolu bulunamadı. Servis compose dosyasında hâlâ duruyor ama kullanılmıyor; ayrıca bazı özellikleri ücretliydi.
- **Appsmith seçildi ve doğrulandı**: `veritabani` host adıyla Postgres'e sorunsuz bağlanıyor; sorgu + Table/Form/Chart/Input widget'larıyla gerçek ekranlar kurulabiliyor; "Deploy" edilince son kullanıcı sadece tasarlanmış ekranları görür, sorgu panelini hiç görmez. Self-hosted Community Edition (Apache 2.0, tamamen açık kaynak) kullanılıyor — fiyatlandırma sayfasındaki "5 kullanıcı" sınırı yalnızca Appsmith'in kendi barındırdığı bulut sürümü için geçerli, self-hosted CE'de kullanıcı sınırı yok. Business/Enterprise'ın eklediği özellikler (ince/özel roller, audit log, SSO, Git ile çoklu ortam, "Powered by Appsmith" ibaresinin kaldırılması) bu projenin ölçeğinde gerekli değil; rol ayrımı (örn. personel vs. yönetici) gerekirse **ayrı Appsmith uygulamaları + ayrı davetli kullanıcı listeleri** ile ücretsiz sürümde de çözülür. Query ayarlarındaki "Run query automatically" açıldığında, bağlı bir widget'ın (örn. arama kutusu) değeri her değiştiğinde sorgu otomatik yeniden çalışır (canlı arama için gerekli).
- **Planlanan barındırma (henüz taşınmadı)**: kullanıcının hâlihazırda ev sunucusu olarak çalışan 16GB RAM'li bir Raspberry Pi 5'i bu iş için ayırması planlanıyor. Postgres tarafı ARM64'te hiç sorun değil; Appsmith'in ARM uyumluluğu (MongoDB+Redis içeriyor, nispeten ağır) bu donanımda henüz test edilmedi — donanım kararı kesinleşmeden önce doğrudan denenip doğrulanmalı. microSD yerine NVMe SSD ve bir UPS önerildi (sürekli yazma yapan gömülü MongoDB + gerçek zamanlı depo verisi için).
- **Planlanan ağ mimarisi (henüz kurulmadı)**: birden fazla fiziksel lokasyon arasında Postgres/Appsmith portlarını genel internete hiç açmadan erişim için **Headscale** (self-hosted, Tailscale protokolüyle uyumlu kontrol sunucusu) + mobil/masaüstünde standart **Tailscale** istemcileri kullanılacak.
- **Planlanan yedekleme (henüz uygulanmadı)**: `pg_dump` (DB) + `images/final/products/` senkronizasyonunu (örn. restic/borgbackup ile) düzenli olarak farklı bir fiziksel lokasyona göndermek — "kendi bulutun" olarak, üçüncü parti bir servise bağımlı kalmadan.
- Appsmith mobil tarayıcıda responsive olarak çalışır (widget'lar için Canvas size mobil ayarlanabilir) ama native bir uygulama (App Store/Play Store paketi) üretmiyor — çevrimdışı mod yok, yukarıdaki Headscale ağına erişim şart.
- Görseller (`urun_gorselleri.dosya_adi`) şu an sadece dosya adı tutuyor, HTTP URL'i değil — Appsmith/başka bir arayüzde görsel göstermek için `images/final/products/` klasörünü ayrı bir statik dosya sunucusuyla (örn. nginx, Docker'a üçüncü servis olarak) yayınlamak gerekecek; henüz yapılmadı.

### Appsmith'in Git entegrasyonu (2026-07-29'da kuruldu)

Appsmith uygulamasının kendisi (sayfalar/sorgular/widget'lar) ayrı bir **GitHub reposuna** bağlandı: `https://github.com/Omer-Bera/depo-appsmith-arayuz` (private). Bu, `metaks_DB` (bu repo, veri pipeline'ı) ile **tamamen ayrı ve ilgisiz** bir repo — karıştırılmamalı. Yerelde `~/depo-appsmith-arayuz` altına klonlandı (bu proje klasörünün dışında, kardeş bir dizinde).

- **Appsmith tarafı (Editor'deki "Connect Git")**: kendi ürettiği bir deploy key ile bağlanıyor, repo Settings → Deploy keys altında "Allow write access" işaretli. Bu, kullanıcının kişisel GitHub SSH anahtarlarından tamamen bağımsız bir mekanizma.
- **Bu Mac'in git/Claude erişimi**: SSH yerine **GitHub CLI (`gh`)** ile HTTPS token tabanlı kimlik doğrulama kullanılıyor (`brew install gh` → `gh auth login` → `gh auth setup-git`) — önceki 1Password SSH agent sorununu (bkz. Git bölümü) tekrar yaşamamak için bilinçli tercih. `gh auth status` ile doğrulanabilir.
- **Datasource bilgisi git'e yazılmıyor** — güvenlik nedeniyle Appsmith gerçek Postgres host/şifre bilgisini export etmiyor, sadece `datasources/users.json` gibi isim/plugin referansı tutuyor. Gerçek bağlantı bilgisi Appsmith'in kendi backend'inde (Mongo) duruyor; herkes aynı canlı Appsmith sunucusuna (Mac'teki `depo-appsmith` container'ı) bağlandığı için bu sorun teşkil etmiyor.
- **Dosya yapısı**: `pages/<Sayfa>/Page1.json` (widget ağacı + layout), `pages/<Sayfa>/queries/<Sorgu>/<Sorgu>.txt` (ham SQL) + `metadata.json` (sorgu ayarları, SQL body'si burada da tekrar ediyor), `datasources/*.json`, `application.json`, `theme.json`.
- **Branch stratejisi**: `Master` (stabil/birleştirilmiş), `Ömer` / `Furkan` (her kişinin kendi manuel çalışma branch'i), `Ömer-Claude` / `Furkan-Claude` (Claude'un ilgili kişiyle eşleşerek doğrudan dosya düzenleyip commit/push attığı branch'ler). Branch protection şimdilik bilinçli olarak açılmadı (erken/hızlı deneme aşaması) — proje olgunlaşınca eklenebilir.
- İlk bağlantı için repo'nun **tamamen boş** (README/gitignore/license eklenmemiş) olması şarttı — Appsmith'in ilk push'u var olan commit'lerle çakışıyor.

## Legacy path gotcha (partially fixed)

The repo was reorganized into `data/`, `scripts/{cleaning,normalization,maintenance,database,images}/`, `images/`, `reports/` subfolders. **Newer scripts** (everything in Stage 3, the image-load/archive/search tooling, and `final_excel_hazirla.py`/`yukle.py`/`gorsel_eslesme_raporu.py` after 2026-07-28 fixes) correctly use `BASE_DIR = Path(__file__).resolve().parents[2]` and read/write real `data/`/`reports/`/`images/` paths. **Older Stage 1/2 scripts** (`scripts/cleaning/*.py`, `scripts/maintenance/kalip_yedekle.py`, `birlesik_stok_kodlarini_duzelt.py`, `ayni_urun_tekrarlarini_sil.py`, `secili_stok_tekrarlarini_sil.py`, `scripts/images/gorsel_esle_duzeltilmis_v2.py`, `gorsel_stok_kodlarini_guncelle.py`) still use bare filenames or script-adjacent `BASE_DIR` — but you shouldn't need to rerun them; their outputs already exist in `data/interim/`. If you ever do need to rerun one, check its path constants first.

## Database schema (`sql/01_schema.sql`)

- **Master data isolation**: `urunler` holds only immutable physical/identifying attributes. Manufacturing/production data is deliberately excluded.
- **Mold cavity count is out-of-scope for `urunler`** — kept in `data/reference/kalip_bilgileri_yedek.xlsx` pending a future `kaliplar` table (Faz 3, not started).
- **Parent/child/variant**: `urunler.urun_tipi` is `ANA_URUN` / `ALT_PARCA` / `VARYANT`, linked via self-referencing `parent_stok_kodu`.
- **Numeric measurements**: `olcu_mm`, `boy_ligne`, `gramaj_gr` are NUMERIC. Note `gramaj_gr` coverage is inherently partial — the source `ÜRÜN GRAMI` column is a literal `"?"` for roughly half the catalog (verified 2026-07-29 against both `data/raw/urun_listesi.xlsx` and a newer root-level copy — identical data, so there's no richer source hiding there). A separate/better weight source would be needed to fill the gap.
- **Images**: `urun_gorselleri`, FK to `urunler.stok_kodu`, partial unique index enforcing at most one active `ana_gorsel_mi` per product. Populated by `scripts/database/gorselleri_yukle.py`.
- **`stok_hareketleri`**: ledger table (islem_tipi includes `SAYIM_DEVRI` for physical inventory counts, `gecici_kod` field explicitly for temporary/unreconciled codes) — schema anticipates the Faz 4 warehouse-count workflow but no loader script exists yet. `lokasyonlar` is defined but empty (location tracking optional for `SAYIM_DEVRI` rows — only required for `TRANSFER`). **No column tracks which user performed a movement yet** — see "UI / arayüz katmanı" below for the planned fix, needed before any giriş/çıkış form is built.

## Repository layout

```text
data/{raw,interim,processed,reference}/  Excel/CSV at each pipeline stage
images/{working,final,arsiv}/products/   product images: working copy, active (DB-matched), archived (unmatched)
reports/excel/                           audit reports + DB export (veritabani_guncel_durum.xlsx)
scripts/{cleaning,normalization,maintenance,database,images}/  pipeline scripts, grouped by stage
sql/01_schema.sql                        current DB schema (mounted by docker-compose)
init_db.sql                              legacy schema, not used by docker-compose
docs/INFO.md                             Turkish project doc: current state, roadmap (Faz 2–6), file descriptions
docs/karisik_stok_kodu_kurali.md         the karışık-code decode rule, with validation evidence
archive/                                 superseded scripts/data/notebooks; not part of the active pipeline (gitignored)

```

## File protection

Load-bearing, never delete/bulk-modify without a backup: `data/raw/urun_listesi.xlsx` (~195 MB, embedded images — Excel re-saves can shift drawing anchors), `data/processed/temiz_urunler_final_v2.xlsx`, `data/reference/kalip_bilgileri_yedek.xlsx`, `images/final/products/`, `sql/01_schema.sql`, `scripts/database/yukle.py`. A root-level `urun_listesi.xlsx` duplicate sometimes appears (the user's live Excel working copy) — gitignored, leave it alone, don't assume it's identical to `data/raw/`'s copy without checking. Files named `~$*.xlsx` are Excel lock files — only delete once the corresponding Excel file is confirmed closed (check with `lsof`).
