"""Local SQLite by default; hosted PostgreSQL when DATABASE_URL is set."""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_FILE = Path(__file__).resolve().parent / "miraflores.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
    if not DATABASE_URL.startswith("postgresql+psycopg://"):
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    engine = create_engine(
        f"sqlite:///{DATABASE_FILE.as_posix()}",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass
