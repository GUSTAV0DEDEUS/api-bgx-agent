from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.entities.agent_config_entity import (
    EmojiUsageEnum,
    GreetingStyleEnum,
    ResponseStyleEnum,
    ToneEnum,
)

class AgentConfigResponse(BaseModel):
    id: uuid.UUID
    tone: ToneEnum
    use_emojis: EmojiUsageEnum
    response_style: ResponseStyleEnum
    greeting_style: GreetingStyleEnum
    max_message_length: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AgentConfigUpdate(BaseModel):
    tone: ToneEnum | None = None
    use_emojis: EmojiUsageEnum | None = None
    response_style: ResponseStyleEnum | None = None
    greeting_style: GreetingStyleEnum | None = None
    max_message_length: int | None = Field(default=None, ge=50, le=1000)
