from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "ECS API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins_value: str = Field("http://localhost:5173", validation_alias="CORS_ORIGINS")
    db_dialect: str = "mssql"
    db_host: str = "127.0.0.1"
    db_port: int = 1433
    db_name: str = "ecs"
    db_user: str = "sa"
    db_password: str = "change-me"
    mssql_driver: str = "ODBC Driver 18 for SQL Server"
    mssql_trust_server_certificate: bool = True
    scheduler_enabled: bool = True
    scheduler_timezone: str = "UTC"
    report_input_dir: Path = Path("report-input")
    report_output_dir: Path = Path("report-output")
    mail_enabled: bool = False
    mail_mailer: Literal["smtp"] = "smtp"
    mail_host: str = "smtp.gmail.com"
    mail_port: int = Field(465, ge=1, le=65535)
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_encryption: Literal["ssl", "tls"] = "ssl"
    mail_from_address: str = ""
    mail_from_name: str = "ECS Retirement Builder"

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", case_sensitive=False, extra="ignore")

    @model_validator(mode="after")
    def validate_mail_settings(self):
        if self.mail_enabled and not all((
            self.mail_host.strip(), self.mail_username.strip(),
            self.mail_password.get_secret_value().strip(), self.mail_from_address.strip(),
        )):
            raise ValueError("Set MAIL_HOST, MAIL_USERNAME, MAIL_PASSWORD and MAIL_FROM_ADDRESS to enable mail.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_value.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus

        driver = quote_plus(self.mssql_driver)
        password = quote_plus(self.db_password)
        trust = "yes" if self.mssql_trust_server_certificate else "no"
        return (
            f"mssql+pyodbc://{self.db_user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?driver={driver}&TrustServerCertificate={trust}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

