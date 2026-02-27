from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from app.core.container import AppContainer


def get_container(connection: HTTPConnection) -> AppContainer:
    return connection.app.state.container


async def get_session(
    container: AppContainer = Depends(get_container),
) -> AsyncIterator[AsyncSession]:
    async with container.session_factory() as session:
        yield session
