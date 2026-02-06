"""
LangGraph Service - Orquestração de Agentes de Vendas

Este serviço implementa o fluxo de agentes usando LangGraph:
1. Qualify Agent - Extrai nome/empresa/cargo e cria lead
2. First Contact Agent - Discovery e explicação da solução  
3. Conversion Agent - Detecta interesse em proposta e ativa human takeover

Fluxo:
- Nova conversa sem lead → qualify
- Conversa com lead existente → first_contact
- Cliente pronto para proposta → conversion → human takeover
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
    nome_cliente: str | None
    nome_empresa: str | None
    cargo: str | None
    tags: list[str]
    notes: str | None


class ConversationState(TypedDict):
    """Estado da conversa no grafo."""
    messages: list[BaseMessage]           # Histórico de mensagens
    profile_id: str                        # UUID do profile
    conversation_id: str                   # UUID da conversa
    lead: LeadInfo | None                  # Dados do lead (se existir)
    lead_id: str | None                    # UUID do lead (se existir)
    pipeline_stage: str                    # "qualify" | "first_contact" | "conversion"
    should_create_lead: bool               # Se deve criar lead
    should_human_takeover: bool            # Se deve ativar human takeover
    user_message_count: int                # Contador de mensagens do usuário
    negative_score_count: int              # Contador de respostas negativas
    current_score: int                     # Score atual (0-100, 50 = neutro)
    response: str                          # Resposta gerada


PipelineStage = Literal["qualify", "first_contact", "conversion"]


# ============================================
# PROMPTS
# ============================================

def _load_prompt(filename: str) -> str:
    """Carrega prompt da pasta instructions."""
    path = Path(__file__).parent.parent / "instructions" / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _safe_format(template: str, **kwargs) -> str:
    """
    Formata template de forma segura, tratando valores None e caracteres especiais.
    """
    safe_kwargs = {}
    for key, value in kwargs.items():
        if value is None:
            safe_kwargs[key] = "Não informado"
        elif isinstance(value, str):
            # Escapa chaves para evitar problemas com .format()
            safe_kwargs[key] = value.replace("{", "{{").replace("}", "}}")
        else:
            safe_kwargs[key] = str(value)
    return template.format(**safe_kwargs)


def _get_lead_field(lead: dict | None, field: str, default: str = "Não informado") -> str:
    """Obtém campo do lead de forma segura."""
    if not lead:
        return default
    value = lead.get(field)
    if value is None or value == "":
        return default
    return str(value)


QUALIFY_PROMPT = """Você é um agente de qualificação de leads da BGX Group.

## OBJETIVO
Extrair naturalmente durante a conversa:
- Nome do cliente
- Nome da empresa
- Cargo/função

## TOM DE VOZ
- Direto, sem formalidade excessiva
- Frases curtas e quebradas
- Usa emoji com moderação

## REGRAS
1. NÃO pergunte tudo de uma vez - extraia nas respostas naturais
2. Quando tiver os 3 dados (nome, empresa, cargo), inclua no final:
   [LEAD_DATA]{{"nome_cliente": "...", "nome_empresa": "...", "cargo": "..."}}[/LEAD_DATA]
3. Se o cliente demonstrar desinteresse forte (score < 30), inclua:
   [NEGATIVE_SIGNAL]true[/NEGATIVE_SIGNAL]
4. Continue a conversa normalmente após extrair dados

## EXEMPLOS DE EXTRAÇÃO NATURAL
Cliente: "Sou o João da Tech Corp"
→ Extraiu: nome=João, empresa=Tech Corp

Cliente: "Trabalho como diretor comercial"
→ Extraiu: cargo=diretor comercial

## CONTEXTO ATUAL
{context}
"""

FIRST_CONTACT_PROMPT = """Você é um agente de vendas da BGX Group.

## OBJETIVO
- Entender a dor/necessidade do cliente
- Explicar como a solução resolve o problema
- Qualificar se está pronto para proposta

## TOM DE VOZ
- Direto, sem enrolação
- Frases curtas
- Foco em resultado, não em features

