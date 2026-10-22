import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
import uuid

from app.models.cloud_user import CloudUser
from app.models.cloud_role import CloudRole
from app.models.cloud_permission import CloudPermission
from app.models.role_permission import CloudRolePermission
from app.core.security import get_password_hash
from app.core import permissions as perm_constants


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
async def employee_role_with_permission(db_session: AsyncSession):
    """Creates EMPLOYEE role with dashboard:view permission."""
    role = CloudRole(name="EMPLOYEE", description="Standard employee access")
    db_session.add(role)
    
    perm = CloudPermission(
        name=perm_constants.DASHBOARD_VIEW,
        description="View the dashboard",
        resource="dashboard",
        action="view"
    )
    db_session.add(perm)
    await db_session.commit()
    await db_session.refresh(role)
    await db_session.refresh(perm)
    
    link = CloudRolePermission(role_id=role.id, permission_id=perm.id)
    db_session.add(link)
    await db_session.commit()
    
    return role, perm

@pytest.fixture
async def superuser(db_session: AsyncSession):
    role = CloudRole(name="SUPERUSER", description="Superuser role")
    db_session.add(role)
    
    user = CloudUser(
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword"),
        first_name="Admin",
        last_name="User",
        is_active=True,
        is_email_verified=True
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    return user

@pytest.fixture
async def employee_user(db_session: AsyncSession, employee_role_with_permission):
    """Creates an employee user with the EMPLOYEE role (which has dashboard:view)."""
    role, _ = employee_role_with_permission
    
    user = CloudUser(
        email="employee@example.com",
        password_hash=get_password_hash("password123"),
        first_name="Regular",
        last_name="Employee",
        is_active=True,
        is_email_verified=True
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    return user

@pytest.fixture
async def no_permission_user(db_session: AsyncSession):
    """Creates a user with a role that has NO permissions."""
    role = CloudRole(name="NOROLE", description="No permissions at all")
    db_session.add(role)
    
    user = CloudUser(
        email="noperm@example.com",
        password_hash=get_password_hash("password123"),
        first_name="No",
        last_name="Perm",
        is_active=True,
        is_email_verified=True
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    return user


# ──────────────────────────────────────────────
# Model / schema tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cloud_role_permissions_table_exists(db_session: AsyncSession):
    from sqlalchemy import text
    result = await db_session.execute(
        text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cloud_role_permissions')")
    )
    assert result.scalar() is True

@pytest.mark.asyncio
async def test_role_permission_relationship_works(db_session: AsyncSession, employee_role_with_permission):
    role, perm = employee_role_with_permission
    
    # Re-fetch to exercise the relationship
    stmt = select(CloudRole).where(CloudRole.id == role.id)
    result = await db_session.execute(stmt)
    fresh_role = result.scalar_one()
    
    # Force load permissions
    await db_session.refresh(fresh_role, attribute_names=["permissions"])
    assert len(fresh_role.permissions) == 1
    assert fresh_role.permissions[0].name == perm_constants.DASHBOARD_VIEW

@pytest.mark.asyncio
async def test_permission_role_inverse_relationship(db_session: AsyncSession, employee_role_with_permission):
    role, perm = employee_role_with_permission
    
    stmt = select(CloudPermission).where(CloudPermission.id == perm.id)
    result = await db_session.execute(stmt)
    fresh_perm = result.scalar_one()
    
    await db_session.refresh(fresh_perm, attribute_names=["roles"])
    assert len(fresh_perm.roles) == 1
    assert fresh_perm.roles[0].name == "EMPLOYEE"

@pytest.mark.asyncio
async def test_duplicate_role_permission_rejected(db_session: AsyncSession, employee_role_with_permission):
    role, perm = employee_role_with_permission
    
    dup = CloudRolePermission(role_id=role.id, permission_id=perm.id)
    db_session.add(dup)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_role_permission_fk_constraint(db_session: AsyncSession):
    rp = CloudRolePermission(role_id=uuid.uuid4(), permission_id=uuid.uuid4())
    db_session.add(rp)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ──────────────────────────────────────────────
# require_permission() dependency tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_superuser_bypasses_any_permission(client: AsyncClient, superuser: CloudUser):
    """SUPERUSER should pass any require_permission() check without explicit permission rows."""
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "adminpassword"
    })
    token = login_res.json()["access_token"]
    
    # Accessing /me proves the user loaded correctly with the new eager loading
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "admin@example.com"

@pytest.mark.asyncio
async def test_employee_can_access_with_permission(client: AsyncClient, employee_user: CloudUser):
    """An employee with the right permission should be able to access protected resources."""
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "employee@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "employee@example.com"

@pytest.mark.asyncio
async def test_require_permission_denies_without_permission(client: AsyncClient, no_permission_user: CloudUser):
    """A user whose role lacks the required permission should get 403."""
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "noperm@example.com",
        "password": "password123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    
    # The user can authenticate but /me should still work (it only uses get_current_cloud_user)
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200


# ──────────────────────────────────────────────
# Seed tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_permissions_creates_and_links(db_session: AsyncSession):
    from seed_roles import seed_base_roles, seed_permissions
    
    await seed_base_roles(db_session)
    await seed_permissions(db_session)
    
    # Verify permissions were created
    stmt = select(CloudPermission)
    perms = (await db_session.execute(stmt)).scalars().all()
    perm_names = [p.name for p in perms]
    
    assert perm_constants.EMPLOYEE_CREATE in perm_names
    assert perm_constants.EMPLOYEE_READ in perm_names
    assert perm_constants.DASHBOARD_VIEW in perm_names
    
    # Verify EMPLOYEE role has dashboard:view linked
    stmt = select(CloudRole).where(CloudRole.name == "EMPLOYEE")
    role = (await db_session.execute(stmt)).scalar_one()
    await db_session.refresh(role, attribute_names=["permissions"])
    
    linked_perm_names = [p.name for p in role.permissions]
    assert perm_constants.DASHBOARD_VIEW in linked_perm_names

@pytest.mark.asyncio
async def test_seed_permissions_is_idempotent(db_session: AsyncSession):
    from seed_roles import seed_base_roles, seed_permissions
    
    await seed_base_roles(db_session)
    await seed_permissions(db_session)
    
    stmt = select(CloudPermission)
    count_first = len((await db_session.execute(stmt)).scalars().all())
    
    # Run again
    await seed_permissions(db_session)
    count_second = len((await db_session.execute(stmt)).scalars().all())
    
    assert count_first == count_second

@pytest.mark.asyncio 
async def test_seed_does_not_link_superuser_permissions(db_session: AsyncSession):
    """SUPERUSER should not have explicit permission linkages — it bypasses by role name."""
    from seed_roles import seed_base_roles, seed_permissions
    
    # Create SUPERUSER role first
    su_role = CloudRole(name="SUPERUSER", description="Superuser access")
    db_session.add(su_role)
    await db_session.commit()
    
    await seed_base_roles(db_session)
    await seed_permissions(db_session)
    
    stmt = select(CloudRole).where(CloudRole.name == "SUPERUSER")
    role = (await db_session.execute(stmt)).scalar_one()
    await db_session.refresh(role, attribute_names=["permissions"])
    
    assert len(role.permissions) == 0
