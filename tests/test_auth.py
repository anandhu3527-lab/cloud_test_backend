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
async def inactive_user(db_session: AsyncSession):
    user = CloudUser(
        email="inactive@example.com",
        password_hash=get_password_hash("password123"),
        first_name="Inactive",
        last_name="User",
        is_active=False,
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

@pytest.mark.asyncio
async def test_successful_login(client: AsyncClient, active_user: CloudUser):
    response = await client.post("/api/v1/auth/login", json={
        "email": "active@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

@pytest.mark.asyncio
async def test_wrong_password(client: AsyncClient, active_user: CloudUser):
    response = await client.post("/api/v1/auth/login", json={
        "email": "active@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

@pytest.mark.asyncio
async def test_unknown_email(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "email": "unknown@example.com",
        "password": "password123"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_inactive_user(client: AsyncClient, inactive_user: CloudUser):
    response = await client.post("/api/v1/auth/login", json={
        "email": "inactive@example.com",
        "password": "password123"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me_with_valid_token(client: AsyncClient, active_user: CloudUser):
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "active@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "active@example.com"
    assert "password_hash" not in me_res.json()

@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_get_me_with_invalid_token(client: AsyncClient):
    res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_logout_and_refresh(client: AsyncClient, active_user: CloudUser):
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "active@example.com",
        "password": "password123"
    })
    refresh_token = login_res.json()["refresh_token"]
    
    # Refresh should work
    refresh_res = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert refresh_res.status_code == 200
    new_refresh = refresh_res.json()["refresh_token"]
    
    # Logout
    login_token = refresh_res.json()["access_token"]
    logout_res = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {login_token}"}, json={
        "refresh_token": new_refresh
    })
    assert logout_res.status_code == 200
    
    # Refresh should fail now
    failed_refresh = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": new_refresh
    })
    assert failed_refresh.status_code == 401

@pytest.mark.asyncio
async def test_openapi_schema_auth_is_bearer(client: AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    openapi_schema = response.json()
    
    # Verify that HTTPBearer is used instead of OAuth2PasswordBearer
    security_schemes = openapi_schema.get("components", {}).get("securitySchemes", {})
    
    # Find a scheme that has type="http" and scheme="bearer"
    bearer_scheme_found = False
    for scheme_name, scheme_details in security_schemes.items():
        if scheme_details.get("type") == "http" and scheme_details.get("scheme") == "bearer":
            bearer_scheme_found = True
        
        # Verify no OAuth2 password flow schemes exist
        assert scheme_details.get("type") != "oauth2", f"Found obsolete OAuth2 scheme: {scheme_name}"
            
    assert bearer_scheme_found, "HTTPBearer security scheme should be present in OpenAPI schema"
    assert "OAuth2PasswordBearer" not in security_schemes, "OAuth2PasswordBearer should be completely removed"

from datetime import timedelta
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_expired_token(client: AsyncClient, active_user: CloudUser):
    # Create an expired token
    expired_token = create_access_token(
        subject=str(active_user.id),
        expires_delta=timedelta(minutes=-10)
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_wrong_audience_token(client: AsyncClient, active_user: CloudUser):
    # Create a token with wrong audience
    wrong_aud_token = create_access_token(
        subject=str(active_user.id),
        audience="wrong-audience"
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {wrong_aud_token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_shopflow_token_rejected(client: AsyncClient, active_user: CloudUser):
    # Create a ShopFlow token (simulated by audience="shopflow")
    shopflow_token = create_access_token(
        subject=str(active_user.id),
        audience="shopflow"
    )
    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {shopflow_token}"})
    assert res.status_code == 401
