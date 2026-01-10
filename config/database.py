"""
数据库配置 - 支持SQLite(开发)和MySQL(生产)
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from sqlalchemy.orm import declarative_base
except Exception:
    from sqlalchemy.ext.declarative import declarative_base


DATABASE_URLS = {
    'sqlite': 'sqlite:///./band_strategy.db',
    'mysql': 'mysql+pymysql://root:root@localhost:3306/band_strategy?charset=utf8mb4'
}

DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DATABASE_URL = DATABASE_URLS.get(DB_TYPE, DATABASE_URLS["sqlite"])

Base = declarative_base()

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "False").lower() == "true",
    connect_args={"check_same_thread": False} if DB_TYPE == "sqlite" else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db():
    """数据库会话上下文"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库"""
    try:
        import data.storage.models  # noqa: F401
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
