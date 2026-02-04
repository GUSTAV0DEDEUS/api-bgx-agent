from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.entities.lead_entity import Lead


def get_by_id(db: Session, lead_id: uuid.UUID) -> Lead | None:
    """Retorna um lead pelo ID (excluindo soft deleted)."""
    return (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.deleted_at.is_(None))
        .one_or_none()
    )


def get_by_conversation_id(db: Session, conversation_id: uuid.UUID) -> Lead | None:
    """Retorna um lead pela conversation_id (excluindo soft deleted)."""
    return (
        db.query(Lead)
        .filter(Lead.conversation_id == conversation_id, Lead.deleted_at.is_(None))
        .one_or_none()
    )


def get_all_paginated(
    db: Session,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    step: str | None = None,
) -> tuple[list[Lead], int]:
    """
    Retorna leads paginados com filtros opcionais.
    
    Args:
        db: Sessão do banco
        page: Número da página (1-indexed)
        per_page: Itens por página
        status: Filtrar por status (novo, contatado, convertido, perdido)
        step: Filtrar por step (step_novo_lead, step_primeiro_contato, etc.)
    
    Returns:
        Tupla com (lista de leads, total de registros)
    """
    query = db.query(Lead).filter(Lead.deleted_at.is_(None))
    
    if status:
        query = query.filter(Lead.status == status)
    
    if step:
        # Mapeia o nome do step para o atributo da entity
        step_mapping = {
            "step_novo_lead": Lead.step_novo_lead,
            "step_primeiro_contato": Lead.step_primeiro_contato,
            "step_orcamento_realizado": Lead.step_orcamento_realizado,
            "step_orcamento_recusado": Lead.step_orcamento_recusado,
            "step_venda_convertida": Lead.step_venda_convertida,
        }
        if step in step_mapping:
            query = query.filter(step_mapping[step] == True)
    
    total = query.count()
    leads = (
        query
        .order_by(Lead.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    return leads, total


def create_lead(
    db: Session,
    conversation_id: uuid.UUID,
    profile_id: uuid.UUID,
    telefone: str | None = None,
    nome_cliente: str | None = None,
    nome_empresa: str | None = None,
    cargo: str | None = None,
    tags: list[str] | None = None,
    score: int = 50,
    notes: str | None = None,
) -> Lead:
    """Cria um novo lead."""
    lead = Lead(
        conversation_id=conversation_id,
        profile_id=profile_id,
        telefone=telefone,
        nome_cliente=nome_cliente,
        nome_empresa=nome_empresa,
        cargo=cargo,
        tags=tags or [],
        score=score,
        notes=notes,
        status="novo",
        step_novo_lead=True,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(
    db: Session,
    lead_id: uuid.UUID,
    nome_cliente: str | None = None,
    nome_empresa: str | None = None,
    cargo: str | None = None,
    telefone: str | None = None,
    tags: list[str] | None = None,
    score: int | None = None,
    notes: str | None = None,
    status: str | None = None,
    step_novo_lead: bool | None = None,
    step_primeiro_contato: bool | None = None,
    step_orcamento_realizado: bool | None = None,
    step_orcamento_recusado: bool | None = None,
    step_venda_convertida: bool | None = None,
) -> Lead | None:
    """Atualiza um lead existente."""
    lead = get_by_id(db, lead_id)
    if not lead:
        return None
    
    if nome_cliente is not None:
        lead.nome_cliente = nome_cliente
    if nome_empresa is not None:
        lead.nome_empresa = nome_empresa
    if cargo is not None:
        lead.cargo = cargo
    if telefone is not None:
        lead.telefone = telefone
    if tags is not None:
        lead.tags = tags
    if score is not None:
        lead.score = score
    if notes is not None:
        lead.notes = notes
    if status is not None:
        lead.status = status
    if step_novo_lead is not None:
        lead.step_novo_lead = step_novo_lead
    if step_primeiro_contato is not None:
        lead.step_primeiro_contato = step_primeiro_contato
    if step_orcamento_realizado is not None:
        lead.step_orcamento_realizado = step_orcamento_realizado
    if step_orcamento_recusado is not None:
        lead.step_orcamento_recusado = step_orcamento_recusado
    if step_venda_convertida is not None:
        lead.step_venda_convertida = step_venda_convertida
    
    db.commit()
    db.refresh(lead)
    return lead


def soft_delete(db: Session, lead_id: uuid.UUID) -> bool:
    """Realiza soft delete de um lead."""
    lead = get_by_id(db, lead_id)
    if not lead:
        return False
    
    lead.deleted_at = datetime.now()
    db.commit()
    return True


def get_metrics(db: Session) -> dict:
    """
    Retorna métricas agregadas dos leads.
    
    Returns:
        Dict com total, contagem por step e taxa de conversão
    """
    base_query = db.query(Lead).filter(Lead.deleted_at.is_(None))
    
    total = base_query.count()
    
    by_step = {
        "novo_lead": base_query.filter(Lead.step_novo_lead == True).count(),
        "primeiro_contato": base_query.filter(Lead.step_primeiro_contato == True).count(),
        "orcamento_realizado": base_query.filter(Lead.step_orcamento_realizado == True).count(),
        "orcamento_recusado": base_query.filter(Lead.step_orcamento_recusado == True).count(),
        "venda_convertida": base_query.filter(Lead.step_venda_convertida == True).count(),
    }
    
    by_status = {
        "novo": base_query.filter(Lead.status == "novo").count(),
        "contatado": base_query.filter(Lead.status == "contatado").count(),
        "convertido": base_query.filter(Lead.status == "convertido").count(),
        "perdido": base_query.filter(Lead.status == "perdido").count(),
    }
    
    # Taxa de conversão (vendas convertidas / total)
    conversion_rate = (by_step["venda_convertida"] / total * 100) if total > 0 else 0.0
    
    return {
        "total": total,
        "by_step": by_step,
        "by_status": by_status,
        "conversion_rate": round(conversion_rate, 2),
    }
