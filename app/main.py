from __future__ import annotations

import logging

from fastapi import FastAPI

from app.controllers.webhook_controller import router as webhook_router


# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(title="WhatsApp Agent API")

app.include_router(webhook_router)
