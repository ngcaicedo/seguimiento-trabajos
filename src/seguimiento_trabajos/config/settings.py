import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "seguimiento-trabajos"
    database_url: str | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            service_name=os.environ.get("SEGUIMIENTO_SERVICE_NAME", "seguimiento-trabajos"),
            database_url=os.environ.get("SEGUIMIENTO_DATABASE_URL", "").strip() or None,
        )
