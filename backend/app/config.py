"""Application configuration."""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenAI
    openai_api_key: str = "sk-placeholder"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Upload
    max_upload_size: int = 104857600  # 100MB
    max_files_per_batch: int = 20  # Max files per batch upload
    concurrent_limit: int = 20  # Max concurrent OCR requests
    batch_size: int = 3  # Number of images to process in each batch

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:3001"

    # App
    app_env: str = "development"
    log_level: str = "info"
    app_version: str = "1.0.0"

    # OpenAI Models
    openai_primary_model: str = "gpt-4o-2024-08-06"
    openai_fallback_model: str = "gpt-4o-mini-2024-07-18"

    # Processing
    pdf_render_dpi: int = 400  # Higher DPI for better OCR
    max_image_dimension: int = 4096
    fuzzy_match_threshold: int = 80  # Minimum similarity score for subject matching

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins from string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
