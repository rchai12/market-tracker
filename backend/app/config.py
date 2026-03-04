from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://sp_user:changeme@localhost:5432/stock_predictor"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "CHANGE_ME_TO_RANDOM_64_CHAR_STRING"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # App
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # External APIs
    polygon_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "stock-predictor/1.0"

    # Alerts
    discord_webhook_url: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_from_email: str = ""

    # FinBERT
    finbert_model_path: str = "ProsusAI/finbert"
    finbert_batch_size: int = 16
    finbert_max_length: int = 512

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]


settings = Settings()
