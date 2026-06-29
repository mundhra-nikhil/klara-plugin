from pydantic import BaseModel
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    driver: str = "postgresql+asyncpg"
    host: str = "localhost"
    port: int = 5432
    database: str = "grss_db"
    user: str = "grss_user"
    pool_size: int = 20
    max_overflow: int = 10


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/0"


@dataclass
class AzureOpenAIConfig:
    endpoint: str = ""
    api_key: str = ""
    deployment: str = "gpt-4"
    api_version: str = "2024-02-15-preview"
