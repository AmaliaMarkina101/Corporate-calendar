from datetime import datetime
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from tkcalendar import DateEntry

from .event_service import (
    add_event_access,
    add_user_to_group,
    create_event,
    create_group,
    get_groups_for_user,
    get_users,
)


def _fit_height(window, wanted):
    """Высота окна не больше экрана (с запасом под панель задач и заголовок)."""
    return max(420, min(wanted, window.winfo_screenheight() - 120))


def _safe_grab(window):
    # Сразу после создания окно может быть ещё не видно, и grab_set падает на Linux/WSL.
    try:
        window.grab_set()
    except tk.TclError:
        window.after(100, lambda: _safe_grab(window))


class CreateEventDialog(ctk.CTkToplevel):
    def __init__(self, parent, database, current_user, on_saved):
        super().__init__(parent)
        self.database = database
        self.current_user = current_user
        self.on_saved = on_saved
        self.users = get_users(database, exclude_user_id=current_user["id"])
        self.groups = get_groups_for_user(current_user["id"], database)
        self.user_checks = {}
        self.title("Создать событие")
        self.geometry(f"590x{_fit_height(self, 760)}")
        self.minsize(540, 420)
        self.transient(parent)
        self.after(50, lambda: _safe_grab(self))
        # Поля лежат в прокручиваемой области, кнопка сохранения закреплена внизу
        # и видна на любом экране.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.body = ctk.CTkScrollableFrame(self)
        self.body.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 0))
        self.body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.body, text="Новое событие", font=ctk.CTkFont(size=23, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(14, 14), sticky="w"
        )

        self.title_entry = self._entry_row(1, "Название")
        self.description_entry = ctk.CTkTextbox(self.body, height=75)
        self._label_row(2, "Описание")
        self.description_entry.grid(row=2, column=1, padx=(8, 14), pady=6, sticky="ew")

        self.start_date = self._date_row(3, "Дата начала")
        self.start_time = self._entry_row(4, "Время начала", "09:00")
        self.end_date = self._date_row(5, "Дата окончания")
        self.end_time = self._entry_row(6, "Время окончания", "10:00")

        self.access_type = self._combo_row(7, "Тип доступа", ["private", "limited", "public"], "private")
        self.category = self._combo_row(8, "Тип события", ["personal", "work", "rest"], "personal")

        self.group_values = {"Без группы": None}
        for group in self.groups:
            self.group_values[f"{group['title']} (ID {group['id']})"] = group["id"]
        self.group_choice = self._combo_row(9, "Группа", list(self.group_values), "Без группы")

        self.permission_choice = self._combo_row(10, "Права приглашённых", ["read", "edit_tasks", "full"], "read")
        self._label_row(11, "Пригласить пользователей")
        # Обычный фрейм: прокручивает внешняя область, вложенный скролл мешал бы колесу мыши.
        self.users_frame = ctk.CTkFrame(self.body)
        self.users_frame.grid(row=11, column=1, padx=(8, 14), pady=6, sticky="ew")
        if self.users:
            for user in self.users:
                label = f"{user['username']} ({user['email']})"
                check = ctk.CTkCheckBox(self.users_frame, text=label)
                check.pack(anchor="w", padx=8, pady=4)
                self.user_checks[user["id"]] = check
        else:
            ctk.CTkLabel(self.users_frame, text="Других пользователей пока нет").pack(anchor="w", padx=8, pady=8)

        self.access_type.configure(command=self._update_access_fields)
        self.save_button = ctk.CTkButton(self, text="Сохранить событие", command=self._save)
        self.save_button.grid(row=1, column=0, padx=20, pady=14, sticky="ew")
        self._update_access_fields("private")

    def _label_row(self, row, label):
        ctk.CTkLabel(self.body, text=label).grid(row=row, column=0, padx=(14, 8), pady=6, sticky="w")

    def _entry_row(self, row, label, value=""):
        self._label_row(row, label)
        entry = ctk.CTkEntry(self.body)
        entry.grid(row=row, column=1, padx=(8, 14), pady=6, sticky="ew")
        if value:
            entry.insert(0, value)
        return entry

    def _date_row(self, row, label):
        self._label_row(row, label)
        entry = DateEntry(
            self.body, date_pattern="yyyy-mm-dd", width=17, locale="ru_RU", firstweekday="monday"
        )
        entry.grid(row=row, column=1, padx=(8, 14), pady=6, sticky="w")
        return entry

    def _combo_row(self, row, label, values, default):
        self._label_row(row, label)
        combo = ctk.CTkComboBox(self.body, values=values, state="readonly")
        combo.set(default)
        combo.grid(row=row, column=1, padx=(8, 14), pady=6, sticky="ew")
        return combo

    def _update_access_fields(self, value):
        is_limited = value == "limited"
        self.permission_choice.configure(state="normal" if is_limited else "disabled")
        for check in self.user_checks.values():
            check.configure(state="normal" if is_limited else "disabled")

    def _save(self):
        title = self.title_entry.get().strip()
        start_text = f"{self.start_date.get()} {self.start_time.get().strip()}"
        end_text = f"{self.end_date.get()} {self.end_time.get().strip()}"
        try:
            start_value = datetime.strptime(start_text, "%Y-%m-%d %H:%M")
            end_value = datetime.strptime(end_text, "%Y-%m-%d %H:%M")
            if end_value < start_value:
                raise ValueError("Дата окончания не может быть раньше даты начала")
            selected_group = self.group_values.get(self.group_choice.get())
            event_id = create_event(
                title=title,
                description=self.description_entry.get("1.0", "end").strip(),
                start_time=start_value,
                end_time=end_value,
                author_id=self.current_user["id"],
                access_type=self.access_type.get(),
                category=self.category.get(),
                group_id=selected_group,
                database=self.database,
            )
            if self.access_type.get() == "limited":
                permission = self.permission_choice.get()
                for user_id, check in self.user_checks.items():
                    if check.get():
                        add_event_access(event_id, user_id, permission, self.database)
        except (ValueError, TypeError) as error:
            messagebox.showerror("Не удалось сохранить событие", str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror("Ошибка базы данных", str(error), parent=self)
            return
        self.destroy()
        self.on_saved()


class CreateGroupDialog(ctk.CTkToplevel):
    def __init__(self, parent, database, current_user, on_saved):
        super().__init__(parent)
        self.database = database
        self.current_user = current_user
        self.on_saved = on_saved
        self.users = get_users(database, exclude_user_id=current_user["id"])
        self.user_checks = {}
        self.title("Создать группу")
        self.geometry(f"450x{_fit_height(self, 520)}")
        self.minsize(400, 420)
        self.transient(parent)
        self.after(50, lambda: _safe_grab(self))
        # Кнопку упаковываем первой, чтобы при нехватке места сжимался список, а не она.
        ctk.CTkButton(self, text="Создать группу", command=self._save).pack(
            side="bottom", fill="x", padx=20, pady=18
        )

        ctk.CTkLabel(self, text="Новая группа", font=ctk.CTkFont(size=22, weight="bold")).pack(
            padx=20, pady=(20, 12), anchor="w"
        )
        ctk.CTkLabel(self, text="Название группы").pack(padx=20, anchor="w")
        self.title_entry = ctk.CTkEntry(self, placeholder_text="Например, Команда разработки")
        self.title_entry.pack(fill="x", padx=20, pady=(4, 12))
        ctk.CTkLabel(self, text="Описание").pack(padx=20, anchor="w")
        self.description_entry = ctk.CTkTextbox(self, height=75)
        self.description_entry.pack(fill="x", padx=20, pady=(4, 12))
        ctk.CTkLabel(self, text="Добавить участников").pack(padx=20, anchor="w")
        self.users_frame = ctk.CTkScrollableFrame(self, height=180)
        self.users_frame.pack(fill="both", expand=True, padx=20, pady=8)
        for user in self.users:
            label = f"{user['username']} ({user['email']})"
            check = ctk.CTkCheckBox(self.users_frame, text=label)
            check.pack(anchor="w", padx=8, pady=4)
            self.user_checks[user["id"]] = check

    def _save(self):
        try:
            group_id = create_group(
                self.title_entry.get(),
                self.current_user["id"],
                self.database,
                self.description_entry.get("1.0", "end").strip(),
            )
            for user_id, check in self.user_checks.items():
                if check.get():
                    add_user_to_group(group_id, user_id, self.database)
        except Exception as error:
            messagebox.showerror("Не удалось создать группу", str(error), parent=self)
            return
        self.destroy()
        self.on_saved()
