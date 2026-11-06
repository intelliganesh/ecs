from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ECS API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins_value: str = Field("http://localhost:5173", validation_alias="CORS_ORIGINS")
    db_dialect: str = "mssql"
    db_host: str = "127.0.0.1"
    db_port: int = 1433
    db_name: str = "generate_report"
    db_user: str = "sa"
    db_password: str = "change-me"
    mssql_driver: str = "ODBC Driver 18 for SQL Server"
    mssql_trust_server_certificate: bool = True

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

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

