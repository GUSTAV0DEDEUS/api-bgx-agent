from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session

from app.dao.conversation_dao import get_or_create_open
from app.dao.message_dao import create_message, get_messages_by_conversation_id
from app.dao.profile_dao import get_or_create
from app.schemas.webhook_schemas import WebhookPayload
from app.services.gemini_service import ChatMessage, GeminiService, GeminiServiceError, get_gemini_service
from app.services.whatsapp_service import WhatsAppService, whatsapp_service
from app.utils.settings import settings


logger = logging.getLogger(__name__)


AUDIO_NOT_SUPPORTED_MESSAGE = (
    "🎤 Desculpe, ainda não suportamos mensagens de áudio. "
    "Por favor, envie sua mensagem em texto."
)


@dataclass
class PendingMessage:
    """Representa mensagens pendentes de consolidação."""
    texts: list[str] = field(default_factory=list)
    timestamp: float = 0.0
    last_sent: str = ""
    timer: threading.Timer | None = None


class MessageHandler:
    """
    Handler de mensagens com consolidação por timeout.
    
    Agrupa mensagens recebidas em sequência antes de processar,
    evitando múltiplas chamadas à IA para mensagens fragmentadas.
    """

    def __init__(
        self,
        timeout: int | None = None,
        history_limit: int | None = None,
        whatsapp: WhatsAppService | None = None,
        gemini: GeminiService | None = None,
    ):
        self.timeout = timeout or settings.message_consolidation_timeout
        self.history_limit = history_limit or settings.message_history_limit
        self.whatsapp = whatsapp or whatsapp_service
        self._gemini = gemini
        self._pending_messages: dict[str, PendingMessage] = {}
        self._lock = threading.Lock()

    @property
    def gemini(self) -> GeminiService:
        """Lazy loading do GeminiService."""
        if self._gemini is None:
            self._gemini = get_gemini_service()
        return self._gemini

    def _validate_message(self, pending: PendingMessage, consolidated_text: str) -> bool:
        """Verifica se a mensagem não é repetida."""
        if consolidated_text.strip() == pending.last_sent.strip():
            logger.debug("Mensagem repetitiva detectada, ignorando envio")
            return False
        pending.last_sent = consolidated_text
        return True

    def _build_chat_history(self, db: Session, conversation_id) -> list[ChatMessage]:
        """Constrói histórico de chat a partir das mensagens persistidas."""
        messages = get_messages_by_conversation_id(
            db, conversation_id, limit=self.history_limit
        )
        return [
            ChatMessage(role=msg.role, content=msg.content)
            for msg in messages
        ]

    def _process_consolidated_message(
        self,
        wa_id: str,
        db_factory: Callable[[], Session],
        profile_id,
        conversation_id,
    ) -> None:
        """
        Processa mensagens consolidadas após o timeout.
        
        Chamado pelo timer em uma thread separada.
        """
        with self._lock:
            pending = self._pending_messages.get(wa_id)
            if not pending or not pending.texts:
                return

            consolidated_text = " ".join(pending.texts)
            
            if not self._validate_message(pending, consolidated_text):
                return

            # Limpa as mensagens pendentes
            pending.texts = []

        try:
            # Usa uma nova sessão do banco
            db = db_factory()
            try:
                # Persiste a mensagem consolidada do usuário
                create_message(
                    db,
                    conversation_id=conversation_id,
                    profile_id=profile_id,
                    role="user",
                    content=consolidated_text,
                )

                # Busca histórico e gera resposta
                history = self._build_chat_history(db, conversation_id)
                
                try:
                    response_text = self.gemini.chat(history)
                except GeminiServiceError as e:
                    logger.error(f"Erro ao chamar Gemini: {e}")
                    response_text = "Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente."

                # Envia resposta via WhatsApp
                self.whatsapp.send_text_message(wa_id, response_text)

                # Persiste a resposta do agente
                create_message(
                    db,
                    conversation_id=conversation_id,
                    profile_id=profile_id,
                    role="agent",
                    content=response_text,
                )

                logger.info(f"Mensagem processada para {wa_id}")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Erro ao processar mensagem consolidada: {e}")

    def _schedule_processing(
        self,
        wa_id: str,
        db_factory: Callable[[], Session],
        profile_id,
        conversation_id,
    ) -> None:
        """Agenda o processamento após o timeout."""
        with self._lock:
            pending = self._pending_messages.get(wa_id)
            if not pending:
                return

            # Cancela timer anterior se existir
            if pending.timer:
                pending.timer.cancel()

            # Agenda novo timer
            pending.timer = threading.Timer(
                self.timeout,
                self._process_consolidated_message,
                args=(wa_id, db_factory, profile_id, conversation_id),
            )
            pending.timer.start()

    def handle_text_message(
        self,
        wa_id: str,
        text: str,
        message_id: str,
        db: Session,
        db_factory: Callable[[], Session],
    ) -> None:
        """
        Processa uma mensagem de texto recebida.
        
        Adiciona à fila de consolidação e agenda processamento.
        """
        # Obtém ou cria profile e conversa
        profile = get_or_create(db, wa_id, None)
        conversation = get_or_create_open(db, profile.id)

        # Marca como lida
        self.whatsapp.mark_as_read(message_id)

        # Adiciona à fila de consolidação
        import time
        with self._lock:
            if wa_id not in self._pending_messages:
                self._pending_messages[wa_id] = PendingMessage()
            
            pending = self._pending_messages[wa_id]
            pending.texts.append(text)
            pending.timestamp = time.time()

        # Agenda processamento
        self._schedule_processing(wa_id, db_factory, profile.id, conversation.id)

        logger.debug(f"Mensagem de texto adicionada à fila para {wa_id}")

    def handle_audio_message(self, wa_id: str, message_id: str) -> None:
        """
        Responde que áudio não é suportado.
        """
        self.whatsapp.mark_as_read(message_id)
        self.whatsapp.send_text_message(wa_id, AUDIO_NOT_SUPPORTED_MESSAGE)
        logger.info(f"Mensagem de áudio não suportada enviada para {wa_id}")

    def handle_unsupported_message(self, wa_id: str, message_id: str, message_type: str) -> None:
        """
        Responde que o tipo de mensagem não é suportado.
        """
        self.whatsapp.mark_as_read(message_id)
        unsupported_message = (
            f"📎 Desculpe, ainda não suportamos mensagens do tipo '{message_type}'. "
            "Por favor, envie sua mensagem em texto."
        )
        self.whatsapp.send_text_message(wa_id, unsupported_message)
        logger.info(f"Mensagem tipo '{message_type}' não suportada para {wa_id}")


def extract_message_data(payload: WebhookPayload) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """
    Extrai dados da mensagem do payload do webhook.
    
    Returns:
        Tupla com (wa_id, display_name, text_body, message_id, message_type)
    """
    if not payload.entry:
        return None, None, None, None, None
    
    for entry in payload.entry:
        if not entry.changes:
            continue
        for change in entry.changes:
            value = change.value
            if not value or not value.messages:
                continue
            
            message = value.messages[0]
            contact = value.contacts[0] if value.contacts else None
            wa_id = (contact.wa_id if contact else None) or message.from_
            display_name = contact.profile.name if contact and contact.profile else None
            
            message_type = message.type or "text"
            text_body = message.text.body if message.text else None
            
            return wa_id, display_name, text_body, message.id, message_type
    
    return None, None, None, None, None


# Instância singleton do MessageHandler
message_handler = MessageHandler()

