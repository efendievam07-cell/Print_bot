from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = "sqlite+aiosqlite:///./optop.db"
    bot_token: str
    api_secret_token: str
    control_chat_id: int
    admin_id: int | None = None
    telegram_proxy: str | None = None


settings = Settings()
