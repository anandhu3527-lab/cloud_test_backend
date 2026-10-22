"""Add cloud_role_permissions table

Revision ID: a1b2c3d4e5f6
Revises: 3530fb4067fb
Create Date: 2026-10-10 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3530fb4067fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('cloud_role_permissions',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('permission_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['cloud_permissions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['role_id'], ['cloud_roles.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('role_id', 'permission_id'),
    sa.UniqueConstraint('role_id', 'permission_id', name='uq_cloud_role_permissions_role_permission')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cloud_role_permissions')
