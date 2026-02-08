from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dao import lead_dao
from app.schemas.lead_schemas import (
    LeadMetricsResponse,
    LeadResponse,
    LeadsListResponse,
    LeadUpdate,
)
from app.services.websocket_manager import ws_manager
from app.utils.db import get_db


router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get("/", response_model=LeadsListResponse)
def list_leads(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filtrar por temperatura (quente, morno, frio)"),
    step: str | None = Query(default=None, description="Filtrar por step do pipeline"),
    db: Session = Depends(get_db),
):
    """
    Lista todos os leads com paginação e filtros.
    
    Filtros opcionais:
    - status: Filtra por temperatura do lead (quente, morno, frio)
    - step: Filtra por step do pipeline (step_novo_lead, step_primeiro_contato, etc.)
    
    Leads com soft delete não são retornados.
    """
    leads, total = lead_dao.get_all_paginated(db, page, per_page, status, step)
    
    items = [
        LeadResponse(
            id=lead.id,
            conversation_id=lead.conversation_id,
            profile_id=lead.profile_id,
            nome_cliente=lead.nome_cliente,
            nome_empresa=lead.nome_empresa,
            cargo=lead.cargo,
            telefone=lead.telefone,
            tags=lead.tags or [],
            score=lead.score,
            notes=lead.notes,
            status=lead.status,
            step_novo_lead=lead.step_novo_lead,
            step_primeiro_contato=lead.step_primeiro_contato,
            step_negociacao=lead.step_negociacao,
            step_orcamento_realizado=lead.step_orcamento_realizado,
            step_orcamento_aceito=lead.step_orcamento_aceito,
            step_orcamento_recusado=lead.step_orcamento_recusado,
            step_venda_convertida=lead.step_venda_convertida,
            step_venda_perdida=lead.step_venda_perdida,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )
        for lead in leads
    ]
    
    return LeadsListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )


@router.get("/metrics", response_model=LeadMetricsResponse)
def get_lead_metrics(
    db: Session = Depends(get_db),
):
    """
    Retorna métricas agregadas dos leads.
    
    Inclui:
    - Total de leads
    - Contagem por step do pipeline
    - Contagem por status
    - Taxa de conversão
    """
    metrics = lead_dao.get_metrics(db)
    
    return LeadMetricsResponse(
        total=metrics["total"],
        by_step=metrics["by_step"],
        by_status=metrics["by_status"],
        conversion_rate=metrics["conversion_rate"],
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retorna detalhes de um lead específico.
    """
    lead = lead_dao.get_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    return LeadResponse(
        id=lead.id,
        conversation_id=lead.conversation_id,
        profile_id=lead.profile_id,
        nome_cliente=lead.nome_cliente,
        nome_empresa=lead.nome_empresa,
        cargo=lead.cargo,
        telefone=lead.telefone,
        tags=lead.tags or [],
        score=lead.score,
        notes=lead.notes,
        status=lead.status,
        step_novo_lead=lead.step_novo_lead,
        step_primeiro_contato=lead.step_primeiro_contato,
        step_negociacao=lead.step_negociacao,
        step_orcamento_realizado=lead.step_orcamento_realizado,
        step_orcamento_aceito=lead.step_orcamento_aceito,
        step_orcamento_recusado=lead.step_orcamento_recusado,
        step_venda_convertida=lead.step_venda_convertida,
        step_venda_perdida=lead.step_venda_perdida,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    request: LeadUpdate,
    db: Session = Depends(get_db),
):
    """
    Atualiza um lead existente.
    
    Campos atualizáveis:
    - Dados comerciais: nome_cliente, nome_empresa, cargo, telefone
    - Qualificação: tags, score, notes
    - Temperatura: status (quente, morno, frio)
    - Pipeline: step_novo_lead, step_primeiro_contato, step_negociacao,
                step_orcamento_realizado, step_orcamento_recusado,
                step_venda_convertida, step_venda_perdida
    
    Apenas campos enviados são atualizados (PATCH parcial).
    """
    # Converte para dict excluindo None
    update_data = request.model_dump(exclude_none=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    
    lead = lead_dao.update_lead(db, lead_id, **update_data)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    await ws_manager.broadcast("lead_updated", {"lead_id": str(lead_id)})
    
    return LeadResponse(
        id=lead.id,
        conversation_id=lead.conversation_id,
        profile_id=lead.profile_id,
        nome_cliente=lead.nome_cliente,
        nome_empresa=lead.nome_empresa,
        cargo=lead.cargo,
        telefone=lead.telefone,
        tags=lead.tags or [],
        score=lead.score,
        notes=lead.notes,
        status=lead.status,
        step_novo_lead=lead.step_novo_lead,
        step_primeiro_contato=lead.step_primeiro_contato,
        step_negociacao=lead.step_negociacao,
        step_orcamento_realizado=lead.step_orcamento_realizado,
        step_orcamento_aceito=lead.step_orcamento_aceito,
        step_orcamento_recusado=lead.step_orcamento_recusado,
        step_venda_convertida=lead.step_venda_convertida,
        step_venda_perdida=lead.step_venda_perdida,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Remove um lead (soft delete).
    
    O lead não é excluído fisicamente, apenas marcado como deletado.
    Isso permite auditoria e recuperação se necessário.
    """
    success = lead_dao.soft_delete(db, lead_id)
    if not success:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    
    await ws_manager.broadcast("lead_deleted", {"lead_id": str(lead_id)})
    
    return {"status": "ok", "message": "Lead removido"}
