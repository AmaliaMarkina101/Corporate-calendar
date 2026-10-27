from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    username: str
    email: str
    role: str

    @classmethod
    def from_row(cls, row: dict) -> "User":
        return cls(
            id=int(row["id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            role=str(row["role"]),
        )


class AuthorizationError(PermissionError):
    """Пользователь не имеет права выполнить действие."""
