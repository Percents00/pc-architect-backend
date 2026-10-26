# PC ARCHITECT — Backend

Django 5.2, Python 3.14, PostgreSQL 18. API каталога, регистрации, токенов и приватных сборок. Модели и миграции БД находятся в этом репозитории.

## Репозитории проекта

- [Фронтенд](https://github.com/Percents00/pc-architect-frontend)
- [Документация](https://github.com/Percents00/pc-architect-docs)

## Подготовка

Разместите репозитории рядом:

```text
PC_ARCHITECT/
  frontend/
  backend/
  documentation/
```

Из папки `backend`, при работающем PostgreSQL:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$pgPassword = Read-Host "Пароль PostgreSQL" -AsSecureString
$env:PGPASSWORD = [System.Net.NetworkCredential]::new("", $pgPassword).Password
Remove-Variable pgPassword
& "C:\Program Files\PostgreSQL\18\bin\createdb.exe" -U postgres -h 127.0.0.1 -p 5432 -E UTF8 pc_architect
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_catalog
.\.venv\Scripts\python.exe manage.py runserver
```

Готовое окружение не создавайте повторно; существующую БД повторно создавать не нужно. При другой папке установки Python или PostgreSQL измените путь. Откройте `http://127.0.0.1:8000/`. Остановка — `Ctrl+C`.

## Следующий запуск

В папке `backend` задайте пароль в новом терминале:

```powershell
$pgPassword = Read-Host "Пароль PostgreSQL" -AsSecureString
$env:PGPASSWORD = [System.Net.NetworkCredential]::new("", $pgPassword).Password
Remove-Variable pgPassword
.\.venv\Scripts\python.exe manage.py runserver
```

Стандартное подключение: `127.0.0.1:5432`, пользователь `postgres`, база `pc_architect`. Для другого подключения задайте `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`. `.env` автоматически не читается.

По умолчанию Django ищет соседнюю папку `frontend`; также распознаются `pc-architect-frontend` и имя распакованного архива `pc-architect-frontend-main`. Другой путь можно указать перед запуском:

```powershell
$env:FRONTEND_DIR = "D:\путь\к\фронтенду"
```

Без фронтенда API, миграции и заполнение каталога работают отдельно; главная страница сообщает об отсутствии интерфейса. CORS для совместного запуска не требуется: страницу и API раздаёт Django.

## Данные и проверки

`core/fixtures/components.json` — начальный каталог из 7 категорий и 21 компонента. `seed_catalog` добавляет отсутствующие записи и не перезаписывает существующие.

```powershell
.\.venv\Scripts\python.exe manage.py check
```

После изменения моделей создайте миграции через `makemigrations`, затем примените `migrate`.

Не включайте в репозиторий `.venv`, `.env` и `.django-secret-key` — они исключены через `.gitignore`. Общая документация находится в репозитории [pc-architect-docs](https://github.com/Percents00/pc-architect-docs).
