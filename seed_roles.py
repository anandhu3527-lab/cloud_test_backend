import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.cloud_role import CloudRole
from app.models.cloud_permission import CloudPermission
from app.models.role_permission import CloudRolePermission
from app.core import permissions as perm_constants

# Permission definitions: (name, description, resource, action)
PERMISSION_DEFINITIONS = [
    (perm_constants.EMPLOYEE_CREATE, "Create new employee accounts", "employee", "create"),
    (perm_constants.EMPLOYEE_READ, "View employee details", "employee", "read"),
    (perm_constants.EMPLOYEE_UPDATE, "Update employee information", "employee", "update"),
    (perm_constants.EMPLOYEE_DEACTIVATE, "Deactivate employee accounts", "employee", "deactivate"),
    (perm_constants.DASHBOARD_VIEW, "View the dashboard", "dashboard", "view"),
    (perm_constants.SHOPFLOW_READ, "View ShopFlow data", "shopflow", "read"),
    (perm_constants.SHOPFLOW_MANAGE, "Manage ShopFlow shops and users", "shopflow", "manage"),
    (perm_constants.SHOPFLOW_SUBSCRIPTION_MANAGE, "Manage ShopFlow subscriptions", "shopflow", "subscription_manage"),
]

# Role-to-permission mappings
# SUPERUSER is NOT listed here — it bypasses permission checks by role name.
ROLE_PERMISSIONS = {
    "EMPLOYEE": [
        perm_constants.DASHBOARD_VIEW,
        perm_constants.SHOPFLOW_READ,
    ],
}


async def seed_base_roles(db: AsyncSession) -> None:
    """Seeds the approved base non-privileged roles (Task 3 scope)."""
    
    # Task 3 only approves the EMPLOYEE role to be seeded.
    # Task 4 will introduce SUPPORT and MANAGER alongside permissions.
    approved_roles = [
        {"name": "EMPLOYEE", "description": "Standard employee access"}
    ]
    
    for role_data in approved_roles:
        stmt = select(CloudRole).where(CloudRole.name == role_data["name"])
        result = await db.execute(stmt)
        existing_role = result.scalar_one_or_none()
        
        if not existing_role:
            print(f"Creating role: {role_data['name']}")
            new_role = CloudRole(
                name=role_data["name"], 
                description=role_data["description"]
            )
            db.add(new_role)
        else:
            print(f"Role {role_data['name']} already exists. Skipping.")
            
    await db.commit()

async def seed_permissions(db: AsyncSession) -> None:
    """Seeds permissions and links them to roles. Idempotent."""
    
    # Seed permission rows
    for name, description, resource, action in PERMISSION_DEFINITIONS:
        stmt = select(CloudPermission).where(CloudPermission.name == name)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if not existing:
            print(f"Creating permission: {name}")
            perm = CloudPermission(
                name=name,
                description=description,
                resource=resource,
                action=action
            )
            db.add(perm)
        else:
            print(f"Permission {name} already exists. Skipping.")
    
    await db.commit()
    
    # Link permissions to roles
    for role_name, perm_names in ROLE_PERMISSIONS.items():
        stmt = select(CloudRole).where(CloudRole.name == role_name)
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()
        
        if not role:
            print(f"Role {role_name} not found. Skipping permission linkage.")
            continue
        
        for perm_name in perm_names:
            stmt = select(CloudPermission).where(CloudPermission.name == perm_name)
            result = await db.execute(stmt)
            perm = result.scalar_one_or_none()
            
            if not perm:
                print(f"Permission {perm_name} not found. Skipping.")
                continue
            
            # Check if linkage already exists
            stmt = select(CloudRolePermission).where(
                CloudRolePermission.role_id == role.id,
                CloudRolePermission.permission_id == perm.id
            )
            result = await db.execute(stmt)
            existing_link = result.scalar_one_or_none()
            
            if not existing_link:
                print(f"Linking {role_name} -> {perm_name}")
                link = CloudRolePermission(role_id=role.id, permission_id=perm.id)
                db.add(link)
            else:
                print(f"Link {role_name} -> {perm_name} already exists. Skipping.")
    
    await db.commit()

async def main():
    print("Starting role initialization...")
    async with AsyncSessionLocal() as db:
        await seed_base_roles(db)
        await seed_permissions(db)
    print("Role and permission initialization completed.")

if __name__ == "__main__":
    asyncio.run(main())

