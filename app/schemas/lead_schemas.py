from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

class LeadBase(BaseModel):
    nome_cliente: str | None = None
    nome_empresa: str | None = None
    cargo: str | None = None
    telefone: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

class LeadCreate(LeadBase):
    conversation_id: uuid.UUID
    profile_id: uuid.UUID
    score: int | None = Field(default=None, ge=0, le=100)

class LeadUpdate(BaseModel):
    nome_cliente: str | None = None
    nome_empresa: str | None = None
    cargo: str | None = None
    telefone: str | None = None
    tags: list[str] | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    status: str | None = Field(default=None, pattern="^(quente|morno|frio)$")
    
    step_novo_lead: bool | None = None
    step_primeiro_contato: bool | None = None
    step_negociacao: bool | None = None
    step_orcamento_realizado: bool | None = None
    step_orcamento_aceito: bool | None = None
    step_orcamento_recusado: bool | None = None
    step_venda_convertida: bool | None = None
    step_venda_perdida: bool | None = None

class LeadSteps(BaseModel):
    novo_lead: bool
    primeiro_contato: bool
    negociacao: bool
    orcamento_realizado: bool
    orcamento_aceito: bool
    orcamento_recusado: bool
    venda_convertida: bool
    venda_perdida: bool

class LeadResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    profile_id: uuid.UUID
    nome_cliente: str | None
    nome_empresa: str | None
    cargo: str | None
    telefone: str | None
    tags: list[str]
    score: int | None
    notes: str | None
    status: str
    
    step_novo_lead: bool
    step_primeiro_contato: bool
    step_negociacao: bool
    step_orcamento_realizado: bool
    step_orcamento_aceito: bool
    step_orcamento_recusado: bool
    step_venda_convertida: bool
    step_venda_perdida: bool
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LeadsListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    per_page: int
    pages: int

class LeadMetricsResponse(BaseModel):
    total: int
    by_step: dict[str, int]
    by_status: dict[str, int]
    conversion_rate: float
