"""
Application settings loaded from .env via pydantic-settings.
All config is centralised here — import `settings` anywhere.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # Security
    api_key: str = "change-me"

    # Database
    database_url: str = "sqlite+aiosqlite:///./facebook_api.db"

    # Token encryption (Fernet key for storing FB access tokens at rest)
    token_encrypt_key: str = ""

    # Facebook Graph API
    fb_graph_api_version: str = "v19.0"
    fb_default_post_limit: int = 25

    # Email Alerting
    admin_email: str = "admin@example.com"
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    @property
    def fb_graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.fb_graph_api_version}"


settings = Settings()
