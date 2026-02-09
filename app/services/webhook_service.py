from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session

from app.dao import agent_config_dao, conversation_dao, lead_dao, profile_dao
from app.dao.conversation_dao import get_or_create_open
from app.dao.message_dao import create_message, get_messages_by_conversation_id
from app.dao.profile_dao import get_or_create
from app.entities.conversation_entity import ConversationStatus
from app.entities.lead_entity import LeadStatus
from app.schemas.webhook_schemas import WebhookPayload
from app.services.agent_config_service import (
    build_emoji_instructions,
    build_greeting_instructions,
    build_response_style_instructions,
    build_tone_instructions,
)
from app.services.openai_service import ChatMessage, AIService, AIServiceError, get_ai_service
from app.services.langgraph_service import get_langgraph_service, LangGraphService
from app.services.lead_scoring_service import LeadData, get_lead_scoring_service
from app.services.whatsapp_service import WhatsAppService, whatsapp_service
from app.services.websocket_manager import ws_manager
from app.utils.message_splitter import split_response
from app.utils.settings import settings

logger = logging.getLogger(__name__)

AUDIO_NOT_SUPPORTED_MESSAGE = (
    "Desculpe, ainda nao suportamos mensagens de audio. "
    "Por favor, envie sua mensagem em texto."
)

BGX_COMMAND_PATTERN = re.compile(
    r'\[BGX_COMMAND:(\w+)\]\s*(\{.*?\})\s*\[/BGX_COMMAND\]',
    re.DOTALL
)

@dataclass
class PendingMessage:
    texts: list[str] = field(default_factory=list)
    timestamp: float = 0.0
    last_sent: str = ""
    timer: threading.Timer | None = None

