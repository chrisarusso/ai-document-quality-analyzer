"""Configuration management for Document Quality Analyzer."""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Fathom API
    fathom_api_key: str = Field(default="", description="Fathom API key for transcript access")
    fathom_api_base: str = Field(default="https://api.fathom.ai/external/v1", description="Fathom API base URL")

    # LLM Providers
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    google_api_key: str = Field(default="", description="Google Gemini API key")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key for multi-model access")

    # Slack
    slack_bot_token: str = Field(default="", description="Slack bot OAuth token")
    slack_channel: str = Field(default="document-analyzer-test", description="Slack channel for notifications")

    # Google OAuth
    google_client_id: str = Field(default="", description="Google OAuth client ID")
    google_client_secret: str = Field(default="", description="Google OAuth client secret")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
