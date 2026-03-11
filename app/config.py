from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dashboard Builder"
    app_env: str = "dev"
    database_url: str = "sqlite:///data/dashboard_builder.db"
    scheduler_tick_seconds: int = 60

    admin_username: str = "admin"
    admin_password: str = "change-me"
    session_secret: str = "change-this-session-secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()