from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.utils.db import Base


class ToneEnum(str, Enum):
    PROFISSIONAL = "profissional"
    DESCONTRAIDO = "descontraido"
    TECNICO = "tecnico"
    AMIGAVEL = "amigavel"


class EmojiUsageEnum(str, Enum):
    SEMPRE = "sempre"
    MODERADO = "moderado"
    NUNCA = "nunca"


class ResponseStyleEnum(str, Enum):
    FORMAL = "formal"
    CONVERSACIONAL = "conversacional"
    CONSULTIVO = "consultivo"
    DIRETO = "direto"


class GreetingStyleEnum(str, Enum):
    CALOROSO = "caloroso"
    NEUTRO = "neutro"
    OBJETIVO = "objetivo"


class AgentConfig(Base):
    __tablename__ = "agent_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tone: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ToneEnum.PROFISSIONAL.value
    )
    use_emojis: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EmojiUsageEnum.MODERADO.value
    )
    response_style: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ResponseStyleEnum.CONVERSACIONAL.value
    )
    greeting_style: Mapped[str] = mapped_column(
        String(32), nullable=False, default=GreetingStyleEnum.CALOROSO.value
    )
    max_message_length: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
