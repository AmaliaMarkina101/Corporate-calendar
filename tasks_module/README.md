# tasks_module — задачи внутри события

Работает на той же базе, что и календарь (`calendar_module.database.Database`): отдельной БД нет.
Таблицы `tasks` и `task_comments` создаются сами при первом создании `TaskService`.

## Подключение в приложение

```python
from tasks_module.window import open_tasks

open_tasks(parent, database, current_user, event_id)          # окно задач события
# current_user: dict или объект с полями id, username, role
```

Из календаря (кнопка «Задачи события» в карточке):

```python
CalendarWindow(app, database, user,
               on_open_tasks=lambda event_id: open_tasks(app, database, user, event_id))
```

Чат подключается так же через `on_open_chat` и у календаря, и у `open_tasks`.

## Правила доступа (те же, что в календаре)

| Событие | Кто работает с ним |
|---|---|
| автор | полный доступ |
| private | только автор |
| limited | выбранные в `event_access` (`read` только смотрит и комментирует, `edit_tasks` и `full` создают и меняют задачи) |
| public без группы | все |
| public с группой | только участники группы |

Задачу создаёт и меняет тот, у кого `edit_tasks` или `full`. Статус меняют исполнитель, создатель
задачи и автор события. Исполнителя выбирает и назначает только тимлид, и только из участников
созданных им групп, у которых есть право работать с задачами этого события.

## Проверка

```
python -m unittest discover -s tasks_module/tests -t .       # логика, без окон
python -m tasks_module.demo_main --user 1 --event 1          # окно задач
```

Демо-данные те же, что у календаря. Пользователь: 1 alex (тимлид), 2 maria, 3 ivan.
Событие: 1 публичное с группой, 2 ограниченное (maria читает, ivan правит задачи), 3 приватное (alex).
