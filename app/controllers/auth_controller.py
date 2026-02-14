from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dao import user_dao
from app.middlewares.auth_middleware import get_current_user
from app.entities.user_entity import User
from app.schemas.auth_schemas import LoginRequest, TokenResponse, UserResponse
from app.utils.auth import create_access_token, verify_password
from app.utils.db import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Endpoint de login que recebe credenciais e retorna um token JWT.
    
    - **username**: Nome de usuário
    - **password**: Senha do usuário
    
    Retorna um token JWT que deve ser usado no header Authorization: Bearer <token>
    """
    # Get user by username
    user = user_dao.get_by_username(db, request.username)
    
    # Verify user exists and password is correct
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return TokenResponse(access_token=access_token, token_type="bearer")

@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retorna informações do usuário autenticado.
    Requer autenticação via token JWT.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
