from functools import lru_cache
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "FashionStore API"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg2://fashionstore:fashionstore@localhost:5433/fashionstore",
        validation_alias="DATABASE_URL",
    )
    secret_key: str = Field(
        default="change-me-in-production",
        validation_alias="SECRET_KEY",
    )
    algorithm: str = Field(default="HS256", validation_alias="ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        gt=0,
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:4200",
            "http://127.0.0.1:4200",
        ]
    )
    ai_provider_mode: str = Field(default="disabled", validation_alias="AI_PROVIDER_MODE")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", validation_alias="GEMINI_MODEL")
    speech_provider_mode: str = Field(default="disabled", validation_alias="SPEECH_PROVIDER_MODE")
    google_speech_api_key: str | None = Field(default=None, validation_alias="GOOGLE_SPEECH_API_KEY")
    google_speech_language_code: str = Field(default="es-CO", validation_alias="GOOGLE_SPEECH_LANGUAGE_CODE")
    stripe_secret_key: str | None = Field(default=None, validation_alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, validation_alias="STRIPE_WEBHOOK_SECRET")
    stripe_api_base: str = Field(default="https://api.stripe.com/v1", validation_alias="STRIPE_API_BASE")
    payment_provider: str = Field(default="stripe", validation_alias="PAYMENT_PROVIDER")
    fiscal_provider: str = Field(default="not_configured", validation_alias="FISCAL_PROVIDER")
    # Documento fiscal simulado: el precio de la venta se interpreta con IVA incluido.
    fiscal_tax_rate: Decimal = Field(default=Decimal("0.19"), validation_alias="FISCAL_TAX_RATE", ge=0, lt=1)
    fiscal_issuer_name: str = Field(default="FashionStore S.A.S.", validation_alias="FISCAL_ISSUER_NAME")
    fiscal_issuer_tax_id: str | None = Field(default=None, validation_alias="FISCAL_ISSUER_TAX_ID")
    notification_provider: str = Field(default="not_configured", validation_alias="NOTIFICATION_PROVIDER")
    # Siembra de cuentas demo al arranque (contraseña admin123). Desactivar en producción real.
    seed_demo_users: bool = Field(default=True, validation_alias="SEED_DEMO_USERS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
