from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=128, description="Nome de usuário")
    password: str = Field(..., min_length=6, description="Senha")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