## REGRAS
1. Faça perguntas de discovery:
   - "Quantos leads chegam por dia?"
   - "Quem atende hoje?"
   - "Quanto tempo demora pra responder?"
2. Quando cliente demonstrar interesse em proposta/orçamento, inclua:
   [READY_FOR_PROPOSAL]true[/READY_FOR_PROPOSAL]
3. Se cliente mostrar resistência ou desinteresse, inclua:
   [NEGATIVE_SIGNAL]true[/NEGATIVE_SIGNAL]
4. Atualize tags quando identificar comportamento:
   [ADD_TAG]{{"tag": "quente"}}[/ADD_TAG]

## CONTEXTO DO LEAD
Nome: {nome_cliente}
Empresa: {nome_empresa}
Cargo: {cargo}

## CONVERSA ATUAL
{context}
"""

CONVERSION_PROMPT = """Você é um agente de conversão da BGX Group.

## OBJETIVO
O cliente demonstrou interesse em proposta. Sua última mensagem deve:
- Confirmar o interesse
- Informar que um consultor especializado entrará em contato

## TOM DE VOZ
- Profissional mas amigável
- Transmitir confiança

## REGRAS
1. NÃO tente vender ou dar preço
2. Apenas confirme e prepare para handoff
3. Sua resposta será a última antes do consultor assumir

## CONTEXTO DO LEAD
Nome: {nome_cliente}
Empresa: {nome_empresa}
Cargo: {cargo}

