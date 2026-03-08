from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_KEY_DEFAULTS = frozenset({
    "CHANGE_ME_TO_RANDOM_64_CHAR_STRING",
    "changeme",
    "secret",
    "test",
})


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
    registration_enabled: bool = False

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        if self.environment == "production":
            if self.secret_key in _INSECURE_KEY_DEFAULTS:
                raise ValueError(
                    "SECRET_KEY must be changed from its default value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            if len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters in production."
                )
        return self

    # External APIs
    polygon_api_key: str = ""
    fred_api_key: str = ""
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

    # Database pool
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Logging
    log_level: str = "INFO"

    # Data retention (days)
    retention_article_text_days: int = 90
    retention_scrape_log_days: int = 30
    retention_alert_log_days: int = 90
    retention_signal_days: int = 180
    retention_sentiment_days: int = 365

    # FinBERT
    finbert_model_path: str = "ProsusAI/finbert"
    finbert_batch_size: int = 16
    finbert_max_length: int = 512

    # Duplicate detection
    duplicate_similarity_threshold: float = 85.0

    # ML ensemble
    ml_ensemble_enabled: bool = False
    ml_min_training_samples: int = 100
    ml_validation_split: float = 0.2
    ml_model_dir: str = "/opt/stock-predictor/backend/ml_models"
    ml_retrain_interval_days: int = 7
    ml_confidence_threshold: float = 0.55

    # Options flow
    options_flow_enabled: bool = False
    options_fetch_delay: float = 0.5
    options_max_expirations: int = 3
    options_min_volume: int = 50
    options_baseline_days: int = 20
    retention_options_days: int = 180

    # Signal feedback loop
    feedback_enabled: bool = True
    feedback_evaluation_windows: str = "1,3,5"
    feedback_min_samples: int = 50
    feedback_weight_min: float = 0.05
    feedback_weight_max: float = 0.60
    feedback_lookback_days: int = 90

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def feedback_windows_list(self) -> list[int]:
        return [int(w.strip()) for w in self.feedback_evaluation_windows.split(",")]


# Source credibility weights for sentiment scoring.
# Higher = more reliable source. Used as multiplier in sentiment_momentum.
SOURCE_CREDIBILITY: dict[str, float] = {
    "sec_edgar": 1.0,
    "fred": 0.9,
    "reuters_rss": 0.9,
    "marketwatch": 0.8,
    "yahoo_finance": 0.75,
    "finviz": 0.7,
    "google_news": 0.65,
    "reddit_stocks": 0.4,
    "reddit_wallstreetbets": 0.35,
}
DEFAULT_SOURCE_CREDIBILITY = 0.5


settings = Settings()
