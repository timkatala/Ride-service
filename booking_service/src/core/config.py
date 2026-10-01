from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5432/booking"
    redis_url: str = "redis://localhost:6379/0"
    events_stream: str = "booking-events"

    provider_url: str = "http://localhost:8001"
    callback_secret: str = "dev-secret"
    provider_timeout_seconds: float = 3.0

    driver_assignment_timeout_seconds: int = 600
    revenue_account: str = "revenue:rides"

    batch_size: int = 20
    submit_lease_seconds: int = 30
    submit_max_backoff_seconds: int = 60
    reconcile_stale_after_seconds: int = 120


settings = Settings()
