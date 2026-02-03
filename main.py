from __future__ import annotations

from fastapi import FastAPI

from app.controllers.webhook_controller import router as webhook_router

app = FastAPI(title="WhatsApp Agent API")
app.include_router(webhook_router)
