from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.entities.profile_entity import Profile


# Constante: máximo de tags por profile
MAX_PROFILE_TAGS = 3


def get_by_whatsapp_number(db: Session, whatsapp_number: str) -> Profile | None:
    return db.query(Profile).filter(Profile.whatsapp_number == whatsapp_number).one_or_none()


def get_by_id(db: Session, profile_id: uuid.UUID) -> Profile | None:
    return db.query(Profile).filter(Profile.id == profile_id).one_or_none()


def create_profile(db: Session, whatsapp_number: str, display_name: str | None) -> Profile:
    profile = Profile(whatsapp_number=whatsapp_number, display_name=display_name, tags=[])
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_or_create(db: Session, whatsapp_number: str, display_name: str | None) -> Profile:
    profile = get_by_whatsapp_number(db, whatsapp_number)
    if profile:
        if display_name and profile.display_name != display_name:
            profile.display_name = display_name
            db.commit()
            db.refresh(profile)
        return profile
    return create_profile(db, whatsapp_number, display_name)


def get_all_paginated(
    db: Session,
    page: int = 1,
    per_page: int = 20,
    tag: str | None = None,
) -> tuple[list[Profile], int]:
    """
    Retorna profiles paginados com filtro opcional por tag.
    
    Args:
        db: Sessão do banco
        page: Número da página (1-indexed)
        per_page: Itens por página
        tag: Filtrar por tag específica
    
    Returns:
        Tupla com (lista de profiles, total de registros)
    """
    query = db.query(Profile)
    
    if tag:
        # Busca profiles que contêm a tag (JSONB contains)
        normalized_tag = tag.lower().strip().replace(" ", "_")
        query = query.filter(Profile.tags.contains([normalized_tag]))
    
    total = query.count()
    profiles = (
        query
        .order_by(Profile.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    return profiles, total


def _normalize_tag(tag: str) -> str:
    """Normaliza tag: lowercase, sem espaços (usa underscore)."""
    return tag.lower().strip().replace(" ", "_")


def add_tag(db: Session, profile_id: uuid.UUID, tag: str) -> Profile | None:
    """
    Adiciona uma tag ao profile.
    
    - Normaliza a tag (lowercase, underscore)
    - Deduplica usando set
    - Respeita limite máximo de 3 tags
    
    Returns:
        Profile atualizado ou None se não encontrado
    """
    profile = get_by_id(db, profile_id)
    if not profile:
        return None
    
    normalized_tag = _normalize_tag(tag)
    
    # Usa set para deduplicar
    current_tags = set(profile.tags or [])
    
    # Verifica se já atingiu o limite
    if len(current_tags) >= MAX_PROFILE_TAGS and normalized_tag not in current_tags:
        # Já tem 3 tags e a nova não é duplicata - não adiciona
        return profile
    
    current_tags.add(normalized_tag)
    profile.tags = list(current_tags)
    
    db.commit()
    db.refresh(profile)
    return profile


def add_tags(db: Session, profile_id: uuid.UUID, tags: list[str]) -> Profile | None:
    """Adiciona múltiplas tags ao profile respeitando limite de 3."""
    profile = get_by_id(db, profile_id)
    if not profile:
        return None
    
    current_tags = set(profile.tags or [])
    
    for tag in tags:
        normalized_tag = _normalize_tag(tag)
        if len(current_tags) < MAX_PROFILE_TAGS:
            current_tags.add(normalized_tag)
    
    profile.tags = list(current_tags)
    db.commit()
    db.refresh(profile)
    return profile


def remove_tag(db: Session, profile_id: uuid.UUID, tag: str) -> Profile | None:
    """Remove uma tag do profile."""
    profile = get_by_id(db, profile_id)
    if not profile:
        return None
    
    normalized_tag = _normalize_tag(tag)
    current_tags = set(profile.tags or [])
    current_tags.discard(normalized_tag)
    profile.tags = list(current_tags)
    
    db.commit()
    db.refresh(profile)
    return profile
