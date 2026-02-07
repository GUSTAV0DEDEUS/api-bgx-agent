from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProfileWithTags(BaseModel):
    """Profile com tags para listagem."""
    id: uuid.UUID
    whatsapp_number: str
    first_name: str | None
    last_name: str | None
    display_name: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    """Resumo de conversa para listagem."""
    id: uuid.UUID
    status: str
    tags: list[str]
    closed_at: datetime | None
    closed_by: str | None
    closed_reason: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientDetailResponse(BaseModel):
    """Detalhes de um cliente com suas conversas."""
    profile: ProfileWithTags
    conversations: list[ConversationSummary]


class PaginatedResponse(BaseModel):
    """Resposta paginada genérica."""
    items: list
    total: int
    page: int
    per_page: int
    pages: int


class ClientsListResponse(BaseModel):
    """Resposta de listagem de clientes paginada."""
    items: list[ProfileWithTags]
    total: int
    page: int
    per_page: int
    pages: int


class MessageResponse(BaseModel):
    """Mensagem de uma conversa."""
    id: uuid.UUID
    role: str  # 'user' ou 'agent'
    content: str
    message_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class AddTagRequest(BaseModel):
    """Request para adicionar tag."""
    tag: str = Field(..., min_length=1, max_length=32)


class CloseConversationRequest(BaseModel):
    """Request para fechar uma conversa."""
    reason: str | None = Field(default=None, max_length=500, description="Motivo do encerramento")
