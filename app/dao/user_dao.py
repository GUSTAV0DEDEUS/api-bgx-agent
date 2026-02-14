from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.entities.user_entity import User

def get_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).one_or_none()

def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).one_or_none()

def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).one_or_none()

def create_user(db: Session, username: str, email: str, hashed_password: str) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
