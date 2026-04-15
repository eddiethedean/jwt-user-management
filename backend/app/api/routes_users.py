from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlmodel import Session, select

from app.api.deps import (
    get_current_user,
    get_db,
    get_optional_admin,
    require_admin_api_key,
)
from app.core.security import hash_password
from app.models.user import User, UserCreate, UserPublic, UserUpdate


router = APIRouter(prefix="/users", tags=["users"])


def _require_admin_or_key(
    current_admin: Optional[User], x_admin_api_key: Optional[str]
) -> None:
    if x_admin_api_key is not None:
        require_admin_api_key(x_admin_api_key)
        return
    if not current_admin:
        raise HTTPException(status_code=403, detail="Admin required")


@router.get("/me", response_model=UserPublic)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("", response_model=List[UserPublic])
def list_users(
    db: Session = Depends(get_db),
    x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key"),
    current_admin: Optional[User] = Depends(get_optional_admin),
) -> list:
    _require_admin_or_key(current_admin, x_admin_api_key)
    # Use SQL text for order-by to keep static typing happy.
    return list(db.exec(select(User).order_by(text("created_at DESC"))).all())


@router.post("", response_model=UserPublic)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key"),
    current_admin: Optional[User] = Depends(get_optional_admin),
) -> User:
    _require_admin_or_key(current_admin, x_admin_api_key)

    existing = db.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    raw_password = payload.password or "ChangeMe123!"
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(raw_password),
        is_admin=payload.is_admin,
        permissions=payload.permissions,
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key"),
    current_admin: Optional[User] = Depends(get_optional_admin),
) -> User:
    _require_admin_or_key(current_admin, x_admin_api_key)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(user, k, v)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key"),
    current_admin: Optional[User] = Depends(get_optional_admin),
) -> dict:
    _require_admin_or_key(current_admin, x_admin_api_key)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.add(user)
    db.commit()
    return {"ok": True}
