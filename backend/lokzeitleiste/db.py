import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


@lru_cache
def engine():
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("mysql+pymysql://"):
        raise RuntimeError("DATABASE_URL muss eine mysql+pymysql://-Adresse sein")
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def database_session():
    with sessionmaker(bind=engine(), expire_on_commit=False)() as session:
        yield session