## CONVERSA ATUAL
{context}
"""


# ============================================
# LANGGRAPH SERVICE
# ============================================

class LangGraphService:
    """
    Serviço de orquestração de agentes usando LangGraph.
    
    Implementa StateGraph com 3 nodes:
    - qualify: extrai dados e cria lead
    - first_contact: discovery e qualificação
    - conversion: handoff para consultor
    """
    
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model_name = model or "gemini-2.5-flash-lite"
        self.api_key = api_key or settings.gemini_api_key
        self._llm: ChatGoogleGenerativeAI | None = None
        self._graph: StateGraph | None = None
        self._compiled_graph = None
    
    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        """Lazy loading do LLM."""
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
        """Lazy loading do grafo compilado."""
        if self._compiled_graph is None:
            self._compiled_graph = self._build_graph()
        return self._compiled_graph
    
    def _build_graph(self):
        """Constrói o StateGraph."""
        workflow = StateGraph(ConversationState)
        
        # Adiciona nodes
        workflow.add_node("qualify", self._qualify_node)
        workflow.add_node("first_contact", self._first_contact_node)
        workflow.add_node("conversion", self._conversion_node)
        
        # Define entry point condicional
        workflow.set_conditional_entry_point(
            self._route_entry,
            {
                "qualify": "qualify",
                "first_contact": "first_contact",
                "conversion": "conversion",
            }
        )
        
        # Transições condicionais
        workflow.add_conditional_edges(
            "qualify",
            self._route_after_qualify,
            {
                "first_contact": "first_contact",
                "qualify": END,  # Continua em qualify, retorna resposta
                "human": END,    # Handoff para humano
            }
        )
        
        workflow.add_conditional_edges(
            "first_contact",
            self._route_after_first_contact,
            {
                "conversion": "conversion",
                "first_contact": END,
                "human": END,
            }
        )
        
        workflow.add_edge("conversion", END)
        
        return workflow.compile()
    
    def _route_entry(self, state: ConversationState) -> str:
        """Determina o node inicial baseado no estado."""
        # Se já tem should_human_takeover, vai direto pro fim
        if state.get("should_human_takeover"):
            return "conversion"
        
        # Se não tem lead, começa em qualify
        if not state.get("lead_id"):
            return "qualify"
        
        # Se tem lead, verifica stage
        stage = state.get("pipeline_stage", "first_contact")
        if stage == "conversion":
            return "conversion"
        
        return "first_contact"
    
    def _route_after_qualify(self, state: ConversationState) -> str:
        """Decide próximo passo após qualify."""
        # Se precisa de human takeover (score baixo)
        if state.get("should_human_takeover"):
            return "human"
        
        # Se criou lead, vai para first_contact
        if state.get("should_create_lead"):
            return "first_contact"
        
        # Continua em qualify
        return "qualify"
    
    def _route_after_first_contact(self, state: ConversationState) -> str:
        """Decide próximo passo após first_contact."""
        if state.get("should_human_takeover"):
            return "human"
        
        # Verifica se está pronto para proposta
        if "[READY_FOR_PROPOSAL]true[/READY_FOR_PROPOSAL]" in state.get("response", ""):
            return "conversion"
        
        return "first_contact"
    
    def _format_context(self, messages: list[BaseMessage]) -> str:
        """Formata histórico de mensagens para contexto."""
        lines = []
        for msg in messages[-10:]:  # Últimas 10 mensagens
            role = "Cliente" if isinstance(msg, HumanMessage) else "Agente"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
    
    def _qualify_node(self, state: ConversationState) -> ConversationState:
        """Node de qualificação - extrai dados do lead."""
        logger.info("Entrando no qualify_node")
        try:
            context = self._format_context(state["messages"])
            logger.debug(f"Contexto formatado: {context[:200]}...")
            
            prompt = _safe_format(QUALIFY_PROMPT, context=context)
            logger.debug("Prompt formatado com sucesso")
            
            messages = [
                SystemMessage(content=prompt),
                *state["messages"]
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content
            
            # Processa resposta
            new_state = dict(state)
            new_state["response"] = response_text
            
            # Extrai dados do lead se presente
            if "[LEAD_DATA]" in response_text and "[/LEAD_DATA]" in response_text:
                try:
                    start = response_text.index("[LEAD_DATA]") + len("[LEAD_DATA]")
                    end = response_text.index("[/LEAD_DATA]")
                    lead_json = response_text[start:end].strip()
                    lead_data = json.loads(lead_json)
                    
                    new_state["lead"] = lead_data
                    new_state["should_create_lead"] = True
                    
                    # Limpa marcadores da resposta
                    response_text = response_text.replace(f"[LEAD_DATA]{lead_json}[/LEAD_DATA]", "").strip()
                    new_state["response"] = response_text
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Erro ao parsear LEAD_DATA: {e}")
            
            # Verifica sinal negativo
            new_state = self._check_negative_signal(new_state, response_text)
            
            logger.info(f"qualify_node concluído. should_create_lead={new_state.get('should_create_lead')}")
            return cast(ConversationState, new_state)
            
        except Exception as e:
            import traceback
            logger.error(f"Erro no qualify_node: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _first_contact_node(self, state: ConversationState) -> ConversationState:
        """Node de primeiro contato - discovery e qualificação."""
        logger.info("Entrando no first_contact_node")
        try:
            lead = state.get("lead")
            context = self._format_context(state["messages"])
            logger.debug(f"Lead info: {lead}")
            
            prompt = _safe_format(
                FIRST_CONTACT_PROMPT,
                nome_cliente=_get_lead_field(lead, "nome_cliente"),
                nome_empresa=_get_lead_field(lead, "nome_empresa"),
                cargo=_get_lead_field(lead, "cargo"),
                context=context,
            )
            
            messages = [
                SystemMessage(content=prompt),
                *state["messages"]
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content
            
            new_state = dict(state)
            new_state["response"] = response_text
            
            # Verifica se está pronto para proposta
            if "[READY_FOR_PROPOSAL]true[/READY_FOR_PROPOSAL]" in response_text:
                new_state["pipeline_stage"] = "conversion"
                new_state["should_human_takeover"] = True
                response_text = response_text.replace("[READY_FOR_PROPOSAL]true[/READY_FOR_PROPOSAL]", "").strip()
                new_state["response"] = response_text
            
            # Verifica sinal negativo
            new_state = self._check_negative_signal(new_state, response_text)
            
            # Extrai tags
            new_state = self._extract_tags(new_state, response_text)
            
            logger.info(f"first_contact_node concluído. should_human_takeover={new_state.get('should_human_takeover')}")
            return cast(ConversationState, new_state)
            
        except Exception as e:
            import traceback
            logger.error(f"Erro no first_contact_node: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _conversion_node(self, state: ConversationState) -> ConversationState:
        """Node de conversão - prepara handoff para consultor."""
        logger.info("Entrando no conversion_node")
        try:
            lead = state.get("lead")
            context = self._format_context(state["messages"])
            logger.debug(f"Lead info: {lead}")
            
            prompt = _safe_format(
                CONVERSION_PROMPT,
                nome_cliente=_get_lead_field(lead, "nome_cliente"),
                nome_empresa=_get_lead_field(lead, "nome_empresa"),
                cargo=_get_lead_field(lead, "cargo"),
                context=context,
            )
            
            messages = [
                SystemMessage(content=prompt),
                *state["messages"]
            ]
            
            response = self.llm.invoke(messages)
            
            new_state = dict(state)
            new_state["response"] = response.content
            new_state["should_human_takeover"] = True
            new_state["pipeline_stage"] = "conversion"
            
            logger.info("conversion_node concluído")
            return cast(ConversationState, new_state)
            
        except Exception as e:
            import traceback
            logger.error(f"Erro no conversion_node: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _check_negative_signal(self, state: dict, response_text: str) -> dict:
        """Verifica e processa sinais negativos."""
        if "[NEGATIVE_SIGNAL]true[/NEGATIVE_SIGNAL]" in response_text:
            state["negative_score_count"] = state.get("negative_score_count", 0) + 1
            state["current_score"] = max(0, state.get("current_score", 50) - 20)
            
            # Remove marcador da resposta
            state["response"] = response_text.replace("[NEGATIVE_SIGNAL]true[/NEGATIVE_SIGNAL]", "").strip()
            
            # Se score < 30 e já teve 2+ mensagens, ativa human takeover
            if state["current_score"] < 30 and state.get("user_message_count", 0) >= 2:
                state["should_human_takeover"] = True
                # Adiciona tag de lead frio
                lead = state.get("lead") or {}
                tags = lead.get("tags", [])
                if "frio" not in tags:
                    tags.append("frio")
                    lead["tags"] = tags
                    state["lead"] = lead
        
        return state
    
    def _extract_tags(self, state: dict, response_text: str) -> dict:
        """Extrai e processa tags da resposta."""
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
        
        # Limpa marcadores
        state["response"] = re.sub(tag_pattern, "", state.get("response", "")).strip()
        
        return state
    
    def process_message(
        self,
        messages: list[dict],
        profile_id: str,
        conversation_id: str,
        lead_id: str | None = None,
        lead_info: dict | None = None,
        pipeline_stage: str = "qualify",
        user_message_count: int = 1,
    ) -> ConversationState:
        """
        Processa uma mensagem através do grafo de agentes.
        
        Args:
            messages: Lista de mensagens no formato [{"role": "user/agent", "content": "..."}]
            profile_id: UUID do profile
            conversation_id: UUID da conversa
            lead_id: UUID do lead (se existir)
            lead_info: Dados do lead (se existir)
            pipeline_stage: Estágio atual do pipeline
            user_message_count: Número de mensagens do usuário
            
        Returns:
            Estado final com resposta gerada e flags de ação
        """
        # Converte mensagens para formato LangChain
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            else:
                langchain_messages.append(AIMessage(content=msg["content"]))
        
        # Prepara estado inicial
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
            "current_score": 50,  # Neutro
            "response": "",
        }
        
        # Executa o grafo
        try:
            logger.info(f"Iniciando LangGraph para conversation {conversation_id}, stage: {pipeline_stage}")
            result = self.graph.invoke(initial_state)
            logger.info(f"LangGraph concluído com sucesso. Response: {result.get('response', '')[:100]}...")
            return result
        except Exception as e:
            import traceback
            logger.error(f"Erro ao processar mensagem no LangGraph: {e}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            # Retorna estado com erro
            initial_state["response"] = "Desculpe, ocorreu um erro. Pode repetir?"
            return initial_state


# Singleton
_langgraph_service: LangGraphService | None = None


def get_langgraph_service() -> LangGraphService:
    """Retorna instância singleton do LangGraphService."""
    global _langgraph_service
    if _langgraph_service is None:
        _langgraph_service = LangGraphService()
    return _langgraph_service
