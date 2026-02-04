from __future__ import annotations

import logging

from fastapi import FastAPI

from app.controllers.webhook_controller import router as webhook_router
from app.controllers.client_controller import router as client_router
from app.controllers.lead_controller import router as lead_router


# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="WhatsApp Agent API",
    description="API para agente de atendimento via WhatsApp com IA",
    version="2.0.0",
)

# Rotas
app.include_router(webhook_router)
app.include_router(client_router)
app.include_router(lead_router)
