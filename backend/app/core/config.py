from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = BACKEND_ROOT / "data"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Paper Search Agent"
    app_env: str = "development"
    api_prefix: str = "/api"

    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        alias="DEEPSEEK_BASE_URL",
    )
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    local_embedding_dimensions: int = Field(
        default=384,
        alias="LOCAL_EMBEDDING_DIMENSIONS",
    )

    sqlite_path: str = Field(
        default=str(DATA_DIR / "paper_agent.sqlite3"),
        alias="SQLITE_PATH",
    )
    chroma_persist_dir: str = Field(
        default=str(DATA_DIR / "chroma"),
        alias="CHROMA_PERSIST_DIR",
    )

    arxiv_api_url: str = Field(
        default="https://export.arxiv.org/api/query",
        alias="ARXIV_API_URL",
    )
    arxiv_default_max_results: int = Field(default=5, alias="ARXIV_DEFAULT_MAX_RESULTS")
    request_timeout_seconds: float = Field(default=30.0, alias="REQUEST_TIMEOUT_SECONDS")
    cache_ttl_seconds: int = Field(default=3600, alias="CACHE_TTL_SECONDS")

    chunk_size: int = Field(default=900, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="CHUNK_OVERLAP")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    max_paper_chars: int = Field(default=12000, alias="MAX_PAPER_CHARS")
    short_term_window: int = Field(default=16, alias="SHORT_TERM_WINDOW")
    conversation_summary_threshold: int = Field(
        default=10,
        alias="CONVERSATION_SUMMARY_THRESHOLD",
    )

    cors_origins: str = Field(
        default="http://localhost:2299,http://127.0.0.1:2299",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlite_file(self) -> Path:
        path = Path(self.sqlite_path).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def chroma_dir(self) -> Path:
        path = Path(self.chroma_persist_dir).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
