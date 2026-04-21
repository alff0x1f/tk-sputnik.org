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
