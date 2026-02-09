from __future__ import annotations

from pydantic import BaseModel

class StructuredMessage(BaseModel):
    role: str
    content: str

class WebhookResponse(BaseModel):
    status: str
