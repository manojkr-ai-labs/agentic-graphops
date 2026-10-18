"""Environment configuration. Secrets are never included in repr or logs."""

from pathlib import Path

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Reads architecture section 4. Missing required values fail startup."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: SecretStr = SecretStr("")
    graph_prefix: str = "graphops_"
    llm_base_url: str
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str
    query_timeout_ms: int = 2000
    max_depth: int = 4
    max_nodes: int = 50
    max_rels: int = 100
    max_agent_iterations: int = 8
    log_level: str = "INFO"

    @field_validator(
        "falkordb_host",
        "graph_prefix",
        "llm_base_url",
        "llm_model",
        mode="before",
    )
    @classmethod
    def reject_blank(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("must not be empty")
            return stripped
        return value

    @field_validator("llm_base_url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("must be an http(s) URL")
        return value

    @field_validator("falkordb_port")
    @classmethod
    def require_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("must be a TCP port")
        return value

    @field_validator(
        "query_timeout_ms",
        "max_depth",
        "max_nodes",
        "max_rels",
        "max_agent_iterations",
    )
    @classmethod
    def require_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be >= 1")
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("log_level")
    @classmethod
    def require_known_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if value not in allowed:
            raise ValueError("must be DEBUG, INFO, WARNING, or ERROR")
        return value

    def __repr__(self) -> str:
        return (
            f"Settings(falkordb_host={self.falkordb_host!r}, "
            f"falkordb_port={self.falkordb_port}, "
            f"graph_prefix={self.graph_prefix!r}, "
            f"llm_model={self.llm_model!r})"
        )


def load_settings() -> Settings:
    env_file = _ENV_FILE if _ENV_FILE.is_file() else None
    return Settings(_env_file=env_file)


def configuration_error(exc: ValidationError) -> str:
    """Field names and error types only. Values can be secrets."""

    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err["loc"]) or "settings"
        parts.append(f"{loc} ({err['type']})")
    return "startup failed: " + ", ".join(parts)
