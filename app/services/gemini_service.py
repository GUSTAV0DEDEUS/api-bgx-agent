from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import OpenAI

from app.utils.settings import settings, load_system_prompt


logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    pass


@dataclass
class ChatMessage:
    """Representa uma mensagem no formato OpenAI."""
    role: str  # 'user', 'assistant' ou 'system'
    content: str


class AIService:
    """
    Serviço para integração com APIs compatíveis com OpenAI.
    
    Suporta OpenAI nativo ou Gemini via endpoint compatível.
    Usa roles: 'user' para usuário, 'assistant' para respostas do modelo.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.openai_api_key or settings.gemini_api_key
        self.base_url = base_url or settings.openai_base_url
        self.model = model or settings.openai_model
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise AIServiceError("OPENAI_API_KEY ou GEMINI_API_KEY não configurada")
            
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def _build_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """
        Constrói lista de mensagens no formato OpenAI.
        Inclui system prompt se disponível.
        """
        result = []
        
        # Adiciona system prompt se existir
        system_prompt = load_system_prompt()
        if system_prompt:
            result.append({
                "role": "system",
                "content": system_prompt,
            })
        
        # Converte mensagens (agent -> assistant para API)
        for msg in messages:
            role = "assistant" if msg.role == "agent" else msg.role
            result.append({
                "role": role,
                "content": msg.content,
            })
        
        return result

    def chat(self, messages: list[ChatMessage]) -> str:
        """
        Envia histórico de mensagens e retorna a resposta.
        
        Args:
            messages: Lista de mensagens da conversa (role: user/agent)
            
        Returns:
            Texto da resposta do modelo
        """
        if not messages:
            raise AIServiceError("Nenhuma mensagem fornecida")

        try:
            client = self._get_client()
            api_messages = self._build_messages(messages)

            logger.debug(f"Enviando {len(api_messages)} mensagens para {self.model}")

            response = client.chat.completions.create(
                model=self.model,
                messages=api_messages, # type: ignore
            )

            result = response.choices[0].message.content or ""
            logger.debug("Resposta recebida do modelo")
            return result

        except Exception as e:
            logger.error(f"Erro ao chamar API: {e}")
            raise AIServiceError(f"Erro ao gerar resposta: {e}") from e

    def simple_chat(self, message: str) -> str:
        """
        Envia uma única mensagem sem histórico.
        
        Args:
            message: Mensagem do usuário
            
        Returns:
            Texto da resposta do modelo
        """
        return self.chat([ChatMessage(role="user", content=message)])


# Instância padrão para uso direto (lazy loading)
_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    """Retorna instância singleton do AIService."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


# Aliases para compatibilidade
GeminiService = AIService
GeminiServiceError = AIServiceError
get_gemini_service = get_ai_service
