from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.agent_config_schemas import AgentConfigResponse, AgentConfigUpdate
from app.services import agent_config_service
from app.utils.db import get_db

router = APIRouter(prefix="/config", tags=["Agent Config"])

@router.get("/", response_model=AgentConfigResponse)
def get_agent_config(db: Session = Depends(get_db)):
    config = agent_config_service.get_config(db)
    return AgentConfigResponse.model_validate(config)

@router.put("/", response_model=AgentConfigResponse)
def update_agent_config(
    request: AgentConfigUpdate,
    db: Session = Depends(get_db),
):
    config = agent_config_service.update_config(
        db,
        tone=request.tone.value if request.tone else None,
        use_emojis=request.use_emojis.value if request.use_emojis else None,
        response_style=request.response_style.value if request.response_style else None,
        greeting_style=request.greeting_style.value if request.greeting_style else None,
        max_message_length=request.max_message_length,
    )
    return AgentConfigResponse.model_validate(config)
