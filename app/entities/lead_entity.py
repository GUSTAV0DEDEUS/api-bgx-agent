from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.utils.db import Base

class LeadStatus:
    QUENTE = "quente"    # Score >= 70 — alta probabilidade de conversão
    MORNO = "morno"      # Score 40-69 — interesse moderado (default)
    FRIO = "frio"        # Score < 40 — baixo interesse / sinais negativos

class Lead(Base):

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), unique=True, nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id"), index=True, nullable=False
    )

    nome_cliente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nome_empresa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cargo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default=LeadStatus.MORNO)

    step_novo_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    step_primeiro_contato: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    step_negociacao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    step_orcamento_realizado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    step_orcamento_aceito: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    step_orcamento_recusado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    step_venda_convertida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    step_venda_perdida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversation = relationship("Conversation", back_populates="lead")
    profile = relationship("Profile", back_populates="leads")
