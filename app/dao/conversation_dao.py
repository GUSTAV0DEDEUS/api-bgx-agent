from __future__ import annotations

from sqlalchemy.orm import Session

from app.entities.conversation_entity import Conversation


def get_open_by_profile_id(db: Session, profile_id) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.profile_id == profile_id, Conversation.status == "open")
        .order_by(Conversation.created_at.desc())
        .first()
    )


def create_conversation(db: Session, profile_id) -> Conversation:
    conversation = Conversation(profile_id=profile_id, status="open")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_or_create_open(db: Session, profile_id) -> Conversation:
    conversation = get_open_by_profile_id(db, profile_id)
    if conversation:
        return conversation
    return create_conversation(db, profile_id)
