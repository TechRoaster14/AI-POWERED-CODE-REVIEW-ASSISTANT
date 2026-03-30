"""
Repository and Pull Request schemas
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ----------------------------
# Repository Schemas
# ----------------------------

class RepositoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    url: str
    provider: str = Field(..., description="github or gitlab")


class RepositoryCreate(RepositoryBase):
    pass


class RepositoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class RepositoryResponse(RepositoryBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


# ----------------------------
# Pull Request Schemas
# ----------------------------

class PullRequestBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_branch: str
    target_branch: str
    provider_pr_id: Optional[str] = Field(
        None, description="PR ID from GitHub or GitLab"
    )


class PullRequestResponse(PullRequestBase):
    id: int
    repository_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }
