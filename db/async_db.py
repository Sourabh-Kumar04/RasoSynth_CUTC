"""Async database connection manager and configuration.

Provides explicit connection handling without silent mock fallbacks.
"""
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


@dataclass
class DatabaseConfig:
    """Configuration for async database connection."""
    url: str
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class AsyncDatabaseManager:
    """Manages async database engine lifecycle and connection verification."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None

    async def initialize(self) -> None:
        """Initialize engine and verify connection explicitly.

        Raises:
            RuntimeError: If connection cannot be established.
        """
        try:
            url = self.config.url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
                url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)

            self.engine = create_async_engine(
                url,
                echo=self.config.echo,
            )
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:
            raise RuntimeError(f"Database connection failed: {e}") from e

    async def close(self) -> None:
        """Close connection engine."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
