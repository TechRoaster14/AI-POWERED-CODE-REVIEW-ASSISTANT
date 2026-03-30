from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class RepositorySource(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    LOCAL = "local"

class RepositoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    url: Optional[str] = None
    source: RepositorySource = RepositorySource.GITHUB
    private: bool = False
    default_branch: str = "main"
    language: Optional[str] = None
    topics: Optional[List[str]] = None

class RepositoryCreate(RepositoryBase):
    project_id: Optional[int] = None

class RepositoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    private: Optional[bool] = None
    default_branch: Optional[str] = None
    language: Optional[str] = None
    topics: Optional[List[str]] = None

class RepositorySyncRequest(BaseModel):
    force: bool = False
    sync_comments: bool = True
    sync_pull_requests: bool = True

class RepositoryResponse(RepositoryBase):
    id: int
    user_id: int
    project_id: Optional[int]
    external_id: Optional[str]
    webhook_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    last_synced_at: Optional[datetime]
    
    class Config:
        from_attributes = True