from collections.abc import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.config import settings
import ssl

# Sync engine (used by Alembic) - works fine with ?sslmode=require
engine = create_engine(settings.database_url, echo=False)

def _async_db_url(url: str) -> str:
    """Swap to asyncpg driver for FastAPI routes"""
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://") and "+asyncpg" not in url:
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# 1. Clean the URL for asyncpg
clean_async_url = _async_db_url(settings.database_url)
clean_async_url = clean_async_url.replace("?sslmode=require", "").replace("&sslmode=require", "")

# 2. Build the SSL Context to encrypt traffic to J39_miso
async_connect_args = {}
if "sslmode=require" in settings.database_url:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    async_connect_args["ssl"] = ssl_ctx

# 3. Create Async Engine
async_engine: AsyncEngine = create_async_engine(
    clean_async_url,
    echo=False,
    connect_args=async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

def get_sync_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
