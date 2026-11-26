"""Время в базе хранится в UTC, а пользователю показывается местное."""
from datetime import datetime, timezone


def utc_to_local_text(value, fmt="%d.%m.%Y %H:%M"):
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().strftime(fmt)
