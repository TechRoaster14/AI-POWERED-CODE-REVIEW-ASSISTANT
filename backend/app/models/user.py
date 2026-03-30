"""
User model
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database.session import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(200))
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # GitHub/GitLab integration
    github_username = Column(String(100), nullable=True)
    gitlab_username = Column(String(100), nullable=True)
    github_access_token = Column(Text, nullable=True)
    gitlab_access_token = Column(Text, nullable=True)
    
    # Preferences
    preferred_language = Column(String(50), default="python")
    notification_settings = Column(Text, default="{}")  # JSON string
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"