"""
Database connection setup.

This file creates the SQLAlchemy "engine" (the thing that actually talks to the
SQLite file on disk) and a SessionLocal factory (used to create a fresh database
session per request). Every router will use get_db() to borrow a session.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# connect_args is only needed for SQLite - it allows the same connection
# to be used across threads, which FastAPI's request handling requires.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is what all our models (PortfolioItem, Lead, etc.) will inherit from.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency. Yields a database session and guarantees it's closed
    afterward, even if an error happens mid-request.

    Used in routers like:
        @router.get("/leads")
        def list_leads(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
