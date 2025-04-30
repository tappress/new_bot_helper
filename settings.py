from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    NEWS_API_KEY: str
    WEATHER_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    API_BASE_URL: str = "http://localhost:8000"


settings = Settings()
