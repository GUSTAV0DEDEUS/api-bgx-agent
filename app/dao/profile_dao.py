from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.entities.profile_entity import Profile


MAX_PROFILE_TAGS = 3


def extract_first_name_only(full_name: str | None) -> str | None:
    """Extrai apenas o primeiro nome de um nome completo.
    
    Exemplos:
    - "Gustavo de Deus Conceição" -> "Gustavo"
    - "Maria Eduarda Silva" -> "Maria"
    - "João" -> "João"
    """
    if not full_name or not full_name.strip():
        return None
    
    parts = full_name.strip().split()
    return parts[0] if parts else None


def parse_display_name(display_name: str | None) -> tuple[str | None, str | None]:
    """
    Faz parse simples do display_name em first_name e last_name.
    
    Regras:
    - Primeiro token = first_name
    - Resto = last_name
    """
    if not display_name or not display_name.strip():
        return None, None

    parts = display_name.strip().split()

    if not parts:
        return None, None
    
    if len(parts) == 1:
        return parts[0], None

    return parts[0], " ".join(parts[1:])


def get_by_whatsapp_number(db: Session, whatsapp_number: str) -> Profile | None:
    return db.query(Profile).filter(Profile.whatsapp_number == whatsapp_number).one_or_none()


def get_by_id(db: Session, profile_id: uuid.UUID) -> Profile | None:
    return db.query(Profile).filter(Profile.id == profile_id).one_or_none()


def create_profile(db: Session, whatsapp_number: str, display_name: str | None) -> Profile:
    first_name, last_name = parse_display_name(display_name)
    profile = Profile(
        whatsapp_number=whatsapp_number,
        first_name=first_name,
        last_name=last_name,
        tags=[],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_or_create(db: Session, whatsapp_number: str, display_name: str | None) -> Profile:
    profile = get_by_whatsapp_number(db, whatsapp_number)
    if profile:
        if display_name:
            first_name, last_name = parse_display_name(display_name)
            changed = False
            if first_name and profile.first_name != first_name:
                profile.first_name = first_name
                changed = True
            if last_name and profile.last_name != last_name:
                profile.last_name = last_name
                changed = True
            if changed:
                db.commit()
                db.refresh(profile)
        return profile
    return create_profile(db, whatsapp_number, display_name)


def update_name(
    db: Session, profile_id: uuid.UUID, first_name: str | None = None, last_name: str | None = None,
) -> Profile | None:
    """Atualiza first_name e/ou last_name do profile."""
    profile = get_by_id(db, profile_id)
    if not profile:
        return None
    if first_name is not None:
        profile.first_name = first_name
    if last_name is not None:
        profile.last_name = last_name
    db.commit()
    db.refresh(profile)
    return profile


def get_all_paginated(
    db: Session, page: int = 1, per_page: int = 20, tag: str | None = None,
) -> tuple[list[Profile], int]:
    query = db.query(Profile)
    if tag:
        normalized_tag = tag.lower().strip().replace(" ", "_")
        query = query.filter(Profile.tags.contains([normalized_tag]))
    total = query.count()
    profiles = (
        query.order_by(Profile.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page).all()
    )
    return profiles, total


def _normalize_tag(tag: str) -> str:
    return tag.lower().strip().replace(" ", "_")


def add_tag(db: Session, profile_id: uuid.UUID, tag: str) -> Profile | None:
    profile = get_by_id(db, profile_id)
    if not profile:
        return None
    normalized_tag = _normalize_tag(tag)
    current_tags = set(profile.tags or [])
    if len(current_tags) >= MAX_PROFILE_TAGS and normalized_tag not in current_tags:
        return profile
    current_tags.add(normalized_tag)
    profile.tags = list(current_tags)
    db.commit()
    db.refresh(profile)
    return profile


def add_tags(db: Session, profile_id: uuid.UUID, tags: list[str]) -> Profile | None:
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
