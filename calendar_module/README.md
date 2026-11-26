# Модуль календаря

Модуль предназначен для подключения к общему приложению Corporate-calendar. Он реализует создание событий, получение доступных пользователю событий, выдачу и отзыв доступа, создание групп, добавление участников и графическое окно календаря.

## Состав

- `event_service.py` — функции работы с событиями, доступом и группами.
- `window.py` — окно календаря `CalendarWindow`.
- `dialogs.py` — окна создания события и группы.
- `database.py` — SQLite-база только для локальной демонстрации и тестов; в основном приложении этот класс использовать не нужно.
- `demo_main.py` — самостоятельный демонстрационный запуск с тестовыми пользователями и событиями.
- `tests/` — автоматические тесты функций работы с БД.

## Зависимости

Python 3.10 или новее, `tkinter`, `customtkinter` и `tkcalendar`. Установите зависимости из корня репозитория:

```bash
python -m pip install -r calendar_module/requirements.txt
```

Если в корне репозитория уже есть общий `requirements.txt`, не заменяйте его. Добавьте туда строки `customtkinter` и `tkcalendar` либо сохраните отдельный файл зависимостей модуля.

## Подключение к главному приложению

После авторизации и инициализации общей базы данных откройте календарь так:

```python
from calendar_module.window import CalendarWindow

calendar_window = CalendarWindow(app, database, current_user)
```

- `app` — существующее главное окно Tkinter/CustomTkinter.
- `database` — общий объект базы данных приложения.
- `current_user` — словарь с `id`, `username`, `email`, `role` либо объект пользователя с такими атрибутами.

Окно календаря создаётся как `CTkToplevel`, поэтому отдельный `mainloop()` для него не нужен. Закрытие календаря закрывает только окно календаря, а не всё главное приложение.

Объект `database` должен предоставлять SQLite-соединение через атрибут `connection`, `conn` или `connection_db`, либо через метод `get_connection()`. Соединение должно быть обычным `sqlite3.Connection`. Если общий проект использует другой способ работы с БД или другой драйвер, адаптер в `_get_connection()` файла `event_service.py` нужно согласовать и изменить перед линковкой.

## Требуемая схема БД

SQL-запросы этого модуля используют таблицы и поля из индивидуальной документации календаря:

- `users(id, username, email, role, ...)`
- `groups(id, title, description, creator_id)`
- `group_members(group_id, user_id)`
- `events(id, title, description, start_time, end_time, access_type, category, author_id, group_id)`
- `event_access(event_id, user_id, permission)`

Допустимые значения: `access_type` — `private`, `limited`, `public`; `category` — `personal`, `work`, `rest`; `permission` — `read`, `edit_tasks`, `full`. Перед объединением тимлид должен подтвердить, что общая БД использует эту схему. Если в общей БД названия отличаются, нужно согласовать единый вариант и адаптировать SQL-запросы.

В текущей реализации публичное событие с `group_id` видно участникам этой группы, а публичное событие без группы — всем пользователям. Это правило также необходимо подтвердить с тимлидом.

## Функции сервиса

```python
create_event(title, start_time, end_time, author_id, access_type, description="", category="personal", group_id=None, database=None)
get_events_for_user(user_id, database=None)
add_event_access(event_id, user_id, permission, database=None)
create_group(title, creator_id, database=None, description="")
add_user_to_group(group_id, user_id, database=None)
remove_event_access(event_id, user_id, database=None)
```

Для общего приложения всегда передавайте объект общей БД аргументом `database`. Если он не передан, функции выдадут ошибку вместо создания отдельной локальной базы.

## Локальная демонстрация

Из корня репозитория выполните:

```bash
python -m calendar_module.demo_main
```

Этот запуск создаёт `calendar_module/calendar_demo.db` и демонстрационные учётные записи `alex`, `maria`, `ivan`. Локальная база исключена из Git файлом `.gitignore`. Демонстрационные данные не создаются при импорте модуля или открытии календаря из главного приложения.

## Автоматические тесты

Из корня репозитория выполните:

```bash
python -m unittest calendar_module.tests.test_event_service -v
```

Тесты используют временную БД и не меняют общую базу проекта.

## Перед слиянием

1. Согласуйте с тимлидом схему таблиц и трактовку публичных событий без группы.
2. Проверьте, что общий объект `Database` предоставляет SQLite-соединение совместимым способом.
3. Подключите `CalendarWindow` из главного приложения с общей БД и авторизованным пользователем.
4. Проверьте права доступа вместе с модулями задач и чата.
5. Не вызывайте `demo_main.py` из главного приложения.
