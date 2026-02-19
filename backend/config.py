from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    OPENAI_API_KEY: str

    # Models
    OPENAI_MODEL: str = "gpt-4.1-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # RAG configuration
    REGULATIONS_DIR: str = "./regulations"
    CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP: int = 250

    # GitHub access (optional)
    GITHUB_TOKEN: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
