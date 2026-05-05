"""
Shared fixtures for the test suite.
Uses an in-memory SQLite database to avoid needing a running PostgreSQL instance.
pgvector-specific SQL is NOT available in SQLite, so vector operations are
excluded from unit tests (they are covered by integration tests against a real DB).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.user import User
from app.models.content import Content  # noqa: F401 — registers model with Base


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user(db_session):
    from app.core.security import get_password_hash
    import uuid

    user = User(
        id=uuid.uuid4(),
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
