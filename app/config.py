"""
GovFlow AI — Application configuration.

Settings are loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    APP_TITLE: str = "GovFlow AI"
    APP_VERSION: str = "0.1.0"

    # Langflow — leave blank to use deterministic stubs
    LANGFLOW_BASE_URL: str = "http://localhost:7860"
    LANGFLOW_FLOW_ID_PARSER: str = ""
    LANGFLOW_FLOW_ID_SEVERITY: str = ""
    LANGFLOW_FLOW_ID_BRIEF: str = ""
    LANGFLOW_API_KEY: str = ""


settings = Settings()
