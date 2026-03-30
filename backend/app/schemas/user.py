"""
User schemas for Pydantic models
"""
from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str
    full_name: Optional[str] = None


class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    password: str = Field(..., min_length=8)
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores and hyphens allowed)')
        return v


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    
    @validator('password')
    def password_strength(cls, v):
        if v and len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserResponse(BaseModel):
    """Schema for user response"""
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Schema for login request"""
    email: str
    password: str


class Token(BaseModel):
    """Schema for authentication token"""
    access_token: str
    token_type: str
    user: UserResponse


class TokenData(BaseModel):
    """Schema for token data"""
    email: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None


class OAuth2Request(BaseModel):
    """Schema for OAuth2 token request"""
    grant_type: str = "password"
    username: str
    password: str
    scope: str = ""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None