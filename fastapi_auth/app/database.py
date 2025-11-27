# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# ======================================================
# 1. Load DATABASE_URL (fallback to SQLite automatically)
# ======================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Auto-fallback to SQLite instead of crashing
    print("⚠️ DATABASE_URL not set — using SQLite database.db")
    DATABASE_URL = "sqlite:///./database.db"

# ======================================================
# 2. Create SQLAlchemy Engine
#    PostgreSQL → pooling enabled
#    SQLite     → pooling disabled (SQLite hates it)
# ======================================================

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # required for SQLite
        echo=False
    )
else:
    # PostgreSQL, MySQL, etc.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=60,
        pool_recycle=3600,
        echo=False
    )

# SessionLocal factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for ORM models
Base = declarative_base()

# ======================================================
# 3. DB Dependency (FastAPI standard)
# ======================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
