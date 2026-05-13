from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User

DB = Annotated[AsyncSession, Depends(get_db)]


async def guard_not_remnawave_managed(user: User) -> None:
    if user.remnawave_user is not None:
        raise HTTPException(
            status_code=409,
            detail='Remnawave-managed user cannot be modified locally',
        )
