from __future__ import annotations

from sqlalchemy.orm import Session

from app.entities.profile_entity import Profile


def get_by_whatsapp_number(db: Session, whatsapp_number: str) -> Profile | None:
    return db.query(Profile).filter(Profile.whatsapp_number == whatsapp_number).one_or_none()


def create_profile(db: Session, whatsapp_number: str, display_name: str | None) -> Profile:
    profile = Profile(whatsapp_number=whatsapp_number, display_name=display_name)
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
