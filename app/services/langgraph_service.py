"""
LangGraph Service - Orquestração de Agentes de Vendas

Este serviço implementa o fluxo de agentes usando LangGraph:
1. Onboarding Agent - Extrai nome/empresa/cargo naturalmente e cria lead
2. First Contact Agent - Discovery sem perguntas técnicas, entende o cliente
3. Negotiation Agent - Detecta interesse em proposta/reunião e ativa human takeover

Fluxo:
- Nova conversa sem lead → onboarding
- Conversa com lead existente → first_contact
- Cliente pergunta sobre reunião/orçamento → negotiation → human takeover
- Score < 30% após 2+ mensagens → human takeover (lead frio)
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, Literal, Annotated, Any, cast

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END

from app.utils.settings import settings


logger = logging.getLogger(__name__)


# ============================================
# TIPOS E ESTADOS
# ============================================

class LeadInfo(TypedDict, total=False):
    """Informações extraídas do lead."""
    first_name: str | None
    last_name: str | None
    nome_empresa: str | None
    cargo: str | None
    tags: list[str]
    notes: str | None


class ConversationState(TypedDict):
    """Estado da conversa no grafo."""
    messages: list[BaseMessage]
    profile_id: str
    conversation_id: str
    lead: LeadInfo | None
    lead_id: str | None
    pipeline_stage: str
    should_create_lead: bool
    should_human_takeover: bool
    user_message_count: int
    negative_score_count: int
    current_score: int
    response: str
    first_name: str | None
    tone_instructions: str
    emoji_instructions: str
    greeting_instructions: str
    response_style_instructions: str


PipelineStage = Literal["onboarding", "first_contact", "negotiation"]


# ============================================
# PROMPTS
# ============================================

def _load_prompt(filename: str) -> str:
    """Carrega prompt da pasta instructions."""
    path = Path(__file__).parent.parent / "instructions" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning(f"Prompt file not found: {path}")
    return ""


def _safe_format(template: str, **kwargs) -> str:
    """Formata template de forma segura, substituindo apenas placeholders conhecidos.

    Usa substituição manual em vez de str.format() para evitar KeyError
    quando o template contém chaves literais (ex: JSON nos exemplos do prompt).
    """
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        if value is None:
            replacement = "Não informado"
        else:
            replacement = str(value)
        result = result.replace(placeholder, replacement)
    return result


def _get_lead_field(lead: Any, field_name: str, default: str = "Não informado") -> str:
    if not lead:
        return default
    value = lead.get(field_name)
    if value is None or value == "":
        return default
    return str(value)


# Carrega prompts dos arquivos .md
ONBOARDING_PROMPT_TEMPLATE = _load_prompt("system_prompt_onboarding.md")
FIRST_CONTACT_PROMPT_TEMPLATE = _load_prompt("system_prompt_first_contact.md")
NEGOTIATION_PROMPT_TEMPLATE = _load_prompt("system_prompt_negotiation.md")


# ============================================
# LANGGRAPH SERVICE
# ============================================

class LangGraphService:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model_name = model or "gemini-2.5-flash-lite"
        self.api_key = api_key or settings.gemini_api_key
        self._llm: ChatGoogleGenerativeAI | None = None
        self._graph: StateGraph | None = None
        self._compiled_graph = None

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        if self._llm is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY não configurada")
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=0.7,
            )
        return self._llm

    @property
    def graph(self):
        if self._compiled_graph is None:
            self._compiled_graph = self._build_graph()
        return self._compiled_graph

    def _build_graph(self):
        workflow = StateGraph(ConversationState)

        # 3 nós: onboarding, first_contact, negotiation
        workflow.add_node("onboarding", self._onboarding_node)
        workflow.add_node("first_contact", self._first_contact_node)
        workflow.add_node("negotiation", self._negotiation_node)

        # Entry point condicional
        workflow.set_conditional_entry_point(
            self._route_entry,
            {
                "onboarding": "onboarding",
                "first_contact": "first_contact",
                "negotiation": "negotiation",
            }
        )

        # Transições após onboarding
        workflow.add_conditional_edges(
            "onboarding",
            self._route_after_onboarding,
            {
                "first_contact": "first_contact",
                "onboarding": END,
                "human": END,
            }
        )

        # Transições após first_contact
        workflow.add_conditional_edges(
            "first_contact",
            self._route_after_first_contact,
            {
                "negotiation": "negotiation",
                "first_contact": END,
                "human": END,
            }
        )

        # Negotiation sempre termina (human takeover)
        workflow.add_edge("negotiation", END)

        return workflow.compile()

    # ============================================
    # ROTEAMENTO
    # ============================================

    def _route_entry(self, state: ConversationState) -> str:
        """Determina o nó de entrada baseado no estado."""
        if state.get("should_human_takeover"):
            return "negotiation"
        if not state.get("lead_id"):
            return "onboarding"
        stage = state.get("pipeline_stage", "first_contact")
        if stage == "negotiation":
            return "negotiation"
        return "first_contact"

    def _route_after_onboarding(self, state: ConversationState) -> str:
        """Roteamento após onboarding."""
        if state.get("should_human_takeover"):
            return "human"
        if state.get("should_create_lead"):
            return "first_contact"
        return "onboarding"

    def _route_after_first_contact(self, state: ConversationState) -> str:
        """Roteamento após first_contact."""
        if state.get("should_human_takeover"):
            return "human"
        response = state.get("response", "")
        if "[NEGOTIATION_DETECTED]true[/NEGOTIATION_DETECTED]" in response:
            return "negotiation"
        return "first_contact"

    # ============================================
    # HELPERS
    # ============================================

    def _format_context(self, messages: list[BaseMessage]) -> str:
        """Formata histórico de mensagens para contexto."""
        lines = []
        for msg in messages[-10:]:
            role = "Cliente" if isinstance(msg, HumanMessage) else "Agente"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    # ============================================
    # NÓS DO GRAFO
    # ============================================

    def _onboarding_node(self, state: ConversationState) -> ConversationState:
        """Nó de onboarding: extrai nome, empresa, cargo naturalmente."""
        logger.info("Entrando no onboarding_node")
        try:
            context = self._format_context(state["messages"])
            prompt = _safe_format(
                ONBOARDING_PROMPT_TEMPLATE,
                context=context,
                tone_instructions=state.get("tone_instructions", ""),
                emoji_instructions=state.get("emoji_instructions", ""),
                greeting_instructions=state.get("greeting_instructions", ""),
                response_style_instructions=state.get("response_style_instructions", ""),
            )

            messages = [SystemMessage(content=prompt), *state["messages"]]
            response = self.llm.invoke(messages)
            response_text = str(response.content)

            new_state = dict(state)
            new_state["response"] = response_text

            # Extrai dados do lead
            if "[LEAD_DATA]" in response_text and "[/LEAD_DATA]" in response_text:
                try:
                    start = response_text.index("[LEAD_DATA]") + len("[LEAD_DATA]")
                    end = response_text.index("[/LEAD_DATA]")
                    lead_json = response_text[start:end].strip()
                    lead_data = json.loads(lead_json)

                    new_state["lead"] = lead_data
                    new_state["should_create_lead"] = True
                    new_state["first_name"] = lead_data.get("first_name", state.get("first_name"))

                    # Remove marcador da resposta
                    full_marker = f"[LEAD_DATA]{lead_json}[/LEAD_DATA]"
                    response_text = response_text.replace(full_marker, "").strip()
                    new_state["response"] = response_text
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Erro ao parsear LEAD_DATA: {e}")

            new_state = self._check_negative_signal(new_state, response_text)
            return cast(ConversationState, new_state)
        except Exception as e:
            import traceback
            logger.error(f"Erro no onboarding_node: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _first_contact_node(self, state: ConversationState) -> ConversationState:
        """Nó de primeiro contato: discovery sem perguntas técnicas."""
        logger.info("Entrando no first_contact_node")
        try:
            lead = state.get("lead")
            first_name = state.get("first_name") or _get_lead_field(lead, "first_name")
            context = self._format_context(state["messages"])

            prompt = _safe_format(
                FIRST_CONTACT_PROMPT_TEMPLATE,
                first_name=first_name,
                nome_empresa=_get_lead_field(lead, "nome_empresa"),
                cargo=_get_lead_field(lead, "cargo"),
                context=context,
                tone_instructions=state.get("tone_instructions", ""),
                emoji_instructions=state.get("emoji_instructions", ""),
                response_style_instructions=state.get("response_style_instructions", ""),
            )

            messages = [SystemMessage(content=prompt), *state["messages"]]
            response = self.llm.invoke(messages)
            response_text = str(response.content)

            new_state = dict(state)
            new_state["response"] = response_text

            # Detecta intenção de negociação
            if "[NEGOTIATION_DETECTED]true[/NEGOTIATION_DETECTED]" in response_text:
                new_state["pipeline_stage"] = "negotiation"
                new_state["should_human_takeover"] = True
                response_text = response_text.replace(
                    "[NEGOTIATION_DETECTED]true[/NEGOTIATION_DETECTED]", ""
                ).strip()
                new_state["response"] = response_text

            new_state = self._check_negative_signal(new_state, response_text)
            new_state = self._extract_tags(new_state, response_text)
            return cast(ConversationState, new_state)
        except Exception as e:
            import traceback
            logger.error(f"Erro no first_contact_node: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _negotiation_node(self, state: ConversationState) -> ConversationState:
        """Nó de negociação: mensagem de transição para humano."""
        logger.info("Entrando no negotiation_node")
        try:
            lead = state.get("lead")
            first_name = state.get("first_name") or _get_lead_field(lead, "first_name")
            context = self._format_context(state["messages"])

            prompt = _safe_format(
                NEGOTIATION_PROMPT_TEMPLATE,
                first_name=first_name,
                nome_empresa=_get_lead_field(lead, "nome_empresa"),
                cargo=_get_lead_field(lead, "cargo"),
                context=context,
                tone_instructions=state.get("tone_instructions", ""),
                emoji_instructions=state.get("emoji_instructions", ""),
                response_style_instructions=state.get("response_style_instructions", ""),
            )

            messages = [SystemMessage(content=prompt), *state["messages"]]
            response = self.llm.invoke(messages)

            new_state = dict(state)
            new_state["response"] = str(response.content)
            new_state["should_human_takeover"] = True
            new_state["pipeline_stage"] = "negotiation"
            return cast(ConversationState, new_state)
        except Exception as e:
            import traceback
            logger.error(f"Erro no negotiation_node: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    # ============================================
    # CHECAGENS E EXTRAÇÃO
    # ============================================

    def _check_negative_signal(self, state: dict, response_text: str) -> dict:
        """Verifica sinais negativos na resposta e ajusta score."""
        if "[NEGATIVE_SIGNAL]true[/NEGATIVE_SIGNAL]" in response_text:
            state["negative_score_count"] = state.get("negative_score_count", 0) + 1
            state["current_score"] = max(0, state.get("current_score", 50) - 20)
            state["response"] = response_text.replace(
                "[NEGATIVE_SIGNAL]true[/NEGATIVE_SIGNAL]", ""
            ).strip()

            if state["current_score"] < 30 and state.get("user_message_count", 0) >= 2:
                state["should_human_takeover"] = True
                lead = state.get("lead") or {}
                tags = lead.get("tags", [])
                if "frio" not in tags:
                    tags.append("frio")
                    lead["tags"] = tags
                    state["lead"] = lead
        return state

    def _extract_tags(self, state: dict, response_text: str) -> dict:
        """Extrai tags da resposta."""
        import re
        tag_pattern = r'\[ADD_TAG\]\s*(\{.*?\})\s*\[/ADD_TAG\]'
        matches = re.findall(tag_pattern, response_text, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                tag = data.get("tag")
                if tag:
                    lead = state.get("lead") or {}
                    tags = lead.get("tags", [])
                    if tag not in tags and len(tags) < 5:
                        tags.append(tag)
                        lead["tags"] = tags
                        state["lead"] = lead
            except json.JSONDecodeError:
                pass

        state["response"] = re.sub(tag_pattern, "", state.get("response", "")).strip()
        return state

    # ============================================
    # ENTRY POINT PÚBLICO
    # ============================================

    def process_message(
        self,
        messages: list[dict],
        profile_id: str,
        conversation_id: str,
        lead_id: str | None = None,
        lead_info: dict | None = None,
        pipeline_stage: str = "onboarding",
        user_message_count: int = 1,
        first_name: str | None = None,
        tone_instructions: str = "",
        emoji_instructions: str = "",
        greeting_instructions: str = "",
        response_style_instructions: str = "",
    ) -> ConversationState:
        """Processa uma mensagem através do grafo LangGraph."""
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            else:
                langchain_messages.append(AIMessage(content=msg["content"]))

        initial_state: dict[str, Any] = {
            "messages": langchain_messages,
            "profile_id": profile_id,
            "conversation_id": conversation_id,
            "lead": lead_info,
            "lead_id": lead_id,
            "pipeline_stage": pipeline_stage,
            "should_create_lead": False,
            "should_human_takeover": False,
            "user_message_count": user_message_count,
            "negative_score_count": 0,
            "current_score": 50,
            "response": "",
            "first_name": first_name,
            "tone_instructions": tone_instructions,
            "emoji_instructions": emoji_instructions,
            "greeting_instructions": greeting_instructions,
            "response_style_instructions": response_style_instructions,
        }

        try:
            logger.info(
                f"Iniciando LangGraph para conversation {conversation_id}, stage: {pipeline_stage}"
            )
            result = self.graph.invoke(cast(ConversationState, initial_state))
            logger.info(
                f"LangGraph concluído com sucesso. Response: {result.get('response', '')[:100]}..."
            )
            return cast(ConversationState, result)
        except Exception as e:
            import traceback
            logger.error(f"Erro ao processar mensagem no LangGraph: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            initial_state["response"] = "Desculpe, ocorreu um erro. Pode repetir?"
            return cast(ConversationState, initial_state)


_langgraph_service: LangGraphService | None = None


def get_langgraph_service() -> LangGraphService:
    global _langgraph_service
    if _langgraph_service is None:
        _langgraph_service = LangGraphService()
    return _langgraph_service
