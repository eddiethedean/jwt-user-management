import os

import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Ensure the backend package root is importable (so `import app...` works)
os.environ.setdefault("PYTHONPATH", os.getcwd())
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-please-change")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-please-change")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")

from app.api.deps import get_db
from app.core.security import hash_password
from app.main import api, app
from app.models.invite import InviteToken
from app.models.password_reset import PasswordResetToken
from app.models.user import User


@pytest.fixture(scope="session")
def engine():
    # Ensure Azure AD validation is disabled in tests
    os.environ.pop("AZURE_TENANT_ID", None)
    os.environ.pop("AZURE_CLIENT_ID", None)
    os.environ.pop("AZURE_CLIENT_SECRET", None)

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    return test_engine


@pytest.fixture()
def db_session(engine):
    with Session(engine) as session:
        # Clear tables between tests (DB is shared via StaticPool)
        session.exec(sa.delete(PasswordResetToken))
        session.exec(sa.delete(InviteToken))
        session.exec(sa.delete(User))
        session.commit()
        yield session


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    api.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://testserver/api") as c:
        yield c
    api.dependency_overrides.clear()


@pytest.fixture()
def admin_user(db_session):
    user = User(
        email="admin@test.local",
        full_name="Admin",
        hashed_password=hash_password("password123"),
        is_active=True,
        is_admin=True,
        permissions=["users:read", "users:write"],
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def normal_user(db_session):
    user = User(
        email="user@test.local",
        full_name="User",
        hashed_password=hash_password("password123"),
        is_active=True,
        is_admin=False,
        permissions=["self:read"],
        email_verified=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
