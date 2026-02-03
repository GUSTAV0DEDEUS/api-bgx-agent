from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.schemas.webhook_schemas import WebhookPayload
from app.services.webhook_service import extract_message_data, message_handler
from app.utils.db import get_db, SessionLocal
from app.utils.settings import settings


logger = logging.getLogger(__name__)

router = APIRouter()


def get_db_factory():
    """Factory function para criar novas sessões do banco."""
    def factory() -> Session:
        return SessionLocal()
    return factory


@router.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(request: Request):
    """
    Endpoint de verificação do webhook do Meta/WhatsApp.
    
    Requer META_WHATSAPP_VERIFY_TOKEN configurado.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token and token == settings.meta_whatsapp_verify_token:
        logger.info("Webhook verificado com sucesso")
        return challenge or ""

    logger.warning("Falha na verificação do webhook")
    raise HTTPException(status_code=403, detail="Falha na verificação do webhook")


@router.post("/webhook")
def receive_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Endpoint para receber mensagens do WhatsApp.
    
    Processa mensagens de texto de forma assíncrona com consolidação por timeout.
    Retorna 200 imediatamente para o Meta não reenviar.
    """
    wa_id, display_name, text_body, message_id, message_type = extract_message_data(payload)

    if not wa_id or not message_id:
        logger.debug("Payload ignorado: sem wa_id ou message_id")
        return {"status": "ignored"}

    logger.info(f"Mensagem recebida de {wa_id}, tipo: {message_type}")

    db_factory = get_db_factory()

    if message_type == "text" and text_body:
        # Processa mensagem de texto
        message_handler.handle_text_message(
            wa_id=wa_id,
            text=text_body,
            message_id=message_id,
            db=db,
            db_factory=db_factory,
        )
    elif message_type == "audio":
        # Áudio não suportado
        background_tasks.add_task(
            message_handler.handle_audio_message,
            wa_id,
            message_id,
        )
    else:
        # Outros tipos não suportados
        background_tasks.add_task(
            message_handler.handle_unsupported_message,
            wa_id,
            message_id,
            message_type,
        )

    return {"status": "ok"}
