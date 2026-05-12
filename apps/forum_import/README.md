# forum_import

Инструмент для импорта данных из архивного phpBB-форума (2007–2014) в Django.

## Загрузка дампа

Дамп лежит в `scratch/2022-12-01-mysql/forum.gz` (gzip-сжатый SQL-дамп MySQL).

### 1. Поднять MySQL-сервис

```bash
cd ../infra
docker compose up -d phpbb_db
```

Дождаться healthy-статуса:

```bash
docker compose ps phpbb_db
# phpbb_db   ...   Up (healthy)
```

### 2. Залить дамп форума

Для gzip-сжатого файла:

```bash
gunzip -c scratch/2022-12-01-mysql/forum.gz \
  | docker exec -i infra-phpbb_db-1 mysql -u dev -pdev phpbb
```

Для несжатого `.sql`-файла:

```bash
docker exec -i infra-phpbb_db-1 mysql -u dev -pdev phpbb < /path/to/forum_dump.sql
```

### 3. Проверить импорт

```bash
docker exec infra-phpbb_db-1 mysql -u dev -pdev phpbb \
  -e "SHOW TABLES; SELECT COUNT(*) FROM vu2_posts; SELECT COUNT(*) FROM vu2_topics; SELECT COUNT(*) FROM vu2_users;" 2>/dev/null
```

### 4. Проверить подключение через Django

```bash
uv run python manage.py shell -c "
from django.db import connections
cursor = connections['phpbb'].cursor()
cursor.execute('SELECT COUNT(*) FROM vu2_posts')
print(cursor.fetchone())
"
```

### 5. Остановить сервис

```bash
cd ../infra && docker compose stop phpbb_db
```

## Переменные окружения

Credentials для подключения Django к MySQL (заполнить в `.env`):

```
PHPBB_DB_HOST=127.0.0.1
PHPBB_DB_PORT=3306
PHPBB_DB_NAME=phpbb
PHPBB_DB_USER=dev
PHPBB_DB_PASSWORD=dev
```

## Следующий шаг

После загрузки дампа создаются Django-модели (`Category`, `Topic`, `Post`, `ForumUser`)
и management-команды `import_phpbb_*` для поэтапного переноса данных в основную БД.
