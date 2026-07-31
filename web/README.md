# web — METAKS arayüzü

METAKS'ın Django + HTMX ile geliştirilen web arayüzü; `metaks` deposunun iki
dizininden biri (diğeri `veritabani/`). Ayrıntılı mimari bağlam ve kararlar için
buradaki `CLAUDE.md`'ye, deponun tamamı için kökteki `CLAUDE.md`'ye bakın.

## Kurulum

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # gerekirse değerleri düzenle
python manage.py migrate
python manage.py runserver
```

`veritabani/` dizinindeki Postgres ve görsel sunucu servislerinin ayakta olması gerekir:

```bash
cd ../veritabani && docker compose up -d
```
