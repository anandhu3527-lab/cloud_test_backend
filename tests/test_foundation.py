import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings, get_settings
from app.core.exceptions import AppException
from app.core.constants import HEADER_REQUEST_ID, ERR_RATE_LIMIT
from app.core.database import get_db
from pydantic import BaseModel
from fastapi import Request
import os
import uuid

# Mock DB Dependency
async def override_get_db():
    class MockSession:
        async def execute(self, *args, **kwargs):
            return True
        async def close(self):
            pass
    yield MockSession()

async def override_get_db_fail():
    class MockSession:
        async def execute(self, *args, **kwargs):
            raise Exception("Mock DB Failure")
        async def close(self):
            pass
    yield MockSession()

# Dummy endpoints for testing exceptions and validation
class DummyModel(BaseModel):
    name: str

@app.get("/dummy-app-exception")
async def dummy_app_exception():
    raise AppException(code="TEST_ERROR", message="Test message", status_code=400)

@app.post("/dummy-validation")
async def dummy_validation(data: DummyModel):
    return data

@app.get("/dummy-unexpected-error")
async def dummy_unexpected_error():
    raise ValueError("Real python error that should be hidden")

@pytest.fixture
async def client():
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_health_returns_successfully(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"
    assert data["data"]["database"] == "healthy"

@pytest.mark.asyncio
async def test_api_v1_health_works(client: AsyncClient):
    response = await client.get(f"{settings.API_V1_PREFIX}/health")
    assert response.status_code == 200
    assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_request_receives_request_id(client: AsyncClient):
    response = await client.get("/health")
    assert HEADER_REQUEST_ID in response.headers
    assert response.json()["request_id"] == response.headers[HEADER_REQUEST_ID]

@pytest.mark.asyncio
async def test_valid_request_id_is_reused(client: AsyncClient):
    test_id = "req_1234567890abcdef"
    response = await client.get("/health", headers={HEADER_REQUEST_ID: test_id})
    assert response.headers[HEADER_REQUEST_ID] == test_id
    assert response.json()["request_id"] == test_id

@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced(client: AsyncClient):
    test_id = "invalid-!@#$"
    response = await client.get("/health", headers={HEADER_REQUEST_ID: test_id})
    assert response.headers[HEADER_REQUEST_ID] != test_id
    assert response.json()["request_id"] != test_id

@pytest.mark.asyncio
async def test_known_exception_returns_controlled_response(client: AsyncClient):
    response = await client.get("/dummy-app-exception")
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "TEST_ERROR"
    assert data["error"]["message"] == "Test message"
    assert "request_id" in data

@pytest.mark.asyncio
async def test_validation_errors_return_controlled_response(client: AsyncClient):
    response = await client.post("/dummy-validation", json={"wrong_field": "value"})
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Invalid request parameters"

@pytest.mark.asyncio
async def test_unexpected_error_does_not_expose_internals(client: AsyncClient):
    response = await client.get("/dummy-unexpected-error")
    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An unexpected error occurred."
    assert "Real python error that should be hidden" not in response.text

@pytest.mark.asyncio
async def test_security_headers(client: AsyncClient):
    response = await client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

@pytest.mark.asyncio
async def test_database_failure_is_handled_safely(client: AsyncClient):
    app.dependency_overrides[get_db] = override_get_db_fail
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["success"] is False
    assert data["data"]["status"] == "unhealthy"
    assert data["data"]["database"] == "unavailable"
    app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_rate_limit(client: AsyncClient):
    # original limit is 10/minute
    for _ in range(10):
        await client.get("/health")
    
    # 11th request should fail with 429
    res2 = await client.get("/health")
    assert res2.status_code == 429
    data = res2.json()
    assert data["success"] is False
    assert data["error"]["code"] == ERR_RATE_LIMIT

@pytest.mark.asyncio
async def test_cors_headers(client: AsyncClient):
    # Origin from config
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    }
    response = await client.options("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

def test_production_config():
    os.environ["APP_ENV"] = "production"
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
    
    with pytest.raises(ValueError, match="DEBUG must be False in production"):
        get_settings()
        
    os.environ["DEBUG"] = "false"
    os.environ["CORS_ORIGINS"] = '["*"]'
    with pytest.raises(ValueError, match="CORS_ORIGINS must be explicitly defined without wildcards in production"):
        get_settings()
        
    os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'
    os.environ["TRUSTED_HOSTS"] = '["*"]'
    with pytest.raises(ValueError, match="TRUSTED_HOSTS must be explicitly defined without wildcards in production"):
        get_settings()
        
    os.environ.pop("APP_ENV")
    os.environ.pop("DEBUG")
    os.environ.pop("DATABASE_URL")
    os.environ.pop("CORS_ORIGINS")
    os.environ.pop("TRUSTED_HOSTS")
