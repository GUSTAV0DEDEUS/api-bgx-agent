from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy.orm import Session

from app.dao import message_dao
from app.utils.settings import settings, load_scoring_prompt

logger = logging.getLogger(__name__)

class LeadScoringError(RuntimeError):
    pass

@dataclass
class LeadData:
    nome_cliente: str | None
    nome_empresa: str | None
    cargo: str | None
    telefone: str | None
    tags: list[str]
    notes: str | None

class LeadScoringService:

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url
        self.model = model or settings.model
        self.max_retries = max_retries
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise LeadScoringError("API key não configurada")
            
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def _build_context(
        self,
        conversation_history: list[dict],
        lead_data: LeadData,
    ) -> str:
        context_parts = []
        
        context_parts.append("## Histórico da Conversa\n")
        for msg in conversation_history:
            role = "Cliente" if msg["role"] == "user" else "Agente"
            context_parts.append(f"**{role}:** {msg['content']}\n")
        
        context_parts.append("\n## Dados do Lead\n")
        if lead_data.nome_cliente:
            context_parts.append(f"- Nome: {lead_data.nome_cliente}")
        if lead_data.nome_empresa:
            context_parts.append(f"- Empresa: {lead_data.nome_empresa}")
        if lead_data.cargo:
            context_parts.append(f"- Cargo: {lead_data.cargo}")
        if lead_data.tags:
            context_parts.append(f"- Tags: {', '.join(lead_data.tags)}")
        if lead_data.notes:
            context_parts.append(f"- Observações: {lead_data.notes}")
        
        return "\n".join(context_parts)

    def _parse_score_response(self, response_text: str) -> dict:
        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                result = json.loads(json_str)
                
                score = result.get("score", 50)
                if not isinstance(score, (int, float)):
                    score = 50
                score = max(0, min(100, int(score)))
                
                return {
                    "score": score,
                    "breakdown": result.get("breakdown", {}),
                    "justificativa": result.get("justificativa", ""),
                }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Falha ao parsear resposta de scoring: {e}")
        
        return {"score": 50, "breakdown": {}, "justificativa": "Não foi possível analisar"}

    def calculate_score(
        self,
        db: Session,
        conversation_id: uuid.UUID,
        lead_data: LeadData,
    ) -> dict:
        messages = message_dao.get_messages_by_conversation_id(db, conversation_id, limit=50)
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        if not conversation_history:
            logger.warning(f"Conversa {conversation_id} sem mensagens para scoring")
            return {"score": 50, "breakdown": {}, "justificativa": "Sem histórico de conversa"}
        
        context = self._build_context(conversation_history, lead_data)
        
        last_error = None
        backoff_times = [1, 2, 4]
        
        for attempt in range(self.max_retries):
            try:
                client = self._get_client()
                scoring_prompt = load_scoring_prompt()
                
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": scoring_prompt},
                        {"role": "user", "content": context},
                    ],
                )
                
                response_text = response.choices[0].message.content or ""
                result = self._parse_score_response(response_text)
                
                logger.info(f"Score calculado para lead da conversa {conversation_id}: {result['score']}")
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Tentativa {attempt + 1}/{self.max_retries} de scoring falhou: {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(backoff_times[attempt])
        
        logger.error(f"Todas as tentativas de scoring falharam: {last_error}")
        return {
            "score": 50,
            "breakdown": {},
            "justificativa": f"Fallback: erro no cálculo ({last_error})",
        }

_lead_scoring_service: LeadScoringService | None = None

def get_lead_scoring_service() -> LeadScoringService:
    global _lead_scoring_service
    if _lead_scoring_service is None:
        _lead_scoring_service = LeadScoringService()
    return _lead_scoring_service
