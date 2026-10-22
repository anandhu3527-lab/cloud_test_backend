import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.models.cloud_user import CloudUser
from app.models.cloud_role import CloudRole
from app.models.cloud_permission import CloudPermission
from app.models.user_role import CloudUserRole
from datetime import datetime, timezone
import uuid

@pytest.mark.asyncio
async def test_database_connection(db_session):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1

@pytest.mark.asyncio
async def test_tables_exist(db_session):
    tables = ['cloud_users', 'cloud_roles', 'cloud_permissions', 'cloud_user_roles', 'cloud_role_permissions']
    for table in tables:
        result = await db_session.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')"))
        assert result.scalar() is True

@pytest.mark.asyncio
async def test_uuid_primary_keys_and_timestamps(db_session):
    user = CloudUser(
        email="test_uuid@example.com",
        password_hash="hash",
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    assert isinstance(user.id, uuid.UUID)
    assert user.created_at is not None
    assert user.created_at.tzinfo is not None  # Timezone aware
    assert user.updated_at is not None
    assert user.updated_at.tzinfo is not None

@pytest.mark.asyncio
async def test_duplicate_user_email_rejected(db_session):
    user1 = CloudUser(email="dup@example.com", password_hash="h", first_name="A", last_name="B")
    db_session.add(user1)
    await db_session.commit()
    
    user2 = CloudUser(email="dup@example.com", password_hash="h2", first_name="C", last_name="D")
    db_session.add(user2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_duplicate_role_name_rejected(db_session):
    role1 = CloudRole(name="ADMIN")
    db_session.add(role1)
    await db_session.commit()
    
    role2 = CloudRole(name="ADMIN")
    db_session.add(role2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_duplicate_permission_name_rejected(db_session):
    perm1 = CloudPermission(name="users.read", resource="users", action="read")
    db_session.add(perm1)
    await db_session.commit()
    
    perm2 = CloudPermission(name="users.read", resource="users", action="write")
    db_session.add(perm2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_duplicate_user_role_rejected(db_session):
    user = CloudUser(email="ur@example.com", password_hash="h", first_name="A", last_name="B")
    role = CloudRole(name="TEST_ROLE")
    db_session.add_all([user, role])
    await db_session.commit()
    
    ur1 = CloudUserRole(user_id=user.id, role_id=role.id)
    db_session.add(ur1)
    await db_session.commit()
    
    ur2 = CloudUserRole(user_id=user.id, role_id=role.id)
    db_session.add(ur2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_foreign_keys_work(db_session):
    ur = CloudUserRole(user_id=uuid.uuid4(), role_id=uuid.uuid4())
    db_session.add(ur)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_nullable_fields_behave_correctly(db_session):
    user = CloudUser(
        email="nullable@example.com",
        password_hash="h",
        first_name="A",
        last_name="B",
        phone=None,
        last_login_at=None
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    assert user.phone is None
    assert user.last_login_at is None
