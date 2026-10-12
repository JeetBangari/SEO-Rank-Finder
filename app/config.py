from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "SERP Engine"
    REDIS_URL: str = "redis://localhost:6379/0"
    PROXY_POOL: List[str] = []

    class Config:
        env_file = ".env"

settings = Settings()