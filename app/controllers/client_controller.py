from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dao import conversation_dao, message_dao, profile_dao
from app.entities.conversation_entity import ConversationStatus
from app.schemas.client_schemas import (
    AddTagRequest,
    ClientDetailResponse,
    ClientsListResponse,
    CloseConversationRequest,
    ConversationSummary,
    MessageResponse,
    ProfileWithTags,
)
from app.utils.db import get_db

router = APIRouter(prefix="/clients", tags=["Clients"])

@router.get("/", response_model=ClientsListResponse)
def list_clients(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    tag: str | None = Query(default=None, description="Filtrar por tag"),
    db: Session = Depends(get_db),
):
    profiles, total = profile_dao.get_all_paginated(db, page, per_page, tag)
    
    items = [
        ProfileWithTags(
            id=p.id,
            whatsapp_number=p.whatsapp_number,
            first_name=p.first_name,
            last_name=p.last_name,
            display_name=p.display_name,
            tags=p.tags or [],
            created_at=p.created_at, # type: ignore
            updated_at=p.updated_at, # type: ignore
        )
        for p in profiles
    ]
    
    return ClientsListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )

@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client_detail(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    profile = profile_dao.get_by_id(db, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    conversations = conversation_dao.get_all_by_profile_id(db, client_id)
    
    profile_response = ProfileWithTags(
        id=profile.id,
        whatsapp_number=profile.whatsapp_number,
        first_name=profile.first_name,
        last_name=profile.last_name,
        display_name=profile.display_name,
        tags=profile.tags or [],
        created_at=profile.created_at, # type: ignore
        updated_at=profile.updated_at, # type: ignore
    )
    
    conversations_response = [
        ConversationSummary(
            id=c.id,
            status=c.status,
            tags=c.tags or [],
            closed_at=c.closed_at,
            closed_by=c.closed_by,
            closed_reason=c.closed_reason,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]
    
    return ClientDetailResponse(
        profile=profile_response,
        conversations=conversations_response,
    )

@router.get("/{client_id}/conversations", response_model=list[ConversationSummary])
def get_client_conversations(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    profile = profile_dao.get_by_id(db, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    conversations = conversation_dao.get_all_by_profile_id(db, client_id)
    
    return [
        ConversationSummary(
            id=c.id,
            status=c.status,
            tags=c.tags or [],
            closed_at=c.closed_at,
            closed_by=c.closed_by,
            closed_reason=c.closed_reason,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]

@router.get(
    "/{client_id}/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_conversation_messages(
    client_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200, description="Número máximo de mensagens"),
    db: Session = Depends(get_db),
):
    profile = profile_dao.get_by_id(db, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    conversation = conversation_dao.get_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if conversation.profile_id != client_id:
        raise HTTPException(status_code=404, detail="Conversa não pertence a este cliente")
    
    messages = message_dao.get_messages_by_conversation_id(db, conversation_id, limit=limit)
    
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            message_type=m.message_type,
            created_at=m.created_at,  # type: ignore
        )
        for m in messages
    ]

@router.post("/{client_id}/tags", response_model=ProfileWithTags)
def add_client_tag(
    client_id: uuid.UUID,
    request: AddTagRequest,
    db: Session = Depends(get_db),
):
    profile = profile_dao.add_tag(db, client_id, request.tag)
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    return ProfileWithTags(
        id=profile.id,
        whatsapp_number=profile.whatsapp_number,
        first_name=profile.first_name,
        last_name=profile.last_name,
        display_name=profile.display_name,
        tags=profile.tags or [],
        created_at=profile.created_at, # type: ignore
        updated_at=profile.updated_at, # type: ignore
    )

@router.delete("/{client_id}/tags/{tag}", response_model=ProfileWithTags)
def remove_client_tag(
    client_id: uuid.UUID,
    tag: str,
    db: Session = Depends(get_db),
):
    profile = profile_dao.remove_tag(db, client_id, tag)
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    return ProfileWithTags(
        id=profile.id,
        whatsapp_number=profile.whatsapp_number,
        first_name=profile.first_name,
        last_name=profile.last_name,
        display_name=profile.display_name,
        tags=profile.tags or [],
        created_at=profile.created_at, # type: ignore
        updated_at=profile.updated_at, # type: ignore
    )

@router.post(
    "/{client_id}/conversations/{conversation_id}/close",
    response_model=ConversationSummary,
)
def close_conversation(
    client_id: uuid.UUID,
    conversation_id: uuid.UUID,
    request: CloseConversationRequest | None = None,
    db: Session = Depends(get_db),
):
    profile = profile_dao.get_by_id(db, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    conversation = conversation_dao.get_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if conversation.profile_id != client_id:
        raise HTTPException(status_code=404, detail="Conversa não pertence a este cliente")
    
    if conversation.status == ConversationStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Conversa já está fechada")
    
    reason = request.reason if request else None
    closed_conversation = conversation_dao.close_conversation(
        db, conversation_id, closed_by="admin", closed_reason=reason
    )
    
    if not closed_conversation:
        raise HTTPException(status_code=500, detail="Erro ao fechar conversa")
    
    return ConversationSummary(
        id=closed_conversation.id,
        status=closed_conversation.status,
        tags=closed_conversation.tags or [],
        closed_at=closed_conversation.closed_at,
        closed_by=closed_conversation.closed_by,
        closed_reason=closed_conversation.closed_reason,
        created_at=closed_conversation.created_at,
        updated_at=closed_conversation.updated_at,
    )

@router.post(
    "/{client_id}/conversations/{conversation_id}/human",
    response_model=ConversationSummary,
)
def set_human_takeover(
    client_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    profile = profile_dao.get_by_id(db, client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    conversation = conversation_dao.get_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if conversation.profile_id != client_id:
        raise HTTPException(status_code=404, detail="Conversa não pertence a este cliente")
    
    if conversation.status != ConversationStatus.OPEN:
        raise HTTPException(
            status_code=400, 
            detail=f"Conversa precisa estar aberta. Status atual: {conversation.status}"
        )
    
    updated_conversation = conversation_dao.set_human_takeover(db, conversation_id)
    
    if not updated_conversation:
        raise HTTPException(status_code=500, detail="Erro ao ativar human takeover")
    
    return ConversationSummary(
        id=updated_conversation.id,
        status=updated_conversation.status,
        tags=updated_conversation.tags or [],
        closed_at=updated_conversation.closed_at,
        closed_by=updated_conversation.closed_by,
        closed_reason=updated_conversation.closed_reason,
        created_at=updated_conversation.created_at,
        updated_at=updated_conversation.updated_at,
    )
