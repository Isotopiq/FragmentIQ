from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FragmentIQ"
    environment: str = "development"
    database_url: str = "sqlite:///./data/database/fragmentiq.db"
    storage_root: Path = Path("./data")
    upload_max_mb: int = 2048
    mock_execution: bool = True
    mock_job_step_seconds: float = 0.05
    job_timeout_seconds: int = 7200
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Engine binaries / execution flags
    mzmine_binary: str = "mzmine"
    mzmine_batch_flag: str = "-batch"
    mzmine_memory_mode: str = "none"
    mzmine_temp_dir: Path = Path("/tmp/mzmine")

    sirius_binary: str = "sirius"
    sirius_username: str = ""
    sirius_password: str = ""
    sirius_api_url: str = ""
    sirius_use_api: bool = False
    sirius_accept_terms: bool = False

    cfm_binary: str = "cfm-predict"
    cfm_train_binary: str = "cfm-train"
    cfm_id_binary: str = "cfm-id"

    # Engine asset directories
    ms2query_library_dir: Path = Path("./data/libraries/ms2query")
    dreams_cache_dir: Path = Path("./data/models/dreams")
    matchms_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.storage_root / "uploads"

    @property
    def results_dir(self) -> Path:
        return self.storage_root / "results"

    @property
    def libraries_dir(self) -> Path:
        return self.storage_root / "libraries"

    @property
    def models_dir(self) -> Path:
        return self.storage_root / "models"

    @property
    def logs_dir(self) -> Path:
        return self.storage_root / "logs"

    @property
    def database_dir(self) -> Path:
        return self.storage_root / "database"

    @property
    def metadata_dir(self) -> Path:
        return self.storage_root / "metadata"

    @property
    def reports_dir(self) -> Path:
        return self.storage_root / "reports"

    @property
    def workflow_configs_dir(self) -> Path:
        return self.storage_root / "workflow_configs"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.upload_max_mb * 1024 * 1024

    def project_dir(self, project_id: int) -> Path:
        path = self.uploads_dir / f"project_{project_id}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_directories(self) -> None:
        for path in [
            self.uploads_dir,
            self.results_dir,
            self.libraries_dir,
            self.models_dir,
            self.logs_dir,
            self.database_dir,
            self.workflow_configs_dir,
            self.metadata_dir,
            self.reports_dir,
            self.ms2query_library_dir,
            self.dreams_cache_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    value = Settings()
    value.ensure_directories()
    return value


settings = get_settings()
