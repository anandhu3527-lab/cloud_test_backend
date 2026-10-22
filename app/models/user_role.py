import uuid
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class CloudUserRole(Base):
    __tablename__ = "cloud_user_roles"

    # We use RESTRICT (the default) behavior here.
    # Security-sensitive identity data like users and roles shouldn't be
    # deleted casually. Instead, they should be deactivated or explicitly
    # unlinked before deletion to ensure audit trails remain intact.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_users.id", ondelete="RESTRICT"), 
        primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cloud_roles.id", ondelete="RESTRICT"), 
        primary_key=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_cloud_user_roles_user_role"),
    )
