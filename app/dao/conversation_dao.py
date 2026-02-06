from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.entities.conversation_entity import Conversation, ConversationStatus


# Constante: máximo de tags por conversa
MAX_CONVERSATION_TAGS = 5


def get_by_id(db: Session, conversation_id: uuid.UUID) -> Conversation | None:
    """Retorna uma conversa pelo ID."""
    return db.query(Conversation).filter(Conversation.id == conversation_id).one_or_none()


def get_open_by_profile_id(db: Session, profile_id) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.profile_id == profile_id, Conversation.status == ConversationStatus.OPEN)
        .order_by(Conversation.created_at.desc())
        .first()
    )


def get_active_by_profile_id(db: Session, profile_id) -> Conversation | None:
    """
    Retorna conversa ativa (open ou human) do profile.
    
    - open: IA responde normalmente
    - human: consultor assumiu, IA silenciada
    
    Se não houver conversa ativa, retorna None.
    """
    return (
        db.query(Conversation)
        .filter(
            Conversation.profile_id == profile_id,
            Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.HUMAN])
        )
        .order_by(Conversation.created_at.desc())
        .first()
    )


def get_all_by_profile_id(db: Session, profile_id: uuid.UUID) -> list[Conversation]:
    """Retorna todas as conversas de um profile ordenadas por data."""
    return (
        db.query(Conversation)
        .filter(Conversation.profile_id == profile_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )


def create_conversation(db: Session, profile_id) -> Conversation:
    """Cria uma nova conversa sem tags (conversa limpa)."""
    conversation = Conversation(profile_id=profile_id, status=ConversationStatus.OPEN, tags=[])
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_or_create_open(db: Session, profile_id) -> Conversation:
    """
    Retorna conversa ativa existente ou cria uma nova.
    
    - Retorna conversa com status 'open' ou 'human' se existir
    - Se só existirem conversas 'closed', cria uma nova conversa limpa
    """
    conversation = get_active_by_profile_id(db, profile_id)
    if conversation:
        return conversation
    # Cria nova conversa sem tags (limpa)
    return create_conversation(db, profile_id)


def close_conversation(
    db: Session,
    conversation_id: uuid.UUID,
    closed_by: str = "agent",
    closed_reason: str | None = None,
) -> Conversation | None:
    """
    Fecha uma conversa.
    
    Args:
        db: Sessão do banco
        conversation_id: ID da conversa
        closed_by: Quem fechou (agent, user, system, admin)
        closed_reason: Motivo do encerramento
    
    Returns:
        Conversa fechada ou None se não encontrada
    """
    conversation = get_by_id(db, conversation_id)
    if not conversation:
        return None
    
    conversation.status = ConversationStatus.CLOSED
    conversation.closed_at = datetime.now()
    conversation.closed_by = closed_by
    conversation.closed_reason = closed_reason
    
    db.commit()
    db.refresh(conversation)
    return conversation


def set_human_takeover(
    db: Session,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """
    Ativa human takeover: consultor assume, IA para de responder.
    
    Args:
        db: Sessão do banco
        conversation_id: ID da conversa
    
    Returns:
        Conversa atualizada ou None se não encontrada
    """
    conversation = get_by_id(db, conversation_id)
    if not conversation:
        return None
    
    conversation.status = ConversationStatus.HUMAN
    
    db.commit()
    db.refresh(conversation)
    return conversation


def _normalize_tag(tag: str) -> str:
    """Normaliza tag: lowercase, sem espaços (usa underscore)."""
    return tag.lower().strip().replace(" ", "_")


def add_tag(db: Session, conversation_id: uuid.UUID, tag: str) -> Conversation | None:
    """
    Adiciona uma tag à conversa.
    
    - Normaliza a tag (lowercase, underscore)
    - Deduplica usando set
    - Respeita limite máximo de 5 tags
    
    Returns:
        Conversa atualizada ou None se não encontrada
    """
    conversation = get_by_id(db, conversation_id)
    if not conversation:
        return None
    
    normalized_tag = _normalize_tag(tag)
    
    # Usa set para deduplicar
    current_tags = set(conversation.tags or [])
    
    # Verifica se já atingiu o limite
    if len(current_tags) >= MAX_CONVERSATION_TAGS and normalized_tag not in current_tags:
        return conversation
    
    current_tags.add(normalized_tag)
    conversation.tags = list(current_tags)
    
    db.commit()
    db.refresh(conversation)
    return conversation


def add_tags(db: Session, conversation_id: uuid.UUID, tags: list[str]) -> Conversation | None:
    """Adiciona múltiplas tags à conversa respeitando limite de 5."""
    conversation = get_by_id(db, conversation_id)
    if not conversation:
        return None
    
    current_tags = set(conversation.tags or [])
    
    for tag in tags:
        normalized_tag = _normalize_tag(tag)
        if len(current_tags) < MAX_CONVERSATION_TAGS:
            current_tags.add(normalized_tag)
    
    conversation.tags = list(current_tags)
    db.commit()
    db.refresh(conversation)
    return conversation


def remove_tag(db: Session, conversation_id: uuid.UUID, tag: str) -> Conversation | None:
    """Remove uma tag da conversa."""
    conversation = get_by_id(db, conversation_id)
    if not conversation:
        return None
    
    normalized_tag = _normalize_tag(tag)
    current_tags = set(conversation.tags or [])
    current_tags.discard(normalized_tag)
    conversation.tags = list(current_tags)
    
    db.commit()
    db.refresh(conversation)
    return conversation
