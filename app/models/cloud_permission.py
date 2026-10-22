from typing import Optional, List
from sqlalchemy import String, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampedBase

class CloudPermission(TimestampedBase):
    __tablename__ = "cloud_permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    resource: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    roles: Mapped[List["CloudRole"]] = relationship(
        "CloudRole",
        secondary="cloud_role_permissions",
        back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_cloud_permissions_resource_action"),
    )
