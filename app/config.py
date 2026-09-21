from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ects_env: str = "development"
    ects_data_dir: Path = Path("./data")
    ects_repo_root: Path = Path(".")
    database_url: str = "sqlite:///./data/ects.db"

    ects_api_host: str = "0.0.0.0"
    ects_api_port: int = 8080
    ects_api_token: str = "dev-token"
    ects_gpu_worker_token: str = "gpu-dev-token"

    ects_default_deadline_hour: int = 8
    ects_lease_minutes: int = 5

    google_service_account_file: str = ""
    drive_inbox_folder_id: str = ""
    drive_processing_folder_id: str = ""
    drive_finished_folder_id: str = ""
    drive_error_folder_id: str = ""

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_monthly_budget_eur: float = 20.0

    git_remote_url: str = "https://github.com/niknakmaniak/ects.git"
    git_user_name: str = "ECTS Bot"
    git_user_email: str = "ects@localhost"
    git_auto_push: bool = False

    gpu_worker_url: str = ""
    whisper_model: str = "large-v3"

    lora_min_sessions: int = 3
    lora_output_dir: Path = Path("./adapters")

    @property
    def sessions_dir(self) -> Path:
        return self.ects_repo_root / "subjects"

    @property
    def profiles_dir(self) -> Path:
        return self.ects_repo_root / "profiles"

    @property
    def latex_templates_dir(self) -> Path:
        return self.ects_repo_root / "templates" / "latex"

    @property
    def work_dir(self) -> Path:
        return self.ects_data_dir / "work"


@lru_cache
def get_settings() -> Settings:
    return Settings()
