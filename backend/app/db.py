from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings


engine = create_engine(get_settings().database_url, pool_pre_ping=True)


def get_db() -> Generator[Engine, None, None]:
    yield engine


def check_database_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

