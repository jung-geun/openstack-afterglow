"""Fail-closed schema bootstrap for deployment automation."""

import asyncio

from app.config import get_settings
from app.database import close_db, create_tables, init_db


async def main() -> None:
    """Initialize the configured database and synchronously create its schema."""
    try:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("database_url must be configured for schema bootstrap")

        init_db(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            connect_timeout=settings.database_connect_timeout,
            pool_timeout=settings.database_pool_timeout,
            unhealthy_seconds=settings.database_unhealthy_seconds,
        )
        await create_tables()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
