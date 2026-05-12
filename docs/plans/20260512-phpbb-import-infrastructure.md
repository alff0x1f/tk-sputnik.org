# phpBB Import Infrastructure

## Overview

Подготовить инфраструктуру для поэтапного импорта данных старого phpBB-форума (2007–2014) в Django.
Это **шаг 1** из нескольких: только инфраструктура, без моделей форума и команд импорта.

Проблема: дамп форума (mysqldump + файлы) хранится отдельно и рискует потеряться; данные нужны
для последующего создания живого Django-форума.

Что будет сделано: MySQL-сервис в Docker Compose, второе подключение БД в Django (`phpbb`),
приложение-скелет `forum_import` для будущих management-команд.

## Context (from discovery)

- `docker-compose.yml` — уже есть, содержит `db` (postgres:15) и `web`; добавляем `phpbb_db`
- `config/settings.py` — `DATABASES` только с `default` (PostgreSQL); добавляем `phpbb`
- `config/__init__.py` — пустой; нужен для `pymysql.install_as_MySQLdb()`
- `pyproject.toml` — зависимости проекта; добавляем `pymysql`
- `.env.example` — образец конфига; добавляем MySQL-переменные
- `apps/` — приложения проекта (`demo`, `contributors`, `accounts`); создаём `forum_import`

## Development Approach

- **testing approach**: Regular (код, затем тесты)
- Каждый таск завершается полностью до перехода к следующему
- Тесты обязательны для каждого таска с изменением кода
- Все тесты должны проходить перед переходом к следующему таску
- `uv run pytest` — команда для запуска тестов

## Testing Strategy

- **unit tests**: проверка настроек и импортируемости нового приложения
- Тесты не требуют запущенного MySQL — проверяем только конфигурацию

## Progress Tracking

- завершённые пункты помечать `[x]` сразу
- новые задачи добавлять с префиксом ➕
- блокеры — с префиксом ⚠️

## Solution Overview

1. `phpbb_db` (MySQL 5.7) добавляется в `docker-compose.yml` с `profiles: [phpbb]` — поднимается
   только явно, не мешает основному стеку
2. `PyMySQL` устанавливается как замена `MySQLdb` через `pymysql.install_as_MySQLdb()` в
   `config/__init__.py` — чистый Python, не требует системных C-библиотек
3. `DATABASES['phpbb']` в settings.py — Django может читать phpBB-таблицы напрямую через ORM
   или raw SQL в management-командах
4. `apps/forum_import` — пустой скелет приложения, зарегистрированный в `INSTALLED_APPS`;
   management-команды будут добавлены в следующих шагах

## Technical Details

**Новые env-переменные:**
- `MYSQL_DATABASE` (default: `phpbb`)
- `MYSQL_USER` (default: `phpbb`)
- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_HOST` (default: `127.0.0.1`)
- `MYSQL_PORT` (default: `3306`)

**Подключение phpbb_db:**
```
docker compose --profile phpbb up -d phpbb_db
docker compose exec phpbb_db mysql -u phpbb -p phpbb < /path/to/forum_dump.sql
```

**PyMySQL и Django:** `pymysql.install_as_MySQLdb()` вызывается в `config/__init__.py`;
Django видит его как `MySQLdb` и использует `django.db.backends.mysql` без изменений.

## What Goes Where

- **Implementation Steps** — изменения в коде, тесты
- **Post-Completion** — загрузка дампа, ручная проверка подключения

## Implementation Steps

### Task 1: Добавить MySQL-сервис в docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] добавить сервис `phpbb_db` (image: `mysql:5.7`, profiles: `[phpbb]`)
- [ ] добавить healthcheck (`mysqladmin ping`)
- [ ] пробросить порт `3306:3306` для доступа с хоста
- [ ] добавить том `phpbb_data` в секцию `volumes`
- [ ] убедиться, что `docker compose --profile phpbb up -d phpbb_db` синтаксически валиден

### Task 2: Добавить MySQL-переменные в .env.example

**Files:**
- Modify: `.env.example`

- [ ] добавить секцию `# phpBB MySQL` с переменными `MYSQL_DATABASE`, `MYSQL_USER`,
  `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`
- [ ] добавить безопасные значения-примеры (не реальные пароли)

### Task 3: Добавить PyMySQL и настроить его как MySQLdb

**Files:**
- Modify: `pyproject.toml`
- Modify: `config/__init__.py`

- [ ] добавить `pymysql` в `dependencies` в `pyproject.toml`
- [ ] запустить `uv sync` чтобы обновить `uv.lock`
- [ ] в `config/__init__.py` добавить `import pymysql; pymysql.install_as_MySQLdb()`
- [ ] убедиться, что `uv run python -c "import config"` выполняется без ошибок

### Task 4: Добавить DATABASES['phpbb'] в settings.py

**Files:**
- Modify: `config/settings.py`

- [ ] добавить запись `"phpbb"` в `DATABASES` с ENGINE `django.db.backends.mysql`
- [ ] читать параметры из env: `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`,
  `MYSQL_HOST`, `MYSQL_PORT`
- [ ] добавить `OPTIONS: {"charset": "utf8mb4"}` (phpBB хранит в utf8/utf8mb4)
- [ ] написать тест: `"phpbb" in settings.DATABASES` — должен быть True
- [ ] написать тест: ENGINE phpbb == `django.db.backends.mysql`
- [ ] запустить `uv run pytest` — тесты должны проходить

### Task 5: Создать скелет приложения forum_import

**Files:**
- Create: `apps/forum_import/__init__.py`
- Create: `apps/forum_import/apps.py`
- Create: `apps/forum_import/management/__init__.py`
- Create: `apps/forum_import/management/commands/__init__.py`
- Modify: `config/settings.py`

- [ ] создать `apps/forum_import/__init__.py` (пустой)
- [ ] создать `apps/forum_import/apps.py` с `ForumImportConfig` (name=`apps.forum_import`)
- [ ] создать пустые `__init__.py` в `management/` и `management/commands/`
- [ ] зарегистрировать `apps.forum_import` в `INSTALLED_APPS`
- [ ] написать тест: `apps.forum_import` присутствует в `settings.INSTALLED_APPS`
- [ ] запустить `uv run pytest` — тесты должны проходить

### Task 6: Написать инструкцию по загрузке дампа

**Files:**
- Create: `apps/forum_import/README.md`

- [ ] описать шаги: поднять `phpbb_db`, залить дамп, проверить подключение из Django
- [ ] добавить команду проверки: `uv run python manage.py dbshell --database phpbb`
- [ ] добавить пример запроса к phpBB: `SELECT COUNT(*) FROM phpbb_posts;`

### Task 7: Финальная проверка

- [ ] убедиться, что `docker compose up` (без `--profile phpbb`) поднимается без ошибок
- [ ] убедиться, что `docker compose --profile phpbb up phpbb_db` синтаксически корректен
- [ ] запустить полный набор тестов: `uv run pytest`
- [ ] запустить `uv run ruff check .` — без новых ошибок
- [ ] переместить план в `docs/plans/completed/`

## Post-Completion

**Загрузка дампа (ручной шаг):**
```bash
docker compose --profile phpbb up -d phpbb_db
# дождаться healthy
docker compose exec phpbb_db mysql -u phpbb -p phpbb < /path/to/forum_dump.sql
# проверить подключение из Django:
uv run python manage.py dbshell --database phpbb
```

**Следующий шаг (отдельный план):** создать модели `Category`, `Topic`, `Post`, `ForumUser`
и management-команды `import_phpbb_*` для поэтапного переноса данных.
