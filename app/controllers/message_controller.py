from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.schemas.client_schemas import MessageResponse
from app.services import message_service
from app.utils.db import get_db

router = APIRouter(prefix="/clients", tags=["Messages"])

class SendMessageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Texto da mensagem")

@router.post(
    "/{profile_id}/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
)
def send_human_message(
    profile_id: uuid.UUID,
    conversation_id: uuid.UUID,
    request: SendMessageRequest,
    db: Session = Depends(get_db),
):
    try:
        result = message_service.send_human_message(
            db,
            profile_id=profile_id,
            conversation_id=conversation_id,
            text=request.text,
        )
        return MessageResponse(
            id=result["id"],
            role=result["role"],
            content=result["content"],
            message_type=result["message_type"],
            created_at=result["created_at"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
