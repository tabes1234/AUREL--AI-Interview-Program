"""SQLAlchemy 数据库引擎与会话管理。"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import database_url

engine = create_engine(
    database_url(),
    # SQLite 需要关闭同线程检查才能与 FastAPI 的线程池配合
    connect_args={"check_same_thread": False} if database_url().startswith("sqlite") else {},
)


def _sqlite_security_pragmas(dbapi_connection, connection_record) -> None:
    """T7 数据库安全设置：外键约束、WAL、更快且持久的同步策略、锁等待。"""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


if database_url().startswith("sqlite"):
    event.listen(engine, "connect", _sqlite_security_pragmas)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
