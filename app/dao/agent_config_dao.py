from __future__ import annotations

from sqlalchemy.orm import Session

from app.entities.agent_config_entity import (
    AgentConfig,
    EmojiUsageEnum,
    GreetingStyleEnum,
    ResponseStyleEnum,
    ToneEnum,
)

def get_config(db: Session) -> AgentConfig:
    config = db.query(AgentConfig).first()
    if config:
        return config
    config = AgentConfig(
        tone=ToneEnum.PROFISSIONAL.value,
        use_emojis=EmojiUsageEnum.MODERADO.value,
        response_style=ResponseStyleEnum.CONVERSACIONAL.value,
        greeting_style=GreetingStyleEnum.CALOROSO.value,
        max_message_length=300,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

def update_config(
    db: Session,
    tone: str | None = None,
    use_emojis: str | None = None,
    response_style: str | None = None,
    greeting_style: str | None = None,
    max_message_length: int | None = None,
) -> AgentConfig:
    config = get_config(db)
    if tone is not None:
        config.tone = tone
    if use_emojis is not None:
        config.use_emojis = use_emojis
    if response_style is not None:
        config.response_style = response_style
    if greeting_style is not None:
        config.greeting_style = greeting_style
    if max_message_length is not None:
        config.max_message_length = max_message_length
    db.commit()
    db.refresh(config)
    return config
