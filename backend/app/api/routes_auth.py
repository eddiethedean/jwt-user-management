from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.api.deps import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    user = db.exec(select(User).where(User.email == form_data.username)).first()
    if (
        not user
        or not user.is_active
        or not verify_password(form_data.password, user.hashed_password)
    ):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "is_admin": user.is_admin},
    )
    return {"access_token": token, "token_type": "bearer"}
