# Plan: Add CI/deployment files from scratch/

## Context
The scratch/ directory contains deployment files borrowed from the kolco24 project. They need to be adapted and added to this project (tk-sputnik.org Django app). Key differences: this project uses `uv` (not pip/requirements.txt), Python 3.14, `config.wsgi:application` (not `kolco24.wsgi`), and has no custom management commands (backup_db, runmailer, vtb_checker).

## Files to create

### 1. `Dockerfile`
Adapted from `scratch/Dockerfile`:
- Base image: `python:3.14-slim`
- Install uv via `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`
- Remove `ru-trust-bundle.pem` and Russian CA cert block (not needed here)
- Keep `ca-certificates` and `postgresql-client` apt packages
- Replace `pip install -r requirements.txt` with `uv sync --frozen --no-dev`
- Fix WSGI: `config.wsgi:application`
- collectstatic via `uv run python manage.py collectstatic --noinput`

```dockerfile
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN DJANGO_SECRET_KEY=build uv run python manage.py collectstatic --noinput

CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application", "--access-logfile", "-", "--log-level", "info"]
```

### 2. `docker-compose.yml`
Adapted from `scratch/docker-compose.yml`:
- Rename all `kolco24_*` → `sputnik_*` (services, containers, networks)
- Rename `KOLCO24_IMAGE` → `SPUTNIK_IMAGE`
- Update env_file: `./deploy/kolco24.env` → `./deploy/sputnik.env`
- Fix gunicorn WSGI: `config.wsgi:application`
- Remove project-specific services: `sputnik_backup`, `sputnik_runmailer`, `sputnik_vtb_checker`
- Keep: `sputnik_migrate`, `sputnik_web`, `sputnik_nginx`, `sputnik_db`
- Static dir: `/app/staticfiles` (matches STATIC_ROOT to be added in settings.py)

### 3. `Makefile`
Adapted from `scratch/Makefile`:
- Change `IMAGE ?= kolco24` → `IMAGE ?= sputnik`
- Update docker compose file reference: `docker-compose.yml` (no `_v2` suffix)
- Remove `backup` and `restore` targets (no backup_db command in this project)

### 4. `deploy/sputnik.env.example`
Adapted from `scratch/deploy/kolco24.env.example`:
- Strip kolco24-specific vars: email, payment (Yandex, Sberbank, SBP, VTB), Google Docs, Backup
- Keep: Django (SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS) + DB (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, POSTGRES_*)
- Update example hosts to `tk-sputnik.org`

### 5. `deploy/nginx.conf`
Copy from `scratch/deploy/nginx.conf` with one change:
- Update upstream name: `kolco24_django` → `sputnik_django`

## Settings change required

`config/settings.py` — switch to PostgreSQL (always) and add STATIC_ROOT:

```python
# Replace existing DATABASES block:
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "sputnik"),
        "USER": os.getenv("DB_USER", "sputnik"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# Add after STATIC_URL:
STATIC_ROOT = BASE_DIR / "staticfiles"
```

Also update `.env.example` to include DB vars for local dev (pointing to localhost).

## Verification
1. `docker build .` — image builds successfully
2. `uv run pytest` — existing tests still pass
3. `uv run ruff check .` — no lint errors
