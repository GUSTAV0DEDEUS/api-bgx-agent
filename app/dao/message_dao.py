from __future__ import annotations

from sqlalchemy.orm import Session

from app.entities.message_entity import Message


def create_message(
    db: Session,
    conversation_id,
    profile_id,
    role: str,
    content: str,
    provider_message_id: str | None = None,
    message_type: str = "text",
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        profile_id=profile_id,
        role=role,
        content=content,
        provider_message_id=provider_message_id,
        message_type=message_type,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages_by_conversation_id(
    db: Session,
    conversation_id,
    limit: int | None = None,
) -> list[Message]:
    """
    Busca mensagens de uma conversa ordenadas por created_at (mais antigas primeiro).
    Se limit for especificado, retorna apenas as últimas N mensagens.
    """
    query = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )

    if limit:
        # Subquery para pegar os IDs das últimas N mensagens
        subquery = (
            db.query(Message.id)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .subquery()
        )
        query = (
            db.query(Message)
            .filter(Message.id.in_(subquery))
            .order_by(Message.created_at.asc())
        )

    return query.all()
