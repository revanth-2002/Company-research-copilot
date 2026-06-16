from functools import lru_cache

from dotenv import load_dotenv
import os 

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ZyLabs AI Research Copilot"
    database_url: str = os.getenv("DATABASE_URL")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    clerk_domain: str = os.getenv("CLERK_DOMAIN")
    cors_origins: str = "https://company-research-copilot-48tw1swnz-revanth2909.vercel.app/"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
