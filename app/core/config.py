from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"

    mistral_api_key: str | None = None
    openai_api_key: str | None = None

    sqlite_path: str = "./data/app.db"
    chroma_persist_dir: str = "./data/chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
