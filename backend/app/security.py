import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def require_access_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_access_key: Annotated[str | None, Header()] = None,
) -> None:
    """Shared demo key (ADR-07). Constant-time comparison."""
    if x_access_key is None or not hmac.compare_digest(
        x_access_key.encode(), settings.access_key.encode()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing access key")
