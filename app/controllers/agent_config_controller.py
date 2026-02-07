from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.agent_config_schemas import AgentConfigResponse, AgentConfigUpdate
from app.services import agent_config_service
from app.utils.db import get_db


router = APIRouter(prefix="/config", tags=["Agent Config"])


@router.get("/", response_model=AgentConfigResponse)
def get_agent_config(db: Session = Depends(get_db)):
    """Retorna a configuracao atual do agente."""
    config = agent_config_service.get_config(db)
    return AgentConfigResponse.model_validate(config)


@router.put("/", response_model=AgentConfigResponse)
def update_agent_config(
    request: AgentConfigUpdate,
    db: Session = Depends(get_db),
):
    """
    Atualiza a configuracao do agente.

    Campos disponiveis:
    - **tone**: profissional | descontraido | tecnico | amigavel
    - **use_emojis**: sempre | moderado | nunca
    - **response_style**: formal | conversacional | consultivo | direto
    - **greeting_style**: caloroso | neutro | objetivo
    - **max_message_length**: 50-1000 (tamanho maximo de cada chunk de mensagem)
    """
    config = agent_config_service.update_config(
        db,
        tone=request.tone.value if request.tone else None,
        use_emojis=request.use_emojis.value if request.use_emojis else None,
        response_style=request.response_style.value if request.response_style else None,
        greeting_style=request.greeting_style.value if request.greeting_style else None,
        max_message_length=request.max_message_length,
    )
    return AgentConfigResponse.model_validate(config)
