import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://booking:booking@localhost:5432/booking_test")
os.environ.setdefault("CALLBACK_SECRET", "test-secret")
