from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import settings
from bot.database.models import Base


def _build_engine_kwargs() -> dict:
    kwargs: dict = {"echo": False}
    if settings.db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 30}
    return kwargs


engine = create_async_engine(settings.db_url, **_build_engine_kwargs())

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
