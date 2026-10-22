import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.models.cloud_user import CloudUser
from app.models.cloud_role import CloudRole

@pytest.fixture
async def active_user(db_session: AsyncSession):
    user = CloudUser(
        email="active@example.com",
        password_hash=get_password_hash("password123"),
        first_name="Active",
        last_name="User",
        is_active=True,
        is_email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    return user

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
async def normal_role(db_session: AsyncSession):
    role = CloudRole(name="EMPLOYEE", description="Normal employee role")
    db_session.add(role)
    await db_session.commit()
    return role

@pytest.mark.asyncio
async def test_superuser_can_create_employee(client: AsyncClient, superuser: CloudUser, normal_role: CloudRole):
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "adminpassword"
    })
    token = login_res.json()["access_token"]
    
    res = await client.post("/api/v1/users", headers={"Authorization": f"Bearer {token}"}, json={
        "email": "newemployee@example.com",
        "password": "strongpassword123",
        "first_name": "New",
        "last_name": "Employee",
        "role_name": "EMPLOYEE"
    })
    assert res.status_code == 201
    data = res.json()

    # Exact minimal success response
    assert data["success"] is True
    assert data["message"] == "Employee created successfully"

    # Sensitive and internal fields must be absent
    for forbidden_field in (
        "id", "email", "first_name", "last_name", "phone",
        "password", "password_hash",
        "is_active", "is_email_verified",
        "last_login_at", "created_at", "updated_at",
        "roles",
    ):
        assert forbidden_field not in data, f"Field '{forbidden_field}' must not be in the response"

@pytest.mark.asyncio
async def test_normal_employee_cannot_create_employee(client: AsyncClient, active_user: CloudUser, normal_role: CloudRole):
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "active@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    
    res = await client.post("/api/v1/users", headers={"Authorization": f"Bearer {token}"}, json={
        "email": "another@example.com",
        "password": "strongpassword123",
        "first_name": "Another",
        "last_name": "Employee",
        "role_name": "EMPLOYEE"
    })
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_employee(client: AsyncClient, normal_role: CloudRole):
    res = await client.post("/api/v1/users", json={
        "email": "another@example.com",
        "password": "strongpassword123",
        "first_name": "Another",
        "last_name": "Employee",
        "role_name": "EMPLOYEE"
    })
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_duplicate_employee_email_rejected(client: AsyncClient, superuser: CloudUser, normal_role: CloudRole):
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "adminpassword"
    })
    token = login_res.json()["access_token"]
    
    await client.post("/api/v1/users", headers={"Authorization": f"Bearer {token}"}, json={
        "email": "dup@example.com",
        "password": "strongpassword123",
        "first_name": "New",
        "last_name": "Employee",
        "role_name": "EMPLOYEE"
    })
    
    res2 = await client.post("/api/v1/users", headers={"Authorization": f"Bearer {token}"}, json={
        "email": "dup@example.com",
        "password": "strongpassword123",
        "first_name": "New",
        "last_name": "Employee",
        "role_name": "EMPLOYEE"
    })
    assert res2.status_code == 409

@pytest.mark.asyncio
async def test_cannot_self_assign_superuser(client: AsyncClient, superuser: CloudUser):
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "adminpassword"
    })
    token = login_res.json()["access_token"]
    
    res = await client.post("/api/v1/users", headers={"Authorization": f"Bearer {token}"}, json={
        "email": "hacker@example.com",
        "password": "strongpassword123",
        "first_name": "Hacker",
        "last_name": "Man",
        "role_name": "SUPERUSER"
    })
    assert res.status_code == 403
