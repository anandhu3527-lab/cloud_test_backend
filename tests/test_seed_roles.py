import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from seed_roles import seed_base_roles
from app.models.cloud_role import CloudRole

@pytest.mark.asyncio
async def test_seed_roles_creates_employee_and_is_idempotent(db_session: AsyncSession):
    # Initial state
    stmt = select(CloudRole)
    roles = (await db_session.execute(stmt)).scalars().all()
    initial_count = len(roles)
    
    # Run first time
    await seed_base_roles(db_session)
    roles = (await db_session.execute(stmt)).scalars().all()
    assert len(roles) == initial_count + 1
    
    role_names = [r.name for r in roles]
    assert "EMPLOYEE" in role_names
    
    # Run second time (idempotency check)
    await seed_base_roles(db_session)
    roles2 = (await db_session.execute(stmt)).scalars().all()
    assert len(roles2) == len(roles)  # Count should not increase
    
@pytest.mark.asyncio
async def test_seed_roles_preserves_superuser_and_omits_unapproved(db_session: AsyncSession):
    # Ensure SUPERUSER exists before seeding
    superuser_role = CloudRole(name="SUPERUSER", description="Superuser access")
    db_session.add(superuser_role)
    await db_session.commit()
    
    await seed_base_roles(db_session)
    
    stmt = select(CloudRole)
    roles = (await db_session.execute(stmt)).scalars().all()
    role_names = [r.name for r in roles]
    
    # Verify exact allowed roles
    assert "SUPERUSER" in role_names
    assert "EMPLOYEE" in role_names
    
    # Verify unapproved roles are NOT seeded
    assert "SUPPORT" not in role_names
    assert "MANAGER" not in role_names
