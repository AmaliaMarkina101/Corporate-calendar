"""Заполняет чистую базу демо-данными, чтобы проверить приложение под разными ролями.

    python seed_demo.py

Аккаунты (пароль у всех demo1234):  admin (администратор), alex (тимлид), maria и ivan (участники).
У maria создаётся задача с напоминанием через 1 минуту: войдите под maria и подождите.
"""
import argparse
import sys
from datetime import datetime, timedelta

from auth_service import hash_password
from calendar_module.demo_main import seed_demo_data
from main import DB_PATH, open_database
from tasks_module.task_service import TaskService

PASSWORD = "demo1234"


def main():
    parser = argparse.ArgumentParser(description="Демо-данные для Corporate Calendar")
    parser.add_argument("--reminder-in", type=int, default=1, help="через сколько минут напомнить maria (по умолчанию 1)")
    args = parser.parse_args()

    database = open_database()
    connection = database.connection
    if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        sys.exit(f"В базе уже есть пользователи. Удалите файл {DB_PATH.name} и запустите снова.")

    seed_demo_data(database)  # alex(1), maria(2), ivan(3), группа и три события из демо календаря
    connection.execute(
        "INSERT INTO users (id, username, email, password, role, first_name, last_name) "
        "VALUES (4, 'admin', 'admin@example.com', '', 'admin', 'Админ', 'Системы')"
    )
    connection.execute("UPDATE users SET password = ?", (hash_password(PASSWORD),))
    connection.commit()

    event_id = connection.execute("SELECT id FROM events WHERE title = 'Обсуждение проекта'").fetchone()["id"]
    alex = {"id": 1, "username": "alex", "role": "teamlead"}
    now = datetime.now()
    TaskService(database, alex).create_task(
        event_id, "Подготовить отчёт", "Демо-задача с напоминанием.", 2,
        (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        (now + timedelta(minutes=args.reminder_in)).strftime("%Y-%m-%d %H:%M"),
    )
    print(f"Готово: {DB_PATH}\nЛогины: admin, alex, maria, ivan. Пароль: {PASSWORD}")
    database.close()


if __name__ == "__main__":
    main()
