"""
Repository model
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.session import Base


class Repository(Base):
    __tablename__ = "repositories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    url = Column(String(500))
    source = Column(String(50), default="github")  # github, gitlab, bitbucket, local
    private = Column(Boolean, default=False)
    
    # Integration details
    external_id = Column(String(100))  # ID from external service
    webhook_id = Column(String(100))   # Webhook ID if set up
    
    # Repository metadata
    default_branch = Column(String(100), default="main")
    language = Column(String(50))
    topics = Column(Text)  # JSON string of tags/topics
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Repository(id={self.id}, name={self.name}, user_id={self.user_id})>"