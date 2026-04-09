from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    semantris_llm_provider: Literal["gemini", "openai"] = "gemini"
    semantris_vocab_file: str = "assets/aviation_1.txt"
    semantris_debug_blocks_llm: bool = False
    semantris_debug_openai_llm: bool = False
    semantris_skip_llm_startup_probe: bool = False
    semantris_use_fake_ranker: bool = False

    flask_debug: bool = True
    flask_secret_key: str | None = None
    port: int = 5001

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash-lite"

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-5.2-mini"

    semantris_cache_backend: Literal["none", "memory"] = "memory"
    semantris_cache_max_entries: int = 512

    semantris_persistence_backend: Literal["none", "sqlite"] = "sqlite"
    semantris_database_url: str = "sqlite:///instance/semantris_plus.sqlite3"

    semantris_run_store_enabled: bool = True

    @field_validator("semantris_vocab_file")
    @classmethod
    def _strip_vocab_file(cls, value: str) -> str:
        return value.strip()

    @field_validator("openai_base_url")
    @classmethod
    def _normalize_openai_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("flask_secret_key")
    @classmethod
    def _normalize_secret_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def assets_dir(self) -> Path:
        return self.base_dir / "assets"

    @property
    def default_vocab_file(self) -> Path:
        return self.assets_dir / "aviation_1.txt"

    @property
    def configured_vocab_file(self) -> Path:
        configured = Path(self.semantris_vocab_file)
        if configured.is_absolute():
            return configured
        return self.base_dir / configured

    @property
    def restriction_rules_file(self) -> Path:
        return self.assets_dir / "restriction_rules.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
