from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated

from .schemas import RegisterRequest
from .util import get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, create_access_token
from backend.database import get_db
from .models import User

router = APIRouter()

@router.post("/register")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=request.email,
        hashed_password=get_password_hash(request.password)
    )

    db.add(new_user)
    await db.commit()

    return {"message": "User created successfully"}


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.email == form_data.username)
    )
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        data={"sub": str(user.id)},  # ⚠️ store USER ID now
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
