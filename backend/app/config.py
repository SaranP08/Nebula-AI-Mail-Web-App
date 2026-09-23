"""Application configuration via Pydantic Settings.

All values are read from environment variables (or a .env file).
Import `settings` from this module everywhere you need config.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Security
    secret_key: str = "dev-secret-change-me"

    # Google OAuth2
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"

    # CORS / cookies / hosting
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    frontend_dist_dir: str = ""
    cookie_secure: bool = False
    cookie_same_site: str = "lax"

    # Database
    database_url: str = "sqlite:///./app.db"

    # Real-time sync
    gmail_pubsub_topic: str = ""
    gmail_webhook_secret: str = ""
    sync_mode: str = "pubsub"  # "pubsub" or "poll"

    # AI Assistant (LiteLLM)
    llm_model: str = "vertex_ai/gemini-2.5-flash"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    @property
    def google_scopes(self) -> list[str]:
        return [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.send",
        ]


settings = Settings()
