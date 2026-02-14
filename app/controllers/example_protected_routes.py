"""
Example: How to protect routes with JWT authentication

This file demonstrates how to use the authentication middleware
to protect API endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.entities.user_entity import User
from app.middlewares.auth_middleware import get_current_user
from app.utils.db import get_db

router = APIRouter(prefix="/example", tags=["Protected Examples"])

# Example 1: Simple protected route
@router.get("/protected")
def protected_route(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    This endpoint requires authentication.
    The user must provide a valid JWT token in the Authorization header.
    
    Example:
        Authorization: Bearer <your_jwt_token>
    """
    return {
        "message": "This is a protected route",
        "user": {
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
        }
    }

# Example 2: Protected route with database access
@router.get("/protected-with-db")
def protected_route_with_db(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    This endpoint requires authentication and uses the database.
    Both dependencies (authentication and database) are injected.
    """
    return {
        "message": "Protected route with database",
        "user_id": str(current_user.id),
        "username": current_user.username,
    }

# Example 3: How to add authentication to existing routes
# 
# To protect an existing route, simply add this parameter:
#     current_user: Annotated[User, Depends(get_current_user)]
#
# Before:
# @router.get("/leads")
# def list_leads(
#     db: Session = Depends(get_db),
# ):
#     ...
#
# After:
# @router.get("/leads")
# def list_leads(
#     current_user: Annotated[User, Depends(get_current_user)],
#     db: Session = Depends(get_db),
# ):
#     ...
