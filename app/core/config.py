from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "vehicle-core-service"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "mysql+aiomysql://vehicle_core:vehicle_core@core-db:3306/vehicle_core"
    jwt_secret: SecretStr = SecretStr("development-only-change-me-jwt")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    sales_service_url: str = "http://vehicle-sales-service:8000"
    sales_service_timeout_seconds: float = 5.0
    service_token: SecretStr = SecretStr("development-only-change-me-service")
    webhook_secret: SecretStr = SecretStr("development-only-change-me-webhook")

    @model_validator(mode="after")
    def reject_development_secrets_outside_development(self) -> "Settings":
        if self.app_env.lower() in {"development", "test"}:
            return self

        insecure = (
            self.jwt_secret.get_secret_value().startswith("development-only"),
            self.service_token.get_secret_value().startswith("development-only"),
            self.webhook_secret.get_secret_value().startswith("development-only"),
        )
        if any(insecure):
            raise ValueError("Os segredos padrão não podem ser usados fora de development/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
