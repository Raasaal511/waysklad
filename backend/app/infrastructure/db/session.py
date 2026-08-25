from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
