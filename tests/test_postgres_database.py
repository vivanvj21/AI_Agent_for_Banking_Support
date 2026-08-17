"""
Unit & Integration Tests for Async Database Engine, Models, and Repositories.
"""

import pytest

try:
    import aiosqlite  # noqa: F401
    import pytest_asyncio
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    _ASYNC_TEST_AVAILABLE = True
except ImportError:
    _ASYNC_TEST_AVAILABLE = False
    pytest_asyncio = None

pytestmark = pytest.mark.skipif(
    not _ASYNC_TEST_AVAILABLE,
    reason="asyncio database test dependencies (pytest_asyncio, aiosqlite) not installed locally",
)

from datetime import datetime, timezone

from database.models import AccountModel, Base, CardModel, UserModel
from database.repositories.account_repository import AccountRepository
from database.repositories.card_repository import CardRepository
from database.repositories.user_repository import UserRepository

fixture_decorator = pytest_asyncio.fixture if _ASYNC_TEST_AVAILABLE else pytest.fixture


@fixture_decorator
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


async_test = pytest.mark.asyncio if _ASYNC_TEST_AVAILABLE else (lambda f: f)


@async_test
async def test_user_repository_crud_and_lockout(async_session):
    repo = UserRepository(async_session)
    user = UserModel(
        user_id="U9999",
        first_name="Test",
        last_name="User",
        email="test.user@bank.com",
        pin_hash="hashed_pin",
        failed_attempts=0,
        created_at=datetime.now(timezone.utc),
    )
    await repo.create(user)

    fetched = await repo.get_by_id("U9999")
    assert fetched is not None
    assert fetched.email == "test.user@bank.com"

    # Test lockout after failed attempts
    updated = await repo.increment_failed_attempts(
        "U9999", max_attempts=3, lockout_minutes=15
    )
    assert updated.failed_attempts == 1
    assert updated.locked_until is None

    await repo.increment_failed_attempts("U9999", max_attempts=3, lockout_minutes=15)
    updated = await repo.increment_failed_attempts(
        "U9999", max_attempts=3, lockout_minutes=15
    )
    assert updated.failed_attempts == 3
    assert updated.locked_until is not None

    # Reset
    reset_user = await repo.reset_failed_attempts("U9999")
    assert reset_user.failed_attempts == 0
    assert reset_user.locked_until is None


@async_test
async def test_account_and_card_repositories(async_session):
    user_repo = UserRepository(async_session)
    acc_repo = AccountRepository(async_session)
    card_repo = CardRepository(async_session)

    user = UserModel(
        user_id="U8888",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@bank.com",
        pin_hash="hash",
        created_at=datetime.now(timezone.utc),
    )
    await user_repo.create(user)

    account = AccountModel(
        account_id="A8888",
        user_id="U8888",
        account_type="checking",
        balance_paise=150000,
        currency="INR",
        is_active=1,
    )
    await acc_repo.create(account)

    card = CardModel(
        card_id="C8888",
        account_id="A8888",
        last4="4321",
        status="active",
    )
    await card_repo.create(card)

    cards = await card_repo.list_user_cards("U8888")
    assert len(cards) == 1
    assert cards[0].last4 == "4321"

    ok = await card_repo.update_status("C8888", "locked")
    assert ok is True
    updated_card = await card_repo.get_by_id("C8888")
    assert updated_card.status == "locked"
