from __future__ import annotations

from pydantic import BaseModel, Field

class WebhookText(BaseModel):
    body: str | None = None

class WebhookMessage(BaseModel):
    from_: str | None = Field(default=None, alias="from")
    id: str | None = None
    timestamp: str | None = None
    type: str | None = None
    text: WebhookText | None = None

class WebhookProfile(BaseModel):
    name: str | None = None

class WebhookContact(BaseModel):
    wa_id: str | None = None
    profile: WebhookProfile | None = None

class WebhookValue(BaseModel):
    messages: list[WebhookMessage] | None = None
    contacts: list[WebhookContact] | None = None
    metadata: dict | None = None

class WebhookChange(BaseModel):
    value: WebhookValue | None = None
    field: str | None = None

class WebhookEntry(BaseModel):
    id: str | None = None
    changes: list[WebhookChange] | None = None

class WebhookPayload(BaseModel):
    object: str | None = None
    entry: list[WebhookEntry] | None = None
