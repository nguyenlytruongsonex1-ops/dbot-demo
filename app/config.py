from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "dbot_demo"
    db_user: str = "dbot"
    db_password: str = "dbot"
    llm_mode: str = "mock"
    openai_api_key: str = ""
    openai_model_name: str = "gpt-4o-mini"
    openai_api_base: str = ""
    dbot_max_iterations: int = 8
    dbot_log_level: str = "INFO"
    incident_store_path: str = "data/incidents.json"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

@lru_cache
def get_settings() -> Settings:
    return Settings()
