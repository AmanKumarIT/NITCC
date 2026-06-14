"""
NITCC Shared Configuration — loads from environment variables / .env file.
All agent microservices import settings from here.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional, Dict


class Settings(BaseSettings):
    # Application
    app_env: str = Field("development", alias="APP_ENV")
    app_secret_key: str = Field(..., alias="APP_SECRET_KEY")
    app_debug: bool = Field(False, alias="APP_DEBUG")
    app_cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        alias="APP_CORS_ORIGINS"
    )
    demo_users: List[dict[str, str]] = Field(
        default_factory=list,
        alias="DEMO_USERS"
    )

    # MongoDB Atlas
    mongodb_uri: str = Field(..., alias="MONGODB_URI")
    mongodb_db_name: str = Field("nitcc", alias="MONGODB_DB_NAME")

    # Kafka
    kafka_bootstrap_servers: str = Field("localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_schema_registry_url: str = Field("http://localhost:8081", alias="KAFKA_SCHEMA_REGISTRY_URL")
    kafka_security_protocol: str = Field("PLAINTEXT", alias="KAFKA_SECURITY_PROTOCOL")

    # Redis
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")
    redis_password: Optional[str] = Field(None, alias="REDIS_PASSWORD")
    redis_db: int = Field(0, alias="REDIS_DB")

    # LLM Provider
    llm_provider: str = Field("openai", alias="LLM_PROVIDER")
    llm_model: str = Field("gpt-4o", alias="LLM_MODEL")
    llm_api_key: str = Field("", alias="LLM_API_KEY")
    llm_max_tokens: int = Field(4096, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(0.2, alias="LLM_TEMPERATURE")

    # OpenWeather
    openweather_api_key: str = Field("", alias="OPENWEATHER_API_KEY")
    openweather_base_url: str = Field(
        "https://api.openweathermap.org/data/3.0", alias="OPENWEATHER_BASE_URL"
    )

    # IMD
    imd_api_url: str = Field("https://mausam.imd.gov.in", alias="IMD_API_URL")
    imd_api_key: str = Field("", alias="IMD_API_KEY")

    # ISRO Bhuvan
    bhuvan_wms_url: str = Field("", alias="BHUVAN_WMS_URL")
    bhuvan_wfs_url: str = Field("", alias="BHUVAN_WFS_URL")
    bhuvan_api_key: str = Field("", alias="BHUVAN_API_KEY")

    # NASA Earthdata
    nasa_earthdata_username: str = Field("", alias="NASA_EARTHDATA_USERNAME")
    nasa_earthdata_password: str = Field("", alias="NASA_EARTHDATA_PASSWORD")
    nasa_earthdata_base_url: str = Field(
        "https://ladsweb.modaps.eosdis.nasa.gov/api/v2", alias="NASA_EARTHDATA_BASE_URL"
    )

    # Railway NTES
    ntes_api_key: str = Field("", alias="NTES_API_KEY")
    ntes_api_base_url: str = Field("", alias="NTES_API_BASE_URL")

    # Railway FOIS
    fois_api_key: str = Field("", alias="FOIS_API_KEY")
    fois_api_base_url: str = Field("", alias="FOIS_API_BASE_URL")

    # Notifications
    twilio_account_sid: str = Field("", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field("", alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: str = Field("", alias="TWILIO_FROM_NUMBER")
    smtp_host: str = Field("smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_username: str = Field("", alias="SMTP_USERNAME")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field("nitcc-alerts@example.gov.in", alias="SMTP_FROM_EMAIL")

    # MLflow
    mlflow_tracking_uri: str = Field("http://localhost:5000", alias="MLFLOW_TRACKING_URI")
    mlflow_experiment_name: str = Field("nitcc_models", alias="MLFLOW_EXPERIMENT_NAME")

    # Security
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(60, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    mfa_issuer: str = Field("NITCC", alias="MFA_ISSUER")

    # Rate Limiting
    rate_limit_per_minute: int = Field(1000, alias="RATE_LIMIT_PER_MINUTE")

    # Google Earth Engine (SatEye Agent)
    gee_service_account_json: str = Field("", alias="GEE_SERVICE_ACCOUNT_JSON")

    # Mapbox
    mapbox_access_token: str = Field("", alias="MAPBOX_ACCESS_TOKEN")

    # Observability
    otel_exporter_otlp_endpoint: str = Field(
        "http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field("nitcc-gateway", alias="OTEL_SERVICE_NAME")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


def _load_settings() -> Settings:
    """Lazy-load settings so import never crashes before .env is created."""
    try:
        return Settings()
    except Exception:
        # Provide safe defaults when .env is missing (e.g. during tests/import)
        return Settings(
            APP_SECRET_KEY="dev-secret-change-me-in-production-32chars",
            MONGODB_URI="mongodb://localhost:27017",
        )


class _SettingsProxy:
    """Proxy that defers construction until first attribute access."""
    _instance: Optional[Settings] = None

    def __getattr__(self, name: str):
        if _SettingsProxy._instance is None:
            _SettingsProxy._instance = _load_settings()
        return getattr(_SettingsProxy._instance, name)


settings = _SettingsProxy()  # type: ignore
