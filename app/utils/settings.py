from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

class Settings:

    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "agentic")

    meta_whatsapp_token: str | None = os.getenv("META_WHATSAPP_TOKEN")
    meta_whatsapp_phone_number_id: str | None = os.getenv("META_WHATSAPP_PHONE_NUMBER_ID")
    meta_whatsapp_verify_token: str | None = os.getenv("META_WHATSAPP_VERIFY_TOKEN")

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")
    model: str = os.getenv("MODEL", "gpt-4o-mini")

    message_history_limit: int = int(os.getenv("MESSAGE_HISTORY_LIMIT", "20"))
    message_consolidation_timeout: int = int(os.getenv("MESSAGE_CONSOLIDATION_TIMEOUT", "60"))
    
    min_response_delay: int = int(os.getenv("MIN_RESPONSE_DELAY", "10"))
    max_response_delay: int = int(os.getenv("MAX_RESPONSE_DELAY", "45"))

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

settings = Settings()

def _load_prompt_file(filename: str) -> str:
    instructions_path = Path(__file__).parent.parent / "instructions" / filename
    if not instructions_path.exists():
        return ""
    return instructions_path.read_text(encoding="utf-8")

@lru_cache
def load_system_prompt() -> str:
    return _load_prompt_file("system_prompt_qualificacao.md")

@lru_cache
def load_lead_prompt() -> str:
    return _load_prompt_file("system_prompt_lead.md")

@lru_cache
def load_scoring_prompt() -> str:
    return _load_prompt_file("system_prompt_scoring.md")

