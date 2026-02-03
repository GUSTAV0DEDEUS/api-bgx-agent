from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Configurações da aplicação carregadas do ambiente."""

    # Database
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "agentic")

    # WhatsApp Meta API
    meta_whatsapp_token: str | None = os.getenv("META_WHATSAPP_TOKEN")
    meta_whatsapp_phone_number_id: str | None = os.getenv("META_WHATSAPP_PHONE_NUMBER_ID")
    meta_whatsapp_verify_token: str | None = os.getenv("META_WHATSAPP_VERIFY_TOKEN")

    # AI Services
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Message Handler Config
    message_history_limit: int = int(os.getenv("MESSAGE_HISTORY_LIMIT", "20"))
    message_consolidation_timeout: int = int(os.getenv("MESSAGE_CONSOLIDATION_TIMEOUT", "60"))

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()


@lru_cache
def load_system_prompt() -> str:
    """Carrega o system prompt do arquivo instructions/system_prompt.md"""
    instructions_path = Path(__file__).parent.parent / "instructions" / "system_prompt.md"
    if not instructions_path.exists():
        return ""
    return instructions_path.read_text(encoding="utf-8")
