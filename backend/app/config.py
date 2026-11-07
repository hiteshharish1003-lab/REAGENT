from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

# OpenAI-compatible endpoints and default models for the free providers.
# Free-tier model names change over time; override with FAST_MODEL / WRITER_MODEL in .env.
PROVIDERS = {
    "anthropic": {"fast": "claude-haiku-5-5", "writer": "claude-sonnet-5-5"},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "fast": "gemini-3.5-flash",
        "writer": "gemini-3.5-flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "fast": "openai/gpt-oss-20b",
        "writer": "openai/gpt-oss-120b",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Set ONE of these. If several are set, the first in this order wins.
    anthropic_api_key: str = ""
    gemini_api_key: str = ""  # free tier: aistudio.google.com/apikey
    groq_api_key: str = ""  # free tier: console.groq.com/keys
    tavily_api_key: str = ""

    # Optional overrides; left empty they default to the provider's models above.
    fast_model: str = ""
    writer_model: str = ""

    # Per-run budgets keep cost and laptop load bounded.
    max_subquestions: int = 4
    results_per_search: int = 4
    max_searches_per_run: int = 8
    max_output_tokens: int = 6000
    search_concurrency: int = 2

    db_path: Path = ROOT / "data" / "docuresearch.db"
    cache_dir: Path = ROOT / "data" / "cache"

    @property
    def provider(self) -> str:
        if self.anthropic_api_key:
            return "anthropic"
        if self.gemini_api_key:
            return "gemini"
        if self.groq_api_key:
            return "groq"
        return ""

    @property
    def compat_providers(self) -> list[str]:
        """Free OpenAI-compatible providers with a key set, in fallback order."""
        return [p for p in ("gemini", "groq") if self.key_for(p)]

    def key_for(self, provider: str) -> str:
        return {"anthropic": self.anthropic_api_key, "gemini": self.gemini_api_key, "groq": self.groq_api_key}.get(
            provider, ""
        )

    @property
    def api_key(self) -> str:
        return {"anthropic": self.anthropic_api_key, "gemini": self.gemini_api_key, "groq": self.groq_api_key}.get(
            self.provider, ""
        )

    @property
    def base_url(self) -> str:
        return PROVIDERS.get(self.provider, {}).get("base_url", "")

    @model_validator(mode="after")
    def _default_models(self):
        defaults = PROVIDERS.get(self.provider)
        if defaults:
            self.fast_model = self.fast_model or defaults["fast"]
            self.writer_model = self.writer_model or defaults["writer"]
        return self

    @property
    def mock_llm(self) -> bool:
        return not self.provider

    @property
    def mock_search(self) -> bool:
        return not self.tavily_api_key


settings = Settings()
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
settings.cache_dir.mkdir(parents=True, exist_ok=True)
