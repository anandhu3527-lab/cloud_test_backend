import asyncio
import getpass
import sys
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.cloud_user import CloudUser
from app.models.cloud_role import CloudRole


async def bootstrap(target_email: str | None = None):
    print("Bootstrapping / Promoting SUPERUSER...")
    if target_email:
        email = target_email.strip()
    else:
        email = input("Enter superuser email: ").strip()

    if not email:
        print("Email cannot be empty.")
        return

    async with AsyncSessionLocal() as db:
        # 1. Ensure SUPERUSER role exists and is active
        stmt = select(CloudRole).where(CloudRole.name == "SUPERUSER")
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()

        if not role:
            print("Creating SUPERUSER role...")
            role = CloudRole(name="SUPERUSER", description="Full system access", is_active=True)
            db.add(role)
            await db.commit()
            await db.refresh(role)
        elif not role.is_active:
            role.is_active = True
            await db.commit()
            await db.refresh(role)

        # 2. Check if user already exists
        stmt = select(CloudUser).options(selectinload(CloudUser.roles)).where(CloudUser.email == email.lower())
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Check if user already has SUPERUSER role
            if any(r.name == "SUPERUSER" for r in user.roles):
                print(f"User {user.email} already has the SUPERUSER role.")
                return

            # Promote existing user
            user.roles.append(role)
            user.is_active = True
            await db.commit()
            print(f"User {user.email} promoted to SUPERUSER successfully!")
            return

        # 3. Create new user if not found
        password = getpass.getpass("Enter superuser password: ")
        first_name = input("Enter first name: ")
        last_name = input("Enter last name: ")

        print("Creating new superuser...")
        superuser = CloudUser(
            email=email.lower(),
            password_hash=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_email_verified=True,
        )
        superuser.roles.append(role)
        db.add(superuser)
        await db.commit()

        print(f"SUPERUSER {email.lower()} bootstrapped successfully!")


if __name__ == "__main__":
    email_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(bootstrap(email_arg))
