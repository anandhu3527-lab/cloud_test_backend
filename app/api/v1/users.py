from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.dependencies import get_superuser
from app.core.security import get_password_hash
from app.models.cloud_user import CloudUser
from app.models.cloud_role import CloudRole
from app.schemas.user import CloudUserCreate, EmployeeCreateResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=EmployeeCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_cloud_employee(
    user_data: CloudUserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_superuser: Annotated[CloudUser, Depends(get_superuser)]
):
    # Find the role
    stmt = select(CloudRole).where(CloudRole.name == user_data.role_name)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=422, detail="Invalid role specified")
        
    if user_data.role_name == "SUPERUSER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Cannot assign SUPERUSER role through this endpoint"
        )
    
    new_user = CloudUser(
        email=user_data.email.lower(),
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        is_active=True,
        is_email_verified=True
    )
    
    new_user.roles.append(role)
    db.add(new_user)
    
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists"
        )

    return EmployeeCreateResponse()
