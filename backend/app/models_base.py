"""Declarative Base（独立文件，供 Alembic env.py 与模型共用）。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
