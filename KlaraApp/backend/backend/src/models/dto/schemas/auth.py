from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID


class LoginRequest(BaseModel):
    azure_ad_token: Optional[str] = None
    username: Optional[str] = None  # work_email
    password: Optional[str] = None
    
    @field_validator('azure_ad_token', 'username', 'password')
    @classmethod
    def validate_auth_method(cls, v, info):
        return v
    
    def model_post_init(self, __context):
        # Either azure_ad_token OR (username AND password) must be provided
        has_azure = self.azure_ad_token is not None
        has_username_password = self.username is not None and self.password is not None
        
        if not (has_azure or has_username_password):
            raise ValueError("Either azure_ad_token or both username and password must be provided")
        
        if has_azure and has_username_password:
            raise ValueError("Provide either azure_ad_token or username/password, not both")
    



class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class UserClaims(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    azure_ad_oid: Optional[str] = None
    department_id: Optional[UUID] = None
