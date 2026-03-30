from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        Create a new user
        """
        try:
            # Hash password
            hashed_password = get_password_hash(user_data.password)
            
            # Create user instance
            user = User(
                email=user_data.email,
                username=user_data.username,
                full_name=user_data.full_name,
                hashed_password=hashed_password,
                is_active=True,
                is_superuser=False
            )
            
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            
            return UserResponse.from_orm(user)
            
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            await self.db.rollback()
            raise
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID
        """
        try:
            query = select(User).where(User.id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get user by ID: {str(e)}")
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email
        """
        try:
            query = select(User).where(User.email == email)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get user by email: {str(e)}")
            raise
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username
        """
        try:
            query = select(User).where(User.username == username)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get user by username: {str(e)}")
            raise
    
    async def update_user(self, user_id: int, user_update: UserUpdate) -> UserResponse:
        """
        Update user information
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            
            update_data = user_update.dict(exclude_unset=True)
            
            # Update fields
            for field, value in update_data.items():
                setattr(user, field, value)
            
            await self.db.commit()
            await self.db.refresh(user)
            
            return UserResponse.from_orm(user)
            
        except Exception as e:
            logger.error(f"Failed to update user: {str(e)}")
            await self.db.rollback()
            raise
    
    async def delete_user(self, user_id: int) -> None:
        """
        Delete user account
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            
            await self.db.delete(user)
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to delete user: {str(e)}")
            await self.db.rollback()
            raise
    
    async def update_user_preferences(self, user_id: int, preferences: dict) -> UserResponse:
        """
        Update user preferences
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            
            # Update notification settings
            if "notification_settings" in preferences:
                user.notification_settings = str(preferences["notification_settings"])
            
            # Update preferred language
            if "preferred_language" in preferences:
                user.preferred_language = preferences["preferred_language"]
            
            await self.db.commit()
            await self.db.refresh(user)
            
            return UserResponse.from_orm(user)
            
        except Exception as e:
            logger.error(f"Failed to update user preferences: {str(e)}")
            await self.db.rollback()
            raise
    
    async def connect_github_account(self, user_id: int, github_username: str, access_token: str) -> UserResponse:
        """
        Connect GitHub account to user
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            
            user.github_username = github_username
            user.github_access_token = access_token
            
            await self.db.commit()
            await self.db.refresh(user)
            
            return UserResponse.from_orm(user)
            
        except Exception as e:
            logger.error(f"Failed to connect GitHub account: {str(e)}")
            await self.db.rollback()
            raise
    
    async def connect_gitlab_account(self, user_id: int, gitlab_username: str, access_token: str) -> UserResponse:
        """
        Connect GitLab account to user
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            
            user.gitlab_username = gitlab_username
            user.gitlab_access_token = access_token
            
            await self.db.commit()
            await self.db.refresh(user)
            
            return UserResponse.from_orm(user)
            
        except Exception as e:
            logger.error(f"Failed to connect GitLab account: {str(e)}")
            await self.db.rollback()
            raise