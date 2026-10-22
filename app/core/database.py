from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger

logger = get_logger("database")

# Create the async engine.
# pool_pre_ping checks the connection before checking out.
# For production, we avoid exposing query details (echo=False).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections after 30 mins
)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    Provides a session and ensures it's closed after the request.
    Rolls back transaction on any exceptions.
    """
    session = AsyncSessionLocal()
    try:
        yield session
    except SQLAlchemyError as e:
        logger.error("Database error occurred, rolling back session.")
        await session.rollback()
        raise DatabaseError("Database operation failed") from e
    except Exception as e:
        logger.error("Unexpected error occurred, rolling back session.")
        await session.rollback()
        raise e
    finally:
        await session.close()
