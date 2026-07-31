# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in the **`veritabani/`** directory. The repository root has its own `CLAUDE.md` covering the whole repo; the Django UI lives in `web/` and has its own.

**Merged 2026-07-31.** This directory used to be a standalone repo (`Omer-Bera/metaks_DB`, cloned at `~/metaks_DB`) alongside `depo-web-arayuz`; the two were combined into `Omer-Bera/metaks` with full history preserved. Everywhere below, "this repo" means this directory — paths like `sql/01_schema.sql` are still correct relative to it, but from the repo root they read `veritabani/sql/01_schema.sql`. Rationale for the merge and the repo-wide rules are in the root `CLAUDE.md`.

## Project overview

METAKS DB is a data-engineering project (not a running application) that cleans, standardizes, and migrates a metal/textile hardware catalog (rivets, buckles, buttons, etc. — "toka", "düğme", "kalıp") from a messy source Excel export into a PostgreSQL database, and links the catalog's embedded product images to stock codes. All code, data, and console output are in Turkish. Current point-in-time state (row counts, coverage stats) lives in `docs/INFO.md`, not here — check that file for "what does the DB currently contain," this file is about how the pipeline works.

## Environment & commands

- Python venv lives in `venv/` — **separate from `web/venv/`**, don't mix them. Activate with `source venv/bin/activate`. `requirements.txt` was added 2026-07-31 (captured from the then-current venv when the repos merged, since a venv can't be moved — absolute paths are baked into its shebangs); recreate with `python3 -m venv venv && venv/bin/pip install -r requirements.txt`. Key packages: `pandas`, `openpyxl`, `psycopg2-binary`, `Pillow` (for thumbnail generation), `SQLAlchemy`.
- Start everything: `docker compose up -d` — brings up three services: `veritabani` (Postgres 16, container `depo-postgres`), `appsmith` (container `depo-appsmith`, port 8082 — the active low-code UI layer), `gorsel-sunucu` (nginx, container `depo-gorsel-sunucu`, port 8083 — serves product images). Stop: `docker compose down`. A fourth service, `nocodb`, was evaluated then abandoned and removed from compose 2026-07-30 (see "UI / arayüz katmanı" below). **Run compose from this directory** — and note the file pins `name: metaks_db` at the top: Compose otherwise derives the project name (and therefore the `pg_data`/`appsmith_data` volume prefixes) from the containing directory's name, so the 2026-07-31 move from `~/metaks_DB` to `~/metaks/veritabani` would have made it open a brand-new **empty** volume instead of the existing `metaks_db_pg_data`. Do not remove that line, and do not rename it — the live database is stored under that prefix.
- The compose file mounts **`sql/01_schema.sql`** as the init script — that file is the authoritative, current schema. The root-level `init_db.sql` is an older/simpler version, not wired into docker-compose; legacy.
- DB connection used by all scripts: `host=localhost port=5433 dbname=depo_sistemi user=depo_admin password=supergizlisifre` (credentials hardcoded per-script).
- Connect manually: `docker exec -it depo-postgres psql -U depo_admin -d depo_sistemi`.
- No test suite, linter, or build step — this is a manually-run, step-by-step batch pipeline.
- **Git**: initialized 2026-07-28, local repo-scoped `user.name`/`user.email` (not global). Remote added 2026-07-29: `https://github.com/Omer-Bera/metaks_DB` (private) — **superseded 2026-07-31**: the repo is now `https://github.com/Omer-Bera/metaks` (private) with this tree under `veritabani/`; the old remote is archived, not deleted. **Branch model simplified 2026-07-29** (and carried over to the merged repo unchanged): after starting with a 5-branch per-person scheme (mirrored in both this repo and `depo-appsmith-arayuz`), the user's sibling (Furkan) stopped actively working on the project — it's now a single-session (Ömer + Claude) workflow, so the branch scheme was collapsed to exactly three, identical in both repos: `master` (approved/stable — only fast-forwarded on explicit user approval), `dev` (Claude's active working branch, commit here), `review` (a deliberately one-checkpoint-behind branch the user reviews — promoted to `dev`'s HEAD only when starting the *next* unit of work, so the user always has something settled to look at rather than a moving target). The old `Ömer`/`Furkan`/`Ömer-Claude`/`Furkan-Claude` branches were deleted (locally and on the remote) in both repos once their content was consolidated. No branch protection on any of the three (early/fast phase, same rationale as before).
- **Commit signing**: global git config uses SSH commit signing (`gpg.format=ssh`) via 1Password's SSH agent. This previously failed ("No SSH private key found") because `user.signingkey` pointed at an orphaned key that existed in neither 1Password nor on disk — root-caused 2026-07-29 (not a sandbox/agent restriction; 1Password's agent responds normally to Claude Code's shell). Fixed by generating a real key in 1Password ("GitHub SSH Key"), registering its public half on GitHub as a **signing key**, and updating `user.signingkey` to match — commits now sign and show as GitHub-verified. If signing ever breaks again, verify with: `SSH_AUTH_SOCK="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock" ssh-add -l` and compare fingerprints against `git config --global --get user.signingkey`; ask the user before falling back to `git commit --no-gpg-sign`. **Second, distinct failure mode seen 2026-07-30** — `git commit` fails with `error: 1Password: failed to fill whole buffer` *while the fingerprints match fine*: that is not a key problem, it's 1Password waiting on an unanswered **authorization prompt**. Listing keys needs no approval but signing does, so `ssh-add -l` looks healthy and misleads you. Isolate it with `ssh-keygen -Y sign -f <(git config --global --get user.signingkey) -n git <somefile>` — if that hangs until timeout (exit 124) rather than erroring, it's the approval prompt. Fix is on the user's side (unlock 1Password / approve the prompt / relax that key's approval setting), then just retry the same commit. Also note `git log --show-signature` reports `%G? = N` locally regardless, because `gpg.ssh.allowedSignersFile` is not configured — that is a local *verification* gap, not proof the commit is unsigned; check with `git cat-file commit HEAD | grep "BEGIN SSH SIGNATURE"`.
- Git operations against GitHub use **`gh` (GitHub CLI) with HTTPS token auth**, not raw SSH — `gh auth status` to check. Installed/authenticated 2026-07-29 specifically to sidestep the 1Password-agent-reachability question for git push/clone (separate from the signing key issue above, which did resolve).

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

- **NocoDB terk edildi**: `NC_ALLOW_LOCAL_HOSTS=true` set edilmesine ve `veritabani:5432`'ye ham TCP bağlantısının çalıştığı doğrulanmasına rağmen ("Connection to internal hosts is not allowed") uygulama seviyesindeki SSRF koruması aşılamadı — kaynağı obfuscated/minified bulunduğundan pratik bir çözüm yolu bulunamadı; ayrıca bazı özellikleri ücretliydi. Servis ve `nc_data` volume'ü **2026-07-30'da `docker-compose.yml`'den tamamen kaldırıldı** (deneme sırasında hiç gerçek veri taşımadığı için kayıp riski yoktu) — bir daha denenecekse compose dosyasına yeniden eklenmesi gerekir.
- **Appsmith seçildi ve doğrulandı**: `veritabani` host adıyla Postgres'e sorunsuz bağlanıyor; sorgu + Table/Form/Chart/Input widget'larıyla gerçek ekranlar kurulabiliyor; "Deploy" edilince son kullanıcı sadece tasarlanmış ekranları görür, sorgu panelini hiç görmez. Self-hosted Community Edition (Apache 2.0, tamamen açık kaynak) kullanılıyor — fiyatlandırma sayfasındaki "5 kullanıcı" sınırı yalnızca Appsmith'in kendi barındırdığı bulut sürümü için geçerli, self-hosted CE'de kullanıcı sınırı yok. Business/Enterprise'ın eklediği özellikler (ince/özel roller, audit log, SSO, Git ile çoklu ortam, "Powered by Appsmith" ibaresinin kaldırılması) bu projenin ölçeğinde gerekli değil; rol ayrımı (örn. personel vs. yönetici) gerekirse **ayrı Appsmith uygulamaları + ayrı davetli kullanıcı listeleri** ile ücretsiz sürümde de çözülür. Query ayarlarındaki "Run query automatically" açıldığında, bağlı bir widget'ın (örn. arama kutusu) değeri her değiştiğinde sorgu otomatik yeniden çalışır (canlı arama için gerekli).
- **Planlanan barındırma (henüz taşınmadı)**: kullanıcının hâlihazırda ev sunucusu olarak çalışan 16GB RAM'li bir Raspberry Pi 5'i bu iş için ayırması planlanıyor. Postgres tarafı ARM64'te hiç sorun değil; Appsmith'in ARM uyumluluğu (MongoDB+Redis içeriyor, nispeten ağır) bu donanımda henüz test edilmedi — donanım kararı kesinleşmeden önce doğrudan denenip doğrulanmalı. microSD yerine NVMe SSD ve bir UPS önerildi (sürekli yazma yapan gömülü MongoDB + gerçek zamanlı depo verisi için).
- **Planlanan ağ mimarisi (henüz kurulmadı)**: birden fazla fiziksel lokasyon arasında Postgres/Appsmith portlarını genel internete hiç açmadan erişim için **Headscale** (self-hosted, Tailscale protokolüyle uyumlu kontrol sunucusu) + mobil/masaüstünde standart **Tailscale** istemcileri kullanılacak.
- **Yedekleme — ✅ yerel kısmı kuruldu (2026-07-30)**: `scripts/maintenance/yedek_al.sh` — `pg_dump -Fc` ile DB'yi tarih damgalı dosyaya yedekler (14 günden eski dump'ları otomatik siler) ve `images/final/products/`'ı rsync ile aynalar (kaynağı asla silmez). Varsayılan hedef `backups/` (repo kökünde, gitignored) — `BACKUP_DEST` ortam değişkeniyle harici bir diske/NAS'a yönlendirilebilir. Henüz otomatik zamanlanmıyor (cron/launchd ile tetiklenmesi ve gerçek bir ikinci fiziksel lokasyona (örn. restic/borgbackup ile) gönderilmesi kullanıcı kararına bırakıldı — "kendi bulutun" hedefi bu ikinci adımla tamamlanır.
- Appsmith mobil tarayıcıda responsive olarak çalışır (widget'lar için Canvas size mobil ayarlanabilir) ama native bir uygulama (App Store/Play Store paketi) üretmiyor — çevrimdışı mod yok, yukarıdaki Headscale ağına erişim şart.
- **Görsel sunucusu: ✅ kuruldu 2026-07-29**. `urun_gorselleri.dosya_adi` hâlâ sadece dosya adı tutuyor (HTTP URL değil), ama artık `docker-compose.yml`'deki `gorsel-sunucu` servisi (nginx:alpine, container `depo-gorsel-sunucu`, port 8083) `images/final/products/`'ı salt-okunur olarak `http://<host>:8083/urun-gorselleri/<dosya_adi>` altında yayınlıyor — config `docker/nginx/gorseller.conf`. Path traversal (400) ve dizin listeleme (403, `autoindex off`) test edildi, engelleniyor. Appsmith `StokIslemi.UrunGorseli` widget'ı Tailscale adresi üzerinden (`http://100.64.0.6:8083/...`, `APPSMITH_BASE_URL` ile aynı desen) buna bağlandı.

### Appsmith'in Git entegrasyonu (2026-07-29'da kuruldu)

Appsmith uygulamasının kendisi (sayfalar/sorgular/widget'lar) ayrı bir **GitHub reposuna** bağlandı: `https://github.com/Omer-Bera/depo-appsmith-arayuz` (private). Bu, `metaks_DB` (bu repo, veri pipeline'ı) ile **tamamen ayrı ve ilgisiz** bir repo — karıştırılmamalı. Yerelde `~/depo-appsmith-arayuz` altına klonlandı (bu proje klasörünün dışında, kardeş bir dizinde).

- **Appsmith tarafı (Editor'deki "Connect Git")**: kendi ürettiği bir deploy key ile bağlanıyor, repo Settings → Deploy keys altında "Allow write access" işaretli. Bu, kullanıcının kişisel GitHub SSH anahtarlarından tamamen bağımsız bir mekanizma.
- **Bu Mac'in git/Claude erişimi**: SSH yerine **GitHub CLI (`gh`)** ile HTTPS token tabanlı kimlik doğrulama kullanılıyor (`brew install gh` → `gh auth login` → `gh auth setup-git`) — önceki 1Password SSH agent sorununu (bkz. Git bölümü) tekrar yaşamamak için bilinçli tercih. `gh auth status` ile doğrulanabilir.
- **Datasource bilgisi git'e yazılmıyor** — güvenlik nedeniyle Appsmith gerçek Postgres host/şifre bilgisini export etmiyor, sadece `datasources/users.json` gibi isim/plugin referansı tutuyor. Gerçek bağlantı bilgisi Appsmith'in kendi backend'inde (Mongo) duruyor; herkes aynı canlı Appsmith sunucusuna (Mac'teki `depo-appsmith` container'ı) bağlandığı için bu sorun teşkil etmiyor.
- **Dosya yapısı — iki farklı biçim gözlemlendi**: (1) `pages/Page1/Page1.json` gibi tek dosyalı sayfalarda widget ağacı `unpublishedPage.layouts[0].dsl.children` içinde iç içe gömülü. (2) `pages/StokIslemi/` gibi çok-widget'lı sayfalarda Appsmith widget'ları ayrı dosyalara bölüyor (`pages/<Sayfa>/widgets/<WidgetAdı>.json`, her biri kendi `parentId`'siyle üstündeki container'a işaret ediyor) — **önemli bulgu (2026-07-29, canlı editörde doğrulandı)**: bu durumda sayfanın ana `dsl` nesnesinde (`StokIslemi.json`) hiçbir `children` dizisi YOK ve olması da gerekmiyor; Appsmith sunucusu widget ağacını `widgets/` klasörünü tarayıp her dosyanın `parentId`'sinden kendisi kuruyor. İlk bakışta bu "eksik/bozuk" gibi görünüp yanlış bir "düzeltme" (children dizisi ekleme) dürtüsü yaratabilir — yapmayın, gerçekten gerekmiyor, StokIslemi sayfası bu haliyle editörde widget'ların tamamını doğru gösteriyor.
- Ayrıca: `pages/<Sayfa>/queries/<Sorgu>/<Sorgu>.txt` (ham SQL) + `metadata.json` (sorgu ayarları, SQL body'si burada da tekrar ediyor), `datasources/*.json`, `application.json`, `theme.json`.
- **StokIslemi sayfası** (Furkan tarafından oluşturuldu, 2026-07-29): Stok İşlemi (giriş/çıkış/transfer/sayım) formu iskeleti — `UrunAraInput`, `UrunSonuclariTable`, `UrunGorseli`, `UrunDetayText`, `LokasyonSelect`, `IslemTipiSelect`, `MiktarInput`, `AciklamaInput`, `KaydetButton`, `GuncelStokTable`, `SonHareketlerTable`. Hiçbir sorgu bağlanmadı henüz (tablolar boş, etiketlerinde "veri sözleşmesi sonrası bağlanacak" notu var) — bağlanacak sorgu sözleşmesi bu repodaki `docs/aktif-urun-veri-sozlesmesi.md`'de tanımlı (`stok_hareketi_kaydet()` fonksiyonu, `v_aktif_urunler` view'ı). `KaydetButton`, `stok_hareketleri`'ne asla doğrudan INSERT atmamalı, sadece o fonksiyonu çağırmalı.
- **Branch stratejisi (2026-07-29'da sadeleştirildi)**: Furkan projeye artık aktif katılmıyor, tek-oturumlu (Ömer + Claude) bir akışa geçildi. Üç branch, `metaks_DB` ile birebir aynı model: `master` (onaylanmış/stabil), `dev` (Claude'un aktif çalıştığı uç), `review` (kullanıcının baktığı, bilerek bir kontrol noktası geride tutulan branch — Claude yeni bir işe başlarken `review`'u `dev`'in bir önceki durağına yükseltir). Eski `Ömer`/`Furkan`/`Ömer-Claude`/`Furkan-Claude` branch'leri (hem yerel hem remote) silindi. Branch protection yok (erken/hızlı deneme aşaması).
- İlk bağlantı için repo'nun **tamamen boş** (README/gitignore/license eklenmemiş) olması şarttı — Appsmith'in ilk push'u var olan commit'lerle çakışıyor.

## Legacy path gotcha (partially fixed)

The repo was reorganized into `data/`, `scripts/{cleaning,normalization,maintenance,database,images}/`, `images/`, `reports/` subfolders. **Newer scripts** (everything in Stage 3, the image-load/archive/search tooling, and `final_excel_hazirla.py`/`yukle.py`/`gorsel_eslesme_raporu.py` after 2026-07-28 fixes) correctly use `BASE_DIR = Path(__file__).resolve().parents[2]` and read/write real `data/`/`reports/`/`images/` paths. **Older Stage 1/2 scripts** (`scripts/cleaning/*.py`, `scripts/maintenance/kalip_yedekle.py`, `birlesik_stok_kodlarini_duzelt.py`, `ayni_urun_tekrarlarini_sil.py`, `secili_stok_tekrarlarini_sil.py`, `scripts/images/gorsel_esle_duzeltilmis_v2.py`, `gorsel_stok_kodlarini_guncelle.py`) still use bare filenames or script-adjacent `BASE_DIR` — but you shouldn't need to rerun them; their outputs already exist in `data/interim/`. If you ever do need to rerun one, check its path constants first.

## Database schema (`sql/01_schema.sql`)

- **Master data isolation**: `urunler` holds only immutable physical/identifying attributes. Manufacturing/production data is deliberately excluded.
- **Mold cavity count is out-of-scope for `urunler`** — kept in `data/reference/kalip_bilgileri_yedek.xlsx` pending a future `kaliplar` table (Faz 3, not started).
- **Parent/child/variant**: `urunler.urun_tipi` is `ANA_URUN` / `ALT_PARCA` / `VARYANT`, linked via self-referencing `parent_stok_kodu`.
- **Numeric measurements**: `olcu_mm`, `boy_ligne`, `gramaj_gr` are NUMERIC. Note `gramaj_gr` coverage is inherently partial — the source `ÜRÜN GRAMI` column is a literal `"?"` for roughly half the catalog (verified 2026-07-29 against both `data/raw/urun_listesi.xlsx` and a newer root-level copy — identical data, so there's no richer source hiding there). A separate/better weight source would be needed to fill the gap.
- **Images**: `urun_gorselleri`, FK to `urunler.stok_kodu`, partial unique index enforcing at most one active `ana_gorsel_mi` per product. Populated by `scripts/database/gorselleri_yukle.py`.
- **`stok_hareketleri`**: ledger table (islem_tipi includes `SAYIM_DEVRI` for physical inventory counts, `gecici_kod` field explicitly for temporary/unreconciled codes) — schema anticipates the Faz 4 warehouse-count workflow but no loader script exists yet. **The ledger is empty as of 2026-07-31** — migration 006 (below) deleted all 30 rows, every one a test entry, and restarted the sequence at 1; the in-progress warehouse count is still tracked in Excel, not here, so `v_toplam_stok`/`v_lokasyon_stok_ozet` return zero rows and every product reads "Sayılmadı" in Django. `lokasyonlar` holds exactly **three** rows, all confirmed real by the user 2026-07-31: `Metaks`/`Fabrika` (DAHILI), `Skor` (FASON). The other five (`Ana Depo`, `Sevkiyat Alanı`, `Fason Atölye 1`, `Depo 1`, `Kaplama`) never physically existed and were **hard-deleted** from Django's `/yonetim/lokasyonlar/` screen once the emptied ledger stopped pinning them via `ON DELETE RESTRICT`. Soft-deactivation (the earlier answer, `aktif_mi = false`) could not fix them: a row that was never real still sits in the management list forever. New locations are created from that same screen when needed.
- **`stok_hareketleri.yapan_kullanici`**: ✅ **applied to the live shared DB 2026-07-29** (`sql/migrations/003_stok_hareketi_fonksiyonu.sql`, NOT NULL, no default — safe because the table had 0 rows at apply time). Every insert must go through `stok_hareketi_kaydet()`, which takes it as a required parameter sourced from Appsmith's `{{ appsmith.user.email }}`, since all Appsmith traffic shares one Postgres role and `current_user` can't distinguish end users.
- **`urunler.katalog_durumu`**: ✅ **applied to the live shared DB 2026-07-29** (`sql/migrations/001_katalog_durumu.sql`). Three values: `AKTIF` (has a verified — Pillow-checked, filename-matched — primary image; 1780 rows), `PASIF` (no such image; 1193 rows), `INCELEME_BEKLIYOR` (schema supports it, currently 0 rows — no automatic "ambiguous" bucket exists in the cleaned data). Kept in sync with the pre-existing `aktif_mi` boolean via a CHECK constraint (`aktif_mi = TRUE` iff `katalog_durumu = 'AKTIF'`). **`v_aktif_urunler` view is live** — the one query surface Appsmith's catalog/search pages should read from (joins kategori/hammadde/kaplama/ana görsel, exposes a combined `arama_metni` search column). Full spec, field names, and example queries: `docs/aktif-urun-veri-sozlesmesi.md`.
- **Numune (sample) locations — ✅ applied to the live shared DB 2026-07-30**: `sql/migrations/004_numune_lokasyonlari.sql`. Samples are NOT a separate entity — they ride on `lokasyonlar` + `stok_hareketleri` (a sample is one unit of the product sitting somewhere; "moved to the sample cabinet" is literally a TRANSFER, so borrow/return history comes free). `lokasyonlar.tip` now allows `NUMUNE`; `ust_lokasyon_id` + `kod` add a **deliberately 2-level** hierarchy (cabinet → shelf, e.g. `N1` / `N1-R3`), enforced structurally via `kok_mu`/`ust_kok_mu` generated columns + a composite FK (no triggers). `uq_lokasyonlar_ad_tip` was replaced by `(COALESCE(ust_lokasyon_id,-1), lokasyon_adi, tip)` — the old one blocked "Raf 3" existing under two different cabinets. New views: `v_lokasyonlar_detay` (**the** dropdown source — `tam_ad`, `yaprak_mi`), `v_fiziksel_stok`, `v_numune_konumlari`. `stok_hareketi_kaydet()` now rejects non-leaf locations (signature unchanged). **`v_toplam_stok` changed meaning: it is now SELLABLE stock (excludes `NUMUNE`)** — safe because all four Appsmith consumers already used it that way and the change was proven to be a 0-row no-op at apply time; `v_fiziksel_stok` is the physical total. **No NUMUNE location rows exist yet** — deliberately: they must not be created until both UIs' location dropdowns filter on `yaprak_mi` (Appsmith `StokIslemi/LokasyonlariGetir` + `LokasyonYonetimi/LokasyonlarListele`; Django `katalog/views.py:651` and `:431`), or the in-progress warehouse count's location picker floods. Do NOT filter samples out by `tip` — someone counting 3 samples in a cabinet must be able to select that shelf. Full contract: `docs/aktif-urun-veri-sozlesmesi.md`.
- **`urun_kaydet()` — ✅ applied to the live shared DB 2026-07-30**: `sql/migrations/005_urun_kaydet_fonksiyonu.sql`. The only sanctioned way to add/edit `urunler` rows, same pattern as `stok_hareketi_kaydet()` (business rules in one place, Turkish `RAISE EXCEPTION` shown straight to users, both UIs share it). Needed because a bare `INSERT INTO urunler (stok_kodu) VALUES (...)` **fails outright** — `aktif_mi` DEFAULT TRUE contradicted `katalog_durumu` DEFAULT `'PASIF'` under `chk_urunler_katalog_durumu_aktif_mi_tutarli`; 005 fixes that default to FALSE so a bare insert yields a valid PASİF draft. Nothing else manages `katalog_durumu` (there are still zero user triggers in this DB). Takes a required `p_mod` (`'EKLE'`/`'GUNCELLE'`) — no silent upsert, so a mistyped stock code can't overwrite an existing product; `GUNCELLE` is **full-replace** semantics (NULL means clear, not "leave alone"). A product goes AKTİF iff a main image is supplied — categories/measurements deliberately NOT required, since 31 of the 1780 existing AKTİF products have no category and 65 no measurement. Also adds `urun_sonraki_gorsel_sirasi()` and audit columns `olusturan_kullanici`/`guncelleyen_kullanici` (NULL for the legacy 2973 rows — we genuinely don't know who created them). Note `ana_gorsel_mi` is now the authoritative "primary image" flag; `sira_no` is only ordering/filename suffix.
- **Stock-quantity views/function — ✅ applied to the live shared DB 2026-07-29**: `sql/migrations/002_lokasyon_stok_view.sql` (`v_lokasyon_stok_ozet`, `v_toplam_stok` — see 004 above, both were later extended/redefined) and `003_stok_hareketi_fonksiyonu.sql` (`stok_hareketi_kaydet()` — the only sanctioned way to write to `stok_hareketleri`; enforces sufficient-stock checks, required `yapan_kullanici`, per-`islem_tipi` location requirements, and idempotency via a client-generated `istemci_islem_kimligi` UUID). Both were syntax/logic-tested against the live schema inside a `BEGIN...ROLLBACK` before being written, then applied for real in order (002 before 003, since 003's function queries `v_lokasyon_stok_ozet`) and verified post-apply with `\d stok_hareketleri` / `\df stok_hareketi_kaydet`. Do the same test-then-verify pattern before proposing further changes to them — ask the user before applying.
- **Ledger test-row cleanup — ✅ applied to the live shared DB 2026-07-31**: `sql/migrations/006_test_hareketlerini_temizle.sql`. Deleted **all 30 rows** of `stok_hareketleri` — every one was a test entry (29 Jul Appsmith trials: each GİRİŞ followed by a matching ÇIKIŞ, round numbers; 30 Jul Django end-to-end verification, identifiable from `aciklama`). No real business data was in the ledger: the in-progress warehouse count lives in Excel, not the DB. Trigger for doing it now was **location deletion** — both `stok_hareketleri` FKs are `ON DELETE RESTRICT`, so those test rows were pinning five locations the user says never existed (Ana Depo, Sevkiyat Alanı, Fason Atölye 1, Depo 1, Kaplama); all five were removed afterwards from Django's location screen, leaving the three real ones (Metaks, Fabrika, Skor). The migration opens with a `DO` block that aborts unless the ledger holds exactly 30 rows, so it refuses to run if real data has since been entered; it also `RESTART`s the sequence so the first real movement gets id 1. Rollback restores all 30 rows with their original `hareket_id` and `istemci_islem_kimligi` — and was **proven before applying** (apply → rollback → row checksum identical). Deleting ledger rows is otherwise not a thing the applications can do: append-only stands, a numbered migration is the only door.
- **`sql/migrations/` convention**: numbered files (`00N_description.sql` + matching `00N_description_rollback.sql`), each wrapped in `BEGIN`/`COMMIT`. Order inside a migration matters — a real bug was caught here 2026-07-29: a CHECK constraint was originally added *before* the backfill `UPDATE`s that would satisfy it, which fails immediately (caught safely by the transaction wrapper, nothing reached the live DB, but the fix — reordering: add column → backfill → add constraint — is the pattern to follow for any future column-plus-constraint migration).

## Repository layout

```text
data/{raw,interim,processed,reference}/  Excel/CSV at each pipeline stage
images/{working,final,arsiv}/products/   product images: working copy, active (DB-matched), archived (unmatched)
reports/excel/                           audit reports + DB export (veritabani_guncel_durum.xlsx)
scripts/{cleaning,normalization,maintenance,database,images}/  pipeline scripts, grouped by stage
sql/01_schema.sql                        current DB schema (mounted by docker-compose)
sql/migrations/                          numbered migrations + rollbacks, applied manually (not by docker-compose)
init_db.sql                              legacy schema, not used by docker-compose
docs/INFO.md                             Turkish project doc: current state, roadmap (Faz 2–6), file descriptions
docs/karisik_stok_kodu_kurali.md         the karışık-code decode rule, with validation evidence
docs/aktif-urun-veri-sozlesmesi.md       active/passive product criteria, view/function contract for Appsmith
archive/                                 superseded scripts/data/notebooks; not part of the active pipeline (gitignored)

```

## File protection

Load-bearing, never delete/bulk-modify without a backup: `data/raw/urun_listesi.xlsx` (~195 MB, embedded images — Excel re-saves can shift drawing anchors), `data/processed/temiz_urunler_final_v2.xlsx`, `data/reference/kalip_bilgileri_yedek.xlsx`, `images/final/products/`, `sql/01_schema.sql`, `scripts/database/yukle.py`. A root-level `urun_listesi.xlsx` duplicate sometimes appears (the user's live Excel working copy) — gitignored, leave it alone, don't assume it's identical to `data/raw/`'s copy without checking. Files named `~$*.xlsx` are Excel lock files — only delete once the corresponding Excel file is confirmed closed (check with `lsof`).
