# depo-web-arayuz

METAKS'ın Django + HTMX ile geliştirilen web arayüzü. Ayrıntılı mimari bağlam ve
kararlar için `CLAUDE.md`'ye bakın.

## Kurulum

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # gerekirse değerleri düzenle
python manage.py migrate
python manage.py runserver
```

`metaks_DB` reposundaki Postgres ve görsel sunucu servislerinin ayakta olması gerekir:

```bash
cd ../metaks_DB && docker compose up -d
```
