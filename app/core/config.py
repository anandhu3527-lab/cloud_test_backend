import os
from typing import Any, Dict, List, Optional, Union
from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.constants import EnvironmentType

class Settings(BaseSettings):
    APP_NAME: str = "CRYVEX Cloud"
    APP_VERSION: str = "0.1.0"
    APP_ENV: EnvironmentType = Field(default="development")
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str

    # Security / JWT
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    CLOUD_JWT_AUDIENCE: str = "cryvex-cloud"
    
    # CORS
    CORS_ORIGINS: List[str] = []

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Logging
    LOG_LEVEL: str = "INFO"

    # Auth Defaults
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # Security
    TRUSTED_HOSTS: List[str] = ["*"]
    
    @field_validator("TRUSTED_HOSTS", mode="before")
    @classmethod
    def assemble_trusted_hosts(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # ShopFlow Integration
    SHOPFLOW_BASE_URL: str = "http://localhost:8000"
    SHOPFLOW_SERVICE_TOKEN: str = ""
    SHOPFLOW_TIMEOUT_SECONDS: float = 30.0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


def get_settings() -> Settings:
    settings = Settings()
    
    # Validation for production
    if settings.APP_ENV == "production":
        if settings.DEBUG:
            raise ValueError("DEBUG must be False in production environment")
        
        if not settings.CORS_ORIGINS or "*" in settings.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS must be explicitly defined without wildcards in production")
            
        if not settings.TRUSTED_HOSTS or "*" in settings.TRUSTED_HOSTS:
            raise ValueError("TRUSTED_HOSTS must be explicitly defined without wildcards in production")
    
    return settings

settings = get_settings()
