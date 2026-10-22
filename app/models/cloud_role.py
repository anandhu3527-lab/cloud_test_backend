from typing import Optional, List
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampedBase

class CloudRole(TimestampedBase):
    __tablename__ = "cloud_roles"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    users: Mapped[List["CloudUser"]] = relationship(
        "CloudUser", 
        secondary="cloud_user_roles", 
        back_populates="roles"
    )
    permissions: Mapped[List["CloudPermission"]] = relationship(
        "CloudPermission",
        secondary="cloud_role_permissions",
        back_populates="roles"
    )
