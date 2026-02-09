from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.entities.conversation_entity import Conversation, ConversationStatus

MAX_CONVERSATION_TAGS = 5

def get_by_id(db: Session, conversation_id: uuid.UUID) -> Conversation | None:
    return db.query(Conversation).filter(Conversation.id == conversation_id).one_or_none()

def get_open_by_profile_id(db: Session, profile_id) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.profile_id == profile_id, Conversation.status == ConversationStatus.OPEN)
        .order_by(Conversation.created_at.desc())
        .first()
    )

def get_active_by_profile_id(db: Session, profile_id) -> Conversation | None:
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
    return (
        db.query(Conversation)
        .filter(Conversation.profile_id == profile_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )

def create_conversation(db: Session, profile_id) -> Conversation:
    conversation = Conversation(profile_id=profile_id, status=ConversationStatus.OPEN, tags=[])
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation

def get_or_create_open(db: Session, profile_id) -> Conversation:
    conversation = get_active_by_profile_id(db, profile_id)
    if conversation:
        return conversation
    return create_conversation(db, profile_id)

def close_conversation(
    db: Session,
    conversation_id: uuid.UUID,
    closed_by: str = "agent",
    closed_reason: str | None = None,
) -> Conversation | None:
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
    conversation = get_by_id(db, conversation_id)
    if not conversation:
        return None
    
    conversation.status = ConversationStatus.HUMAN
    
    db.commit()
    db.refresh(conversation)
    return conversation

def _normalize_tag(tag: str) -> str:
    return tag.lower().strip().replace(" ", "_")

def add_tag(db: Session, conversation_id: uuid.UUID, tag: str) -> Conversation | None:
    conversation = get_by_id(db, conversation_id)
    if not conversation:
        return None
    
    normalized_tag = _normalize_tag(tag)
    
    current_tags = set(conversation.tags or [])
    
    if len(current_tags) >= MAX_CONVERSATION_TAGS and normalized_tag not in current_tags:
        return conversation
    
    current_tags.add(normalized_tag)
    conversation.tags = list(current_tags)
    
    db.commit()
    db.refresh(conversation)
    return conversation

def add_tags(db: Session, conversation_id: uuid.UUID, tags: list[str]) -> Conversation | None:
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
