# forum_import

Инструмент для импорта данных из архивного phpBB-форума (2007–2014) в Django.

## Загрузка дампа

### 1. Поднять MySQL-сервис

```bash
docker compose --profile phpbb up -d phpbb_db
```

Дождаться healthy-статуса:

```bash
docker compose ps phpbb_db
```

### 2. Залить дамп форума

```bash
docker compose exec -T phpbb_db mysql -u phpbb -pPASSWORD phpbb < /path/to/forum_dump.sql
```

Или через файл внутри контейнера:

```bash
docker compose cp /path/to/forum_dump.sql phpbb_db:/tmp/forum_dump.sql
docker compose exec phpbb_db mysql -u phpbb -pPASSWORD phpbb -e "source /tmp/forum_dump.sql"
```

### 3. Проверить подключение из Django

```bash
uv run python manage.py dbshell --database phpbb
```

Пример запроса для проверки:

```sql
SELECT COUNT(*) FROM phpbb_posts;
```

### 4. Остановить сервис

```bash
docker compose --profile phpbb stop phpbb_db
```

## Переменные окружения

Скопируйте из `.env.example` и заполните в `.env`:

```
MYSQL_DATABASE=phpbb
MYSQL_USER=phpbb
MYSQL_PASSWORD=<пароль>
MYSQL_ROOT_PASSWORD=<root-пароль>
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

## Следующий шаг

После загрузки дампа создаются Django-модели (`Category`, `Topic`, `Post`, `ForumUser`)
и management-команды `import_phpbb_*` для поэтапного переноса данных в основную БД.
