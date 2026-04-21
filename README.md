
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

## Деплой

Файлы деплоя лежат в `deploy/`.

Первый запуск:

```bash
cp deploy/.env.example deploy/.env
cp deploy/sputnik.env.example deploy/sputnik.env
cd deploy
docker compose up -d
```

В `deploy/.env` задаются переменные самого compose (`SPUTNIK_IMAGE`, `DATA_LOCATION`), а в `deploy/sputnik.env` лежит окружение контейнеров Django/PostgreSQL.

## Наименование веток

- feat/ — новая функциональность
- fix/ — исправление бага
- chore/ — техработы, зависимости, конфиги
- refactor/ — рефакторинг без изменения поведения
- docs/ — документация
- test/ — тесты

Примеры:

```
feat/4-add-demo-app
fix/7-correct-password-reset
chore/9-add-pre-commit-hooks
refactor/15-split-settings-module
docs/22-update-readme
```
