from typing import Optional, List
from datetime import datetime
import uuid
from pydantic import BaseModel, EmailStr, ConfigDict

class CloudUserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None

class CloudUserCreate(CloudUserBase):
    password: str
    role_name: str

class CloudRoleResponse(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)

class CloudUserResponse(CloudUserBase):
    id: uuid.UUID
    is_active: bool
    is_email_verified: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    roles: List[CloudRoleResponse] = []

    model_config = ConfigDict(from_attributes=True)


class EmployeeCreateResponse(BaseModel):
    """Minimal response returned on successful employee creation.
    
    Deliberately omits all personal, internal, and identity fields.
    Full user details are only accessible through authorized endpoints.
    """
    success: bool = True
    message: str = "Employee created successfully"
