import uuid
from typing import Annotated, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.cloud_user import CloudUser
from app.repositories.cloud_user_repository import CloudUserRepository

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_cloud_user(
    token_cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> CloudUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token_cred:
        raise credentials_exception
        
    token = token_cred.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
        
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user_repo = CloudUserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        
    return user

def is_superuser(user: CloudUser) -> bool:
    """Check if the user holds an active SUPERUSER role."""
    if not user or not user.is_active:
        return False
    return any(
        (role.name.strip().upper() == "SUPERUSER" and role.is_active)
        for role in user.roles
    )


async def get_superuser(
    current_user: Annotated[CloudUser, Depends(get_current_cloud_user)]
) -> CloudUser:
    """Dependency that checks if the current user has the SUPERUSER role."""
    if not is_superuser(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_permission(permission_name: str) -> Callable:
    """Dependency factory that checks if the current user has a specific permission.
    
    SUPERUSER role automatically grants all permissions without needing
    explicit permission rows in the database.
    
    Usage in an endpoint:
        current_user: Annotated[CloudUser, Depends(require_permission("employee:create"))]
    """
    async def _check_permission(
        current_user: Annotated[CloudUser, Depends(get_current_cloud_user)]
    ) -> CloudUser:
        # SUPERUSER bypasses all permission checks
        if is_superuser(current_user):
            return current_user
        
        # Check if any of the user's roles carry the required permission
        for role in current_user.roles:
            if not role.is_active:
                continue
            for perm in role.permissions:
                if perm.name == permission_name and perm.is_active:
                    return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return _check_permission


def require_any_permission(*permission_names: str) -> Callable:
    """Dependency factory that checks if the current user has at least one of the given permissions.
    
    SUPERUSER role automatically grants all permissions.
    """
    async def _check_any_permission(
        current_user: Annotated[CloudUser, Depends(get_current_cloud_user)]
    ) -> CloudUser:
        if is_superuser(current_user):
            return current_user
        
        for role in current_user.roles:
            if not role.is_active:
                continue
            for perm in role.permissions:
                if perm.name in permission_names and perm.is_active:
                    return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return _check_any_permission


