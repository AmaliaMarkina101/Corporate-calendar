from __future__ import annotations

from dataclasses import dataclass


class AuthorizationError(PermissionError):
    """Пользователь не имеет права выполнить действие."""


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str
    email: str = ""

    @classmethod
    def from_any(cls, user) -> "User":
        """Принимает User, dict (в том числе sqlite3.Row через dict()) или объект с полями id, username, role."""
        if isinstance(user, cls):
            return user
        get = user.get if isinstance(user, dict) else (lambda key, default=None: getattr(user, key, default))
        return cls(
            id=int(get("id")),
            username=str(get("username", "")),
            role=str(get("role", "member")),
            email=str(get("email", "") or ""),
        )
