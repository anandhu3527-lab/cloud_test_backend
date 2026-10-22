import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.cloud_user import CloudUser
from app.models.cloud_role import CloudRole
from app.models.user_role import CloudUserRole

class CloudUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[CloudUser]:
        stmt = select(CloudUser).options(
            selectinload(CloudUser.roles).selectinload(CloudRole.permissions)
        ).where(CloudUser.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[CloudUser]:
        stmt = select(CloudUser).options(
            selectinload(CloudUser.roles).selectinload(CloudRole.permissions)
        ).where(CloudUser.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
