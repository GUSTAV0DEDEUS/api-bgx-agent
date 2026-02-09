from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.dao import agent_config_dao
from app.entities.agent_config_entity import AgentConfig

logger = logging.getLogger(__name__)

def get_config(db: Session) -> AgentConfig:
    return agent_config_dao.get_config(db)

def update_config(
    db: Session,
    tone: str | None = None,
    use_emojis: str | None = None,
    response_style: str | None = None,
    greeting_style: str | None = None,
    max_message_length: int | None = None,
) -> AgentConfig:
    config = agent_config_dao.update_config(
        db,
        tone=tone,
        use_emojis=use_emojis,
        response_style=response_style,
        greeting_style=greeting_style,
        max_message_length=max_message_length,
    )
    logger.info(f"Configuracao do agente atualizada: tone={config.tone}, emojis={config.use_emojis}")
    return config

def build_tone_instructions(config: AgentConfig) -> str:
    tone_map = {
        "profissional": (
            "Use um tom profissional e confiante. "
            "Seja educado e objetivo. Evite girias e informalidades excessivas. "
            "Transmita credibilidade e competencia."
        ),
        "descontraido": (
            "Use um tom descontraido e leve. "
            "Seja amigavel e acessivel. Pode usar expressoes informais e humor leve. "
            "Faca o cliente se sentir a vontade."
        ),
        "tecnico": (
            "Use um tom tecnico e preciso. "
            "Seja direto e informativo. Use termos do mercado quando apropriado. "
            "Demonstre expertise e conhecimento profundo."
        ),
        "amigavel": (
            "Use um tom amigavel e acolhedor. "
            "Seja caloroso e empatetico. Mostre interesse genuino pelo cliente. "
            "Crie conexao pessoal e rapport."
        ),
    }
    return tone_map.get(config.tone, tone_map["profissional"])

def build_emoji_instructions(config: AgentConfig) -> str:
    emoji_map = {
        "sempre": (
            "Use emojis frequentemente nas mensagens para tornar a conversa mais expressiva. "
            "Inclua emojis relevantes ao contexto (ex: 🚀 para crescimento, ✅ para confirmacao, "
            "💡 para ideias, 📊 para dados)."
        ),
        "moderado": (
            "Use emojis com moderacao. Inclua 1-2 emojis por mensagem quando fizer sentido. "
            "Nao exagere. Use apenas em momentos que reforcem a mensagem."
        ),
        "nunca": (
            "NAO use emojis em nenhuma mensagem. Mantenha o texto limpo e puramente textual."
        ),
    }
    return emoji_map.get(config.use_emojis, emoji_map["moderado"])

def build_greeting_instructions(config: AgentConfig) -> str:
    greeting_map = {
        "caloroso": "Cumprimente o cliente de forma calorosa e acolhedora. Use o primeiro nome quando disponivel.",
        "neutro": "Cumprimente de forma neutra e educada. Use saudacoes padrao como 'Ola' ou 'Bom dia'.",
        "objetivo": "Va direto ao ponto sem saudacoes longas. Seja breve e objetivo na abertura.",
    }
    return greeting_map.get(config.greeting_style, greeting_map["caloroso"])

def build_response_style_instructions(config: AgentConfig) -> str:
    style_map = {
        "formal": (
            "Responda de forma formal e estruturada. "
            "Use linguagem culta e frases bem construidas."
        ),
        "conversacional": (
            "Responda de forma conversacional e natural. "
            "Frases curtas e quebradas, como em uma conversa real de WhatsApp. "
            "Evite paragrafos longos."
        ),
        "consultivo": (
            "Responda como um consultor especializado. "
            "Faca perguntas estrategicas, oferca insights e guie o cliente. "
            "Demonstre autoridade no assunto."
        ),
        "direto": (
            "Seja extremamente direto e conciso. "
            "Nada de rodeios. Responda com o minimo necessario. "
            "Foque na informacao essencial."
        ),
    }
    return style_map.get(config.response_style, style_map["conversacional"])
