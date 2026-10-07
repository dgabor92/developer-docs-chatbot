from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    # Database
    database_url: str

    # Ollama
    ollama_url: str = 'http://localhost:11434'
    embedding_model: str = 'nomic-embed-text'

    # Anthropic
    anthropic_api_key: str
    llm_model: str = 'claude-haiku-4-5-20251001'

    # App
    cors_origins: list[str] = ['http://localhost:5173', 'http://localhost:3000']
    log_level: str = 'INFO'
    environment: str = 'development'

    @field_validator('anthropic_api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == 'sk-ant-...':
            raise ValueError('ANTHROPIC_API_KEY must be set to a valid key')
        return v


settings = Settings()
