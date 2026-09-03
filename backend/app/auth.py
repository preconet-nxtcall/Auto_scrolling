import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

logger = logging.getLogger("uvicorn.error")

def get_or_create_default_user(db: Session) -> User:
    """Ensures at least one default user exists in the database for single-tenant / local mode."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(
            id=1,
            email="admin@autoscroll.io",
            full_name="Default User",
            role="ADMIN",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Authentication & Authorization Dependency.
    1. Checks for 'X-User-Id' header or 'Authorization' Bearer header.
    2. Validates user existence and active status in DB.
    3. Falls back seamlessly to default active user (ID=1) if unauthenticated.
    """
    user_id_header = request.headers.get("X-User-Id")
    auth_header = request.headers.get("Authorization")

    target_user_id: Optional[int] = None

    if user_id_header:
        try:
            target_user_id = int(user_id_header)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-User-Id header format. Must be an integer."
            )
    elif auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1].strip()
        # If token is numeric ID or dummy token
        if token.isdigit():
            target_user_id = int(token)

    if target_user_id is not None:
        user = db.query(User).filter(User.id == target_user_id).first()
        if not user:
            if target_user_id == 1:
                user = get_or_create_default_user(db)
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or account is deactivated."
                )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated."
            )
        return user

    # Default fallback user for single-tenant / dev environment
    return get_or_create_default_user(db)