class MessageHandler:
    def __init__(
        self,
        timeout: int | None = None,
        history_limit: int | None = None,
        whatsapp: WhatsAppService | None = None,
        gemini: AIService | None = None,
        langgraph: LangGraphService | None = None,
    ):
        self.timeout = timeout or settings.message_consolidation_timeout
        self.history_limit = history_limit or settings.message_history_limit
        self.min_delay = settings.min_response_delay
        self.max_delay = max(
            self.min_delay,
            min(
                settings.max_response_delay,
                settings.message_consolidation_timeout - 5,
            ),
        )
        self.whatsapp = whatsapp or whatsapp_service
        self._gemini = gemini
        self._langgraph = langgraph
        self._pending_messages: dict[str, PendingMessage] = {}
        self._lock = threading.Lock()

    @property
    def gemini(self) -> AIService:
        if self._gemini is None:
            self._gemini = get_ai_service()
        return self._gemini

    @property
    def langgraph(self) -> LangGraphService:
        if self._langgraph is None:
            self._langgraph = get_langgraph_service()
        return self._langgraph

    def _validate_message(self, pending: PendingMessage, consolidated_text: str) -> bool:
        if consolidated_text.strip() == pending.last_sent.strip():
            logger.debug("Mensagem repetitiva detectada, ignorando envio")
            return False
        pending.last_sent = consolidated_text
        return True

    def _build_chat_history(self, db: Session, conversation_id) -> list[ChatMessage]:
        messages = get_messages_by_conversation_id(
            db, conversation_id, limit=self.history_limit
        )
        return [
            ChatMessage(role=msg.role, content=msg.content)
            for msg in messages
        ]

    def _calculate_humanized_delay(self) -> float:
        if self.max_delay <= 0:
            return 0
        return random.uniform(self.min_delay, self.max_delay)

    def _send_split_messages(self, wa_id: str, text: str, max_length: int = 300) -> None:
        chunks = split_response(text, max_length=max_length)
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(random.uniform(1.0, 3.0))
            self.whatsapp.send_text_message(wa_id, chunk)

    def _parse_bgx_commands(
        self,
        response_text: str,
        db: Session,
        conversation_id: uuid.UUID,
        profile_id: uuid.UUID,
        profile_phone: str,
    ) -> str:
        clean_text = response_text
        matches = BGX_COMMAND_PATTERN.findall(response_text)
        for command_type, json_str in matches:
            try:
                data = json.loads(json_str)
                if command_type == "ADD_TAG":
                    tag = data.get("tag")
                    if tag:
                        self._add_tag_to_conversation_and_profile(
                            db, conversation_id, profile_id, tag
                        )
                elif command_type == "ADD_TAGS":
                    tags = data.get("tags", [])
                    for tag in tags:
                        self._add_tag_to_conversation_and_profile(
                            db, conversation_id, profile_id, tag
                        )
                elif command_type == "CREATE_LEAD":
                    self._create_lead_from_conversation(
                        db, conversation_id, profile_id, profile_phone, data,
                    )
            except json.JSONDecodeError as e:
                logger.warning(f"Erro ao parsear comando BGX: {e}")
            except Exception as e:
                logger.error(f"Erro ao executar comando BGX {command_type}: {e}")
        clean_text = BGX_COMMAND_PATTERN.sub("", clean_text).strip()
        return clean_text

    def _add_tag_to_conversation_and_profile(
        self, db: Session, conversation_id: uuid.UUID, profile_id: uuid.UUID, tag: str,
    ) -> None:
        conversation_dao.add_tag(db, conversation_id, tag)
        profile_dao.add_tag(db, profile_id, tag)
        logger.info(f"Tag '{tag}' adicionada a conversa {conversation_id} e profile {profile_id}")

    def _create_lead_from_conversation(
        self, db: Session, conversation_id: uuid.UUID, profile_id: uuid.UUID,
        profile_phone: str, lead_data: dict,
    ) -> None:
        try:
            existing_lead = lead_dao.get_by_conversation_id(db, conversation_id)
            if existing_lead:
                logger.warning(f"Lead ja existe para conversa {conversation_id}")
                return
            close_reason = lead_data.get("close_reason", "Lead qualificado")
            conversation_dao.close_conversation(db, conversation_id, "agent", close_reason)
            nome_cliente = lead_data.get("nome_cliente")
            nome_empresa = lead_data.get("nome_empresa")
            cargo = lead_data.get("cargo")
            tags = lead_data.get("tags", [])
            notes = lead_data.get("notes")
            lead = lead_dao.create_lead(
                db, conversation_id=conversation_id, profile_id=profile_id,
                telefone=profile_phone, nome_cliente=nome_cliente,
                nome_empresa=nome_empresa, cargo=cargo, tags=tags, score=None, notes=notes,
            )
            logger.info(f"Lead criado: {lead.id} (score pendente) para conversa {conversation_id}")

            if nome_cliente:
                profile = profile_dao.get_by_id(db, profile_id)
                if profile and not profile.first_name:
                    first_name, last_name = profile_dao.parse_display_name(nome_cliente)
                    if first_name:
                        profile_dao.update_name(db, profile_id, first_name=first_name, last_name=last_name)
                        logger.info(f"Nome do lead copiado para contato {profile_id}: {first_name} {last_name or ''}")
        except Exception as e:
            logger.error(f"Erro ao criar lead para conversa {conversation_id}: {e}")

    def _get_agent_config_instructions(self, db: Session) -> tuple[str, str, str, str, int]:
        try:
            config = agent_config_dao.get_config(db)
            return (
                build_tone_instructions(config),
                build_emoji_instructions(config),
                build_greeting_instructions(config),
                build_response_style_instructions(config),
                config.max_message_length,
            )
        except Exception as e:
            logger.warning(f"Erro ao carregar agent_config, usando defaults: {e}")
            return "", "", "", "", 300

    def _process_consolidated_message(
        self, wa_id: str, db_factory: Callable[[], Session], profile_id, conversation_id,
    ) -> None:
        with self._lock:
            pending = self._pending_messages.get(wa_id)
            if not pending or not pending.texts:
                return
            consolidated_text = " ".join(pending.texts)
            if not self._validate_message(pending, consolidated_text):
                return
            pending.texts = []

        try:
            db = db_factory()
            try:
                conversation = conversation_dao.get_by_id(db, conversation_id)
                if not conversation or conversation.status != ConversationStatus.OPEN:
                    logger.info(f"Conversa {conversation_id} nao esta open, ignorando processamento")
                    return

                create_message(
                    db, conversation_id=conversation_id, profile_id=profile_id,
                    role="user", content=consolidated_text,
                )
                history = self._build_chat_history(db, conversation_id)
                messages_for_graph = [
                    {"role": msg.role, "content": msg.content} for msg in history
                ]

                existing_lead = lead_dao.get_by_conversation_id(db, conversation_id)
                if not existing_lead:
                    existing_lead = lead_dao.get_by_profile_id(db, profile_id)

                profile = profile_dao.get_by_id(db, profile_id)
                first_name = profile.first_name if profile else None

                if existing_lead:
                    lead_info = {
                        "first_name": existing_lead.nome_cliente,
                        "nome_empresa": existing_lead.nome_empresa,
                        "cargo": existing_lead.cargo,
                        "tags": existing_lead.tags or [],
                    }
                    lead_id = str(existing_lead.id)

                    if existing_lead.step_negociacao:
                        pipeline_stage = "negotiation"
                    else:
                        pipeline_stage = "first_contact"

                    if existing_lead.nome_cliente:
                        first_name = existing_lead.nome_cliente
                else:
                    lead_info = None
                    pipeline_stage = "onboarding"
                    lead_id = None

                user_message_count = len([m for m in messages_for_graph if m["role"] == "user"])

                (
                    tone_instructions,
                    emoji_instructions,
                    greeting_instructions,
                    response_style_instructions,
                    max_message_length,
                ) = self._get_agent_config_instructions(db)

                try:
                    result = self.langgraph.process_message(
                        messages=messages_for_graph,
                        profile_id=str(profile_id),
                        conversation_id=str(conversation_id),
                        lead_id=lead_id,
                        lead_info=lead_info,
                        pipeline_stage=pipeline_stage,
                        user_message_count=user_message_count,
                        first_name=first_name,
                        tone_instructions=tone_instructions,
                        emoji_instructions=emoji_instructions,
                        greeting_instructions=greeting_instructions,
                        response_style_instructions=response_style_instructions,
                    )
                    response_text = result.get("response", "")
                    self._process_langgraph_actions(
                        db, dict(result), conversation_id, profile_id, wa_id
                    )
                except Exception as e:
                    logger.error(f"Erro ao chamar LangGraph: {e}")
                    try:
                        response_text = self.gemini.chat(history)
                        response_text = self._parse_bgx_commands(
                            response_text, db, conversation_id, profile_id, wa_id
                        )
                    except AIServiceError as e:
                        logger.error(f"Erro ao chamar OpenAI: {e}")
                        response_text = "Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente."

                delay = self._calculate_humanized_delay()
                logger.debug(f"Aplicando delay humanizado de {delay:.1f}s para {wa_id}")
                time.sleep(delay)

                if response_text:
                    self._send_split_messages(wa_id, response_text, max_length=max_message_length)

                create_message(
                    db, conversation_id=conversation_id, profile_id=profile_id,
                    role="agent", content=response_text or "",
                )

                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(ws_manager.broadcast("new_message", {
                            "conversation_id": str(conversation_id),
                            "profile_id": str(profile_id),
                        }))
                    else:
                        loop.run_until_complete(ws_manager.broadcast("new_message", {
                            "conversation_id": str(conversation_id),
                            "profile_id": str(profile_id),
                        }))
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(ws_manager.broadcast("new_message", {
                        "conversation_id": str(conversation_id),
                        "profile_id": str(profile_id),
                    }))
                    loop.close()

                logger.info(f"Mensagem processada para {wa_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Erro ao processar mensagem consolidada: {e}")

    def _process_langgraph_actions(
        self, db: Session, result: dict, conversation_id: uuid.UUID,
        profile_id: uuid.UUID, profile_phone: str,
    ) -> None:
        try:
            if result.get("should_create_lead") and result.get("lead"):
                lead_data = result["lead"]
                existing_lead = lead_dao.get_by_conversation_id(db, conversation_id)
                if not existing_lead:
                    profile = profile_dao.get_by_id(db, profile_id)
                    first_name_raw = lead_data.get("first_name")
                    last_name = lead_data.get("last_name")

                    first_name = profile_dao.extract_first_name_only(first_name_raw) if first_name_raw else None

                    if profile and first_name and not profile.first_name:
                        profile_dao.update_name(
                            db, profile_id,
                            first_name=first_name,
                            last_name=last_name,
                        )
                        logger.info(f"Nome do lead copiado para contato {profile_id}: {first_name} {last_name or ''}")

                    nome_cliente = first_name
                    if first_name and last_name:
                        nome_cliente = f"{first_name} {last_name}"
                    elif not nome_cliente and profile and profile.first_name:
                        nome_cliente = profile.first_name

                    lead = lead_dao.create_lead(
                        db, conversation_id=conversation_id, profile_id=profile_id,
                        telefone=profile_phone, nome_cliente=nome_cliente,
                        nome_empresa=lead_data.get("nome_empresa"),
                        cargo=lead_data.get("cargo"),
                        tags=lead_data.get("tags", []), score=None,
                        notes=lead_data.get("notes"),
                    )
                    logger.info(f"Lead criado via LangGraph: {lead.id} (score pendente)")
                    for tag in lead_data.get("tags", []):
                        self._add_tag_to_conversation_and_profile(
                            db, conversation_id, profile_id, tag
                        )

                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(ws_manager.broadcast("lead_created", {
                                "lead_id": str(lead.id),
                                "conversation_id": str(conversation_id),
                            }))
                        else:
                            loop.run_until_complete(ws_manager.broadcast("lead_created", {
                                "lead_id": str(lead.id),
                                "conversation_id": str(conversation_id),
                            }))
                    except RuntimeError:
                        pass

            if result.get("should_human_takeover"):
                conversation_dao.set_human_takeover(db, conversation_id)
                logger.info(f"Human takeover ativado para conversa {conversation_id}")

                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(ws_manager.broadcast("human_takeover", {
                            "conversation_id": str(conversation_id),
                        }))
                    else:
                        loop.run_until_complete(ws_manager.broadcast("human_takeover", {
                            "conversation_id": str(conversation_id),
                        }))
                except RuntimeError:
                    pass

                lead = lead_dao.get_by_conversation_id(db, conversation_id)
                if lead:
                    pipeline_stage = result.get("pipeline_stage", "")
                    if pipeline_stage == "negotiation":
                        try:
                            scoring_service = get_lead_scoring_service()
                            lead_data_obj = LeadData(
                                nome_cliente=lead.nome_cliente,
                                nome_empresa=lead.nome_empresa,
                                cargo=lead.cargo,
                                telefone=lead.telefone,
                                tags=lead.tags or [],
                                notes=lead.notes,
                            )
                            score_result = scoring_service.calculate_score(db, conversation_id, lead_data_obj)
                            new_score = score_result.get("score", 50)
                            justificativa = score_result.get("justificativa", "")
                            notes = lead.notes or ""
                            if justificativa:
                                notes = f"{notes}\n\n[Scoring negociação]: {justificativa}".strip()

                            if new_score >= 70:
                                temperatura = LeadStatus.QUENTE
                            elif new_score >= 40:
                                temperatura = LeadStatus.MORNO
                            else:
                                temperatura = LeadStatus.FRIO

                            lead_dao.update_lead(
                                db, lead.id,
                                status=temperatura,
                                score=new_score,
                                notes=notes,
                                step_negociacao=True,
                            )
                            logger.info(f"Lead {lead.id} em negociação: score={new_score}, temperatura={temperatura}")
                        except Exception as e:
                            logger.error(f"Erro ao rodar scoring na negociação: {e}")
                            lead_dao.update_lead(db, lead.id, step_negociacao=True)
                            logger.info(f"Lead {lead.id} step_negociacao=True (sem scoring)")
                    elif result.get("current_score", 50) < 30:
                        lead_dao.update_lead(
                            db, lead.id,
                            status=LeadStatus.FRIO,
                            tags=list(set(lead.tags + ["frio"])),
                        )
                        self._add_tag_to_conversation_and_profile(
                            db, conversation_id, profile_id, "frio"
                        )
        except Exception as e:
            logger.error(f"Erro ao processar acoes do LangGraph: {e}")

    def _schedule_processing(
        self, wa_id: str, db_factory: Callable[[], Session], profile_id, conversation_id,
    ) -> None:
        with self._lock:
            pending = self._pending_messages.get(wa_id)
            if not pending:
                return
            if pending.timer:
                pending.timer.cancel()
            pending.timer = threading.Timer(
                self.timeout,
                self._process_consolidated_message,
                args=(wa_id, db_factory, profile_id, conversation_id),
            )
            pending.timer.start()

    def handle_text_message(
        self, wa_id: str, text: str, message_id: str, db: Session,
        db_factory: Callable[[], Session],
    ) -> None:
        profile = get_or_create(db, wa_id, None)
        conversation = get_or_create_open(db, profile.id)
        self.whatsapp.mark_as_read(message_id)

        if conversation.status == ConversationStatus.HUMAN:
            create_message(
                db, conversation_id=conversation.id, profile_id=profile.id,
                role="user", content=text,
            )
            logger.info(f"Mensagem de {wa_id} persistida (modo human takeover)")
            return

        import time
        with self._lock:
            if wa_id not in self._pending_messages:
                self._pending_messages[wa_id] = PendingMessage()
            pending = self._pending_messages[wa_id]
            pending.texts.append(text)
            pending.timestamp = time.time()

        self._schedule_processing(wa_id, db_factory, profile.id, conversation.id)
        logger.debug(f"Mensagem de texto adicionada a fila para {wa_id}")

    def handle_audio_message(self, wa_id: str, message_id: str) -> None:
        self.whatsapp.mark_as_read(message_id)
        self.whatsapp.send_text_message(wa_id, AUDIO_NOT_SUPPORTED_MESSAGE)
        logger.info(f"Mensagem de audio nao suportada enviada para {wa_id}")

    def handle_unsupported_message(self, wa_id: str, message_id: str, message_type: str) -> None:
        self.whatsapp.mark_as_read(message_id)
        unsupported_message = (
            f"Desculpe, ainda nao suportamos mensagens do tipo '{message_type}'. "
            "Por favor, envie sua mensagem em texto."
        )
        self.whatsapp.send_text_message(wa_id, unsupported_message)
        logger.info(f"Mensagem tipo '{message_type}' nao suportada para {wa_id}")

def extract_message_data(payload: WebhookPayload) -> tuple[str | None, str | None, str | None, str | None, str | None]:
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

message_handler = MessageHandler()
