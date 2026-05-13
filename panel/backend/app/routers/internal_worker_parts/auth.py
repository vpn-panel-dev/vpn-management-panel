import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status


async def require_worker_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.environ.get('WORKER_TOKEN')
    if not expected or not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    token = authorization.removeprefix('Bearer ').strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
