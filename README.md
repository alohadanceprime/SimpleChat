Перед использованием:

1. Cоздайте базу данных postgres:
CREATE DATABASE userdata;

2. Подключитесь к созданной базе данных и выполните команды из .sql файла:
\с userdata
\i .../create_table.sql

3. Установите asyncpg

4. Поставить свои username, password и т.п. в psql params, проверить свободность портов
