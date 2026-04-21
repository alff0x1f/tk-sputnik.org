# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Django 5.2 website for a tourism club (турклуб). Python 3.14+, managed with `uv`.

## Setup

```bash
cp .env.example .env          # fill in DJANGO_SECRET_KEY and ALLOWED_HOSTS at minimum
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

The app loads `.env` automatically via `python-dotenv`. `DEBUG` defaults to `False` unless set to `1`, `true`, `yes`, or `on`.

## Common commands

```bash
uv run python manage.py runserver       # dev server at http://127.0.0.1:8000/
uv run python manage.py migrate
uv run python manage.py makemigrations
uv run pytest                           # run all tests
uv run pytest apps/demo/tests.py       # run a single test file
uv run ruff check .                     # lint
uv run ruff format .                    # format
```

## Testing

Use `pytest` (not `manage.py test`). `DJANGO_SETTINGS_MODULE` is set in `pyproject.toml` under `[tool.pytest.ini_options]`, so no extra env setup is needed. Write tests with `django.test.TestCase` and use `self.client` for HTTP assertions. Test files can be named `tests.py` or `test_*.py` — both are discovered.

## Architecture

- `config/` — Django project config (settings, urls, wsgi, asgi)
- `apps/` — all Django apps live here; currently only `apps.demo`
- New apps go in `apps/` and are registered in `INSTALLED_APPS` as `apps.<name>`
- Database: SQLite in development (`db.sqlite3`), PostgreSQL via `psycopg[binary]` in production
- Static files: standard Django `STATIC_URL`
- No custom authentication — uses Django's built-in auth

## Branch naming

`feat/`, `fix/`, `chore/`, `refactor/`, `docs/`, `test/` — followed by issue number and slug, e.g. `feat/4-add-demo-app`.
