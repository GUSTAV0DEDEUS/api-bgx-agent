from app.controllers.webhook_controller import router as webhook_router
from app.controllers.client_controller import router as client_router
from app.controllers.lead_controller import router as lead_router

__all__ = [
    "webhook_router",
    "client_router",
    "lead_router",
]
