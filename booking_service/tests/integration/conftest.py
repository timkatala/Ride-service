from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from src.core.database import async_session, engine
from src.main import app
from tests.helpers import create_booking
from tests.integration.jobs import run_submission
from tests.stubs import StubProvider

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"

TABLES = [
    "ledger_entries",
    "booking_status_history",
    "provider_callbacks",
    "outbox",
    "bookings",
]


def alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    return config


@pytest.fixture(scope="session", autouse=True)
def database_schema():
    """Build the schema with the real migrations, starting from an empty database."""
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
async def dispose_engine(database_schema):
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(database_schema):
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def session_factory():
    return async_session


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def provider():
    return StubProvider()


@pytest.fixture
async def submitted_booking(client, provider):
    """A booking that the provider has accepted our request for (status `submitted`)."""
    booking = await create_booking(client)
    await run_submission(provider)
    response = await client.get(f"/bookings/{booking['id']}")
    assert response.json()["status"] == "submitted"
    return response.json()
