from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.dao import conversation_dao, message_dao, profile_dao
from app.entities.conversation_entity import ConversationStatus
from app.services.whatsapp_service import whatsapp_service


logger = logging.getLogger(__name__)


def send_human_message(
    db: Session,
    profile_id: uuid.UUID,
    conversation_id: uuid.UUID,
    text: str,
) -> dict:
    """
    Envia mensagem de um humano (admin/consultor) para o cliente via WhatsApp.

    Regras:
    - A conversa deve existir e pertencer ao profile
    - A conversa deve estar em status 'human' (consultor assumiu)
    - A mensagem é persistida como role='admin'
    - A mensagem é enviada via WhatsApp
    """
    # Valida profile
    profile = profile_dao.get_by_id(db, profile_id)
    if not profile:
        raise ValueError("Cliente nao encontrado")

    # Valida conversa
    conversation = conversation_dao.get_by_id(db, conversation_id)
    if not conversation:
        raise ValueError("Conversa nao encontrada")

    if conversation.profile_id != profile_id:
        raise ValueError("Conversa nao pertence a este cliente")

    if conversation.status != ConversationStatus.HUMAN:
        raise ValueError(
            f"Conversa precisa estar em modo humano para enviar mensagens. "
            f"Status atual: {conversation.status}"
        )

    # Persiste a mensagem como admin
    message = message_dao.create_message(
        db,
        conversation_id=conversation_id,
        profile_id=profile_id,
        role="admin",
        content=text,
    )

    # Envia via WhatsApp
    try:
        whatsapp_service.send_text_message(profile.whatsapp_number, text)
        logger.info(
            f"Mensagem humana enviada para {profile.whatsapp_number} "
            f"na conversa {conversation_id}"
        )
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem WhatsApp: {e}")
        # Mensagem ja esta persistida, nao falha

    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "profile_id": message.profile_id,
        "role": message.role,
        "content": message.content,
        "message_type": message.message_type,
        "created_at": message.created_at,
    }
