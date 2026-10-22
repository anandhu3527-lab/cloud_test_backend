from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_cloud_user
from app.models.cloud_user import CloudUser
from app.schemas.auth import LoginRequest, Token, RefreshRequest
from app.schemas.user import CloudUserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    auth_service = AuthService(db)
    user = await auth_service.authenticate_user(login_data.email, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    access_token, refresh_token, expires_in = await auth_service.create_tokens_for_user(
        user, ip_address, user_agent
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )

@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    refresh_data: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    tokens = await auth_service.refresh_tokens(refresh_data.refresh_token, ip_address, user_agent)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token, refresh_token, expires_in = tokens
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )

@router.post("/logout")
async def logout(
    refresh_data: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[CloudUser, Depends(get_current_cloud_user)]
):
    auth_service = AuthService(db)
    await auth_service.logout(refresh_data.refresh_token)
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=CloudUserResponse)
async def get_me(current_user: Annotated[CloudUser, Depends(get_current_cloud_user)]):
    return current_user
