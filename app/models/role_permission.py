import uuid
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class CloudRolePermission(Base):
    __tablename__ = "cloud_role_permissions"

    # We use RESTRICT (the default) behavior here.
    # Roles and permissions are security-sensitive identity data.
    # They should be deactivated or explicitly unlinked before deletion
    # to ensure audit trails remain intact.
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_roles.id", ondelete="RESTRICT"), 
        primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_permissions.id", ondelete="RESTRICT"), 
        primary_key=True
    )

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_cloud_role_permissions_role_permission"),
    )
