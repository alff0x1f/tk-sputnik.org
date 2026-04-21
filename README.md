
## Разработка

Требования:
- `uv`
- Python `3.14+`

Первый запуск:

```bash
cp .env.example .env
```

Заполните в `.env` как минимум `DJANGO_SECRET_KEY` и `ALLOWED_HOSTS`, а также при необходимости включите `DEBUG=True`.

Установите зависимости:

```bash
uv sync
```

Экспортируйте переменные окружения из `.env`:

```bash
set -a
source .env
set +a
```

Примените миграции:

```bash
uv run python manage.py migrate
```

Запустите локальный сервер разработки:

```bash
uv run python manage.py runserver
```

Приложение будет доступно по адресу `http://127.0.0.1:8000/`.
