from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.config import db_url


engine = create_async_engine(url=db_url)
AsynSessionLocal = async_sessionmaker(bind=engine)


async def get_session():
    async with AsynSessionLocal() as session:
        yield session