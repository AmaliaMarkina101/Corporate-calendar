"""Экраны входа и регистрации (рисуются прямо в главном окне)."""
import customtkinter as ctk

from auth_service import AuthError, AuthService, MIN_PASSWORD

ERROR_COLOR = ("#c0392b", "#ff7b72")


def _title(master, text, size=28):
    return ctk.CTkLabel(master, text=text, font=ctk.CTkFont(size=size, weight="bold"))


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, auth: AuthService, on_login, on_show_register):
        super().__init__(master, fg_color="transparent")
        self.auth = auth
        self.on_login = on_login

        card = ctk.CTkFrame(self, corner_radius=14)
        card.place(relx=0.5, rely=0.5, anchor="center")
        _title(card, "Корпоративный календарь").pack(padx=40, pady=(32, 4))
        ctk.CTkLabel(card, text="Войдите в свой аккаунт", text_color="gray").pack(pady=(0, 18))

        self.identifier = ctk.CTkEntry(card, width=320, height=38, placeholder_text="Логин или email")
        self.identifier.pack(padx=40, pady=6)
        self.password = ctk.CTkEntry(card, width=320, height=38, placeholder_text="Пароль", show="•")
        self.password.pack(padx=40, pady=6)

        self.show_password = ctk.CTkCheckBox(card, text="Показать пароль", command=self._toggle_password)
        self.show_password.pack(padx=40, pady=(4, 0), anchor="w")

        self.error = ctk.CTkLabel(card, text="", text_color=ERROR_COLOR, wraplength=320)
        self.error.pack(padx=40, pady=(8, 0))

        ctk.CTkButton(card, text="Войти", width=320, height=40, command=self._submit).pack(padx=40, pady=(10, 6))
        ctk.CTkButton(
            card, text="Нет аккаунта? Зарегистрироваться", width=320, height=34,
            fg_color="transparent", border_width=1, text_color=("gray20", "gray90"),
            command=on_show_register,
        ).pack(padx=40, pady=(0, 32))

        for entry in (self.identifier, self.password):
            entry.bind("<Return>", self._submit)
        self.after(150, self.identifier.focus_set)

    def _toggle_password(self):
        self.password.configure(show="" if self.show_password.get() else "•")

    def _submit(self, event=None):
        try:
            user = self.auth.login(self.identifier.get(), self.password.get())
        except AuthError as exc:
            self.error.configure(text=str(exc))
            self.password.delete(0, "end")
            return
        self.on_login(user)


class RegisterFrame(ctk.CTkFrame):
    def __init__(self, master, auth: AuthService, on_registered, on_show_login):
        super().__init__(master, fg_color="transparent")
        self.auth = auth
        self.on_registered = on_registered

        card = ctk.CTkScrollableFrame(self, width=380, corner_radius=14)
        card.pack(expand=True, fill="y", pady=20)
        _title(card, "Регистрация", 26).pack(padx=30, pady=(20, 14))

        self.first_name = self._field(card, "Имя")
        self.last_name = self._field(card, "Фамилия")
        self.username = self._field(card, "Логин")
        self.email = self._field(card, "Email")
        self.password = self._field(card, f"Пароль (не короче {MIN_PASSWORD} символов)", secret=True)
        self.password2 = self._field(card, "Повторите пароль", secret=True)

        self.error = ctk.CTkLabel(card, text="", text_color=ERROR_COLOR, wraplength=320)
        self.error.pack(padx=30, pady=(8, 0))
        ctk.CTkButton(card, text="Создать аккаунт", width=320, height=40, command=self._submit).pack(padx=30, pady=(10, 6))
        ctk.CTkButton(
            card, text="Назад ко входу", width=320, height=34, fg_color="transparent",
            border_width=1, text_color=("gray20", "gray90"), command=on_show_login,
        ).pack(padx=30, pady=(0, 20))
        self.after(150, self.first_name.focus_set)

    def _field(self, card, label, secret=False):
        ctk.CTkLabel(card, text=label, anchor="w").pack(padx=30, pady=(6, 0), fill="x")
        entry = ctk.CTkEntry(card, width=320, height=36, show="•" if secret else "")
        entry.pack(padx=30, pady=(2, 0))
        entry.bind("<Return>", self._submit)
        return entry

    def _submit(self, event=None):
        if self.password.get() != self.password2.get():
            self.error.configure(text="Пароли не совпадают.")
            return
        try:
            user = self.auth.register(
                self.username.get(), self.email.get(), self.password.get(),
                self.first_name.get(), self.last_name.get(),
            )
        except AuthError as exc:
            self.error.configure(text=str(exc))
            return
        self.on_registered(user)
