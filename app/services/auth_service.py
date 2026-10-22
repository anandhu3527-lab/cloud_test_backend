import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import verify_password, create_access_token, generate_secure_token
from app.models.cloud_user import CloudUser
from app.models.cloud_session import CloudSession
from app.repositories.cloud_user_repository import CloudUserRepository

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = CloudUserRepository(db)

    async def authenticate_user(self, email: str, password: str) -> Optional[CloudUser]:
        user = await self.user_repo.get_by_email(email)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
            
        # Update last_login_at
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def create_tokens_for_user(self, user: CloudUser, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> Tuple[str, str, int]:
        """Creates access and refresh tokens."""
        access_token = create_access_token(subject=str(user.id))
        
        refresh_token = generate_secure_token(64)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        session = CloudSession(
            user_id=user.id,
            refresh_token=refresh_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(session)
        await self.db.commit()
        
        return access_token, refresh_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    async def refresh_tokens(self, refresh_token: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> Optional[Tuple[str, str, int]]:
        stmt = select(CloudSession).options(selectinload(CloudSession.user)).where(CloudSession.refresh_token == refresh_token)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session or session.is_revoked or session.expires_at < datetime.now(timezone.utc):
            return None
            
        user = session.user
        if not user or not user.is_active:
            return None
            
        # Revoke old session
        session.is_revoked = True
        
        # Create new tokens
        access_token = create_access_token(subject=str(user.id))
        new_refresh_token = generate_secure_token(64)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        new_session = CloudSession(
            user_id=user.id,
            refresh_token=new_refresh_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(new_session)
        await self.db.commit()
        
        return access_token, new_refresh_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    async def logout(self, refresh_token: str) -> bool:
        stmt = select(CloudSession).where(CloudSession.refresh_token == refresh_token)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            session.is_revoked = True
            await self.db.commit()
            return True
        return False
