from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

settings = get_settings()

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=not _is_sqlite,  # pool_pre_ping not supported by aiosqlite
    # SQLite: wait up to 30 s for write locks instead of immediately raising
    # "database is locked" when the middleware and a route handler write concurrently.
    connect_args={"timeout": 30} if _is_sqlite else {},
    **({"pool_size": 5, "max_overflow": 10} if not _is_sqlite else {}),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


# Tracks whether table DDL has run in this process lifetime.
# Vercel may spin up a fresh process per invocation, so this resets on cold-start.
_db_initialized = False


async def init_db() -> None:
    """Create all tables (idempotent). Enables WAL mode for SQLite.

    WAL pragma and create_all MUST run in separate transactions — mixing them
    in the same engine.begin() block causes a SQLite disk I/O error because
    the journal-mode switch conflicts with the table-introspection PRAGMA
    issued by SQLAlchemy's has_table() check inside run_sync.
    """
    global _db_initialized
    if _is_sqlite:
        # Step 1: set journal mode in its own transaction
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
    # Step 2: create tables in a fresh transaction
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _db_initialized = True


async def _ensure_db() -> None:
    """Lazy init — called before the first session in this process."""
    global _db_initialized
    if not _db_initialized:
        await init_db()


async def get_db():
    """FastAPI dependency that yields a transactional database session.
    Ensures tables exist before the first query on every cold start.
    """
    await _ensure_db()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
