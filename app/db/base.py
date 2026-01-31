from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.settings import get_settings

settings = get_settings()

Base = declarative_base()

url = settings.database_url
if not url.startswith("postgresql+asyncpg://"):
    url = url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    url,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
    connect_args={
        "server_settings": {
            "application_name": "com_brasper_api",
            "statement_timeout": "300000"
        },
        "command_timeout": 60,
        "timeout": 30,
    }
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
