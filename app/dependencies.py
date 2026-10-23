import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings

header = APIKeyHeader(name="X-API-Key", auto_error=False)


def current_user(key: str | None = Security(header)) -> str:
    if key:
        for expected, user in get_settings().api_keys.items():
            if secrets.compare_digest(key.encode("utf-8"), expected.encode("utf-8")):
                return user
    raise HTTPException(401, "Invalid API key")
