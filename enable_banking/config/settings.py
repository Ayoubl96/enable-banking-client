import os
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Enable Banking API Configuration
    enable_banking_private_key_path: str = Field(
        default="./keys/private_key.pem",
        env="ENABLE_BANKING_PRIVATE_KEY_PATH"
    )
    enable_banking_application_id: str = Field(
        ...,
        env="ENABLE_BANKING_APPLICATION_ID"
    )
    enable_banking_base_url: str = Field(
        default="https://api.enablebanking.com",
        env="ENABLE_BANKING_BASE_URL"
    )
    enable_banking_token_expiry_minutes: int = Field(
        default=60,
        env="ENABLE_BANKING_TOKEN_EXPIRY_MINUTES"
    )

    # API Server Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8080, env="API_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Optional Redis Configuration
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")

    # Development Settings
    debug: bool = Field(default=False, env="DEBUG")
    testing: bool = Field(default=False, env="TESTING")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("enable_banking_private_key_path")
    def validate_private_key_path(cls, v):
        """Validate that private key path exists if not in testing mode."""
        if not os.getenv("TESTING", "false").lower() == "true":
            path = Path(v)
            if not path.exists():
                raise ValueError(f"Private key file not found: {v}")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()


# Global settings instance
settings = Settings()
