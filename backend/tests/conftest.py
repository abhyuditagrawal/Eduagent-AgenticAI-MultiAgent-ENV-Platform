import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.config import get_settings
from app.main import app
from app.models.user import User
from app.services.auth import hash_password, create_access_token

settings = get_settings()

# Use the same database but with a test schema approach
# For simplicity, use the existing database with cleanup
TEST_DATABASE_URL = settings.DATABASE_URL

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_student(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test_student_{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test Student",
        hashed_password=hash_password("testpass123"),
        role="student",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_admin(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test_admin_{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test Admin",
        hashed_password=hash_password("adminpass123"),
        role="admin",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def student_token(test_student: User) -> str:
    token_data = {
        "sub": str(test_student.id),
        "email": test_student.email,
        "role": test_student.role,
    }
    return create_access_token(token_data)


@pytest_asyncio.fixture
async def admin_token(test_admin: User) -> str:
    token_data = {
        "sub": str(test_admin.id),
        "email": test_admin.email,
        "role": test_admin.role,
    }
    return create_access_token(token_data)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
