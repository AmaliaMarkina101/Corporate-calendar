# chat_module — личные и групповые чаты

Работает на общей базе приложения (той же, что календарь и задачи). Таблицы `chat_messages` и
`private_messages` создаются сами при создании `ChatService`.

## Подключение в приложение

```python
from chat_module.window import open_chat

open_chat(parent, database, current_user)               # окно чата
open_chat(parent, database, current_user, event_id=1)   # сразу чат события 1
```

Из календаря (кнопка «Чат события») и из задач:

```python
CalendarWindow(app, database, user,
               on_open_chat=lambda event_id: open_chat(app, database, user, event_id))
open_tasks(app, database, user, event_id,
           on_open_chat=lambda eid: open_chat(app, database, user, eid))
```

В обратную сторону, из чата события в задачи (кнопка «Задачи» в шапке):

```python
open_chat(app, database, user, event_id,
          on_open_tasks=lambda eid: open_tasks(app, database, user, eid))
```

## Правила

- Чат события доступен тем же людям, что и само событие (правила как в календаре и задачах, `core/event_access.py`).
- Групповой чат показывает последние 50 сообщений.
- Личную переписку видят только двое участников. Писать самому себе нельзя.
- Список чатов: сверху тот, где писали последним; чаты событий без сообщений внизу.
- Поиск ищет по имени, фамилии и логину без учёта регистра. «Мария Иванова» ищет по обоим словам.
- Время в базе хранится в UTC, пользователю показывается местное.

## Проверка

```
python -m unittest discover -s chat_module/tests -t .
python -m chat_module.demo_main --user 1
python -m chat_module.demo_main --user 2 --event 1
```
