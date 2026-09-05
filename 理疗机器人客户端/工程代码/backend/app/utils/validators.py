import re
from typing import Optional


def validate_phone(phone: str) -> bool:
    pattern = r"^1[3-9]\d{9}$"
    return bool(re.match(pattern, phone))


def validate_password(password: str) -> bool:
    return len(password) >= 6


def validate_nickname(nickname: Optional[str]) -> bool:
    if nickname is None:
        return True
    return len(nickname) >= 2 and len(nickname) <= 50
