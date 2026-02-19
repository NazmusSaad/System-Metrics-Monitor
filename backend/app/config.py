import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://metrics:metricspass@db:5432/metrics_monitor"
    collection_interval_seconds: int = 2
    machine_name: str = "local"

    # Health thresholds
    cpu_warn: float = 80
    cpu_crit: float = 95
    mem_warn: float = 80
    mem_crit: float = 95
    disk_warn: float = 85
    disk_crit: float = 95

    # V2: multi-device
    ingest_api_key: str = ""  # required in production; empty = no auth
    enable_local_collector: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
