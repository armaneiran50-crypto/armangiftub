from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import LoginOut, PasswordChangeIn, UserIn
from ..security import admin_only, create_token, current_user, hash_password, verify_password
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return LoginOut(access_token=create_token(user), role=user.role)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    audit.log(db, admin.email, "user.create", "user", user.id, {"role": body.role})
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/password")
def change_password(body: PasswordChangeIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    audit.log(db, user.email, "user.password_change", "user", user.id, {})
    db.commit()
    return {"ok": True}
