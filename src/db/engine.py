from fastapi import HTTPException

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.config import db_url

engine = create_async_engine(url=db_url)
AsynSessionLocal = async_sessionmaker(bind=engine)


async def get_session():
    try:
        async with AsynSessionLocal() as session:
            yield session

    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Ошибки при работе с базой данных")
    
    
