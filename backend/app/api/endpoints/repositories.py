from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database.session import get_db
from app.core.dependencies import get_current_active_user
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryUpdate,
    RepositorySyncRequest
)
from app.services.repository_service import RepositoryService
from app.models.user import User
from app.models.repository import Repository
from app.utils.git_integration import GitIntegration

# Router must be defined before any endpoint decorators
router = APIRouter()
logger = logging.getLogger(__name__)


# ---------- SYNCHRONOUS ENDPOINTS ----------
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_repository(
    repo_data: RepositoryCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new repository
    """
    try:
        repository_service = RepositoryService(db)

        existing_repo = repository_service.get_repository_by_name(
            name=repo_data.name,
            user_id=current_user.id
        )

        if existing_repo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository with this name already exists"
            )

        repository = repository_service.create_repository(
            repo_data=repo_data,
            user_id=current_user.id
        )

        return {
            "id": repository.id,
            "name": repository.name,
            "provider": repository.source or "GitHub",
            "language": repository.language or "Unknown",
            "last_review": repository.updated_at.isoformat() if repository.updated_at else None,
            "issues": 0,
            "connected": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create repository: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create repository: {str(e)}"
        )


@router.get("/")
def get_repositories(
    current_user: User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all repositories for the current user
    """
    try:
        logger.info(f"✅ Root GET /repositories called for user {current_user.id}")

        repositories = db.query(Repository).filter(
            Repository.user_id == current_user.id
        ).order_by(Repository.updated_at.desc()).offset(skip).limit(limit).all()

        result = []
        for repo in repositories:
            try:
                result.append({
                    "id": repo.id,
                    "name": repo.name,
                    "provider": repo.source or "GitHub",
                    "language": repo.language or "Unknown",
                    "last_review": repo.updated_at.isoformat() if repo.updated_at else None,
                    "issues": 0,
                    "connected": True
                })
            except Exception as e:
                logger.error(f"Error formatting repository {repo.id}: {str(e)}")
                continue

        return result

    except Exception as e:
        logger.error(f"Failed to get repositories: {str(e)}", exc_info=True)
        return []


@router.get("/{repository_id}")
def get_repository(
    repository_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific repository by ID
    """
    try:
        logger.info(f"GET /repositories/{repository_id} called")
        repository_service = RepositoryService(db)
        repository = repository_service.get_repository_by_id(repository_id)

        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )

        if repository.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this repository"
            )

        return {
            "id": repository.id,
            "name": repository.name,
            "provider": repository.source or "GitHub",
            "language": repository.language or "Unknown",
            "last_review": repository.updated_at.isoformat() if repository.updated_at else None,
            "issues": 0,
            "connected": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get repository: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get repository: {str(e)}"
        )


@router.put("/{repository_id}")
def update_repository(
    repository_id: int,
    repo_update: RepositoryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update a repository
    """
    try:
        repository_service = RepositoryService(db)

        existing_repo = repository_service.get_repository_by_id(repository_id)
        if not existing_repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )

        if existing_repo.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this repository"
            )

        updated_repo = repository_service.update_repository(
            repository_id=repository_id,
            repo_update=repo_update
        )

        return {
            "id": updated_repo.id,
            "name": updated_repo.name,
            "provider": updated_repo.source or "GitHub",
            "language": updated_repo.language or "Unknown",
            "last_review": updated_repo.updated_at.isoformat() if updated_repo.updated_at else None,
            "issues": 0,
            "connected": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update repository: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update repository: {str(e)}"
        )


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repository_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a repository
    """
    try:
        repository_service = RepositoryService(db)

        existing_repo = repository_service.get_repository_by_id(repository_id)
        if not existing_repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )

        if existing_repo.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this repository"
            )

        repository_service.delete_repository(repository_id)
        return {"message": "Repository deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete repository: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete repository: {str(e)}"
        )


@router.post("/{repository_id}/sync")
def sync_repository(
    repository_id: int,
    sync_request: RepositorySyncRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Sync repository with external source (GitHub, GitLab, etc.)
    """
    try:
        repository_service = RepositoryService(db)

        existing_repo = repository_service.get_repository_by_id(repository_id)
        if not existing_repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found"
            )

        if existing_repo.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to sync this repository"
            )

        synced_repo = repository_service.sync_repository(
            repository_id=repository_id,
            sync_data=sync_request
        )

        return {
            "id": synced_repo.id,
            "name": synced_repo.name,
            "provider": synced_repo.source or "GitHub",
            "language": synced_repo.language or "Unknown",
            "last_review": synced_repo.updated_at.isoformat() if synced_repo.updated_at else None,
            "issues": 0,
            "connected": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync repository: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync repository: {str(e)}"
        )


# ---------- ASYNC ENDPOINTS (REAL GIT DATA) ----------
@router.get("/{repository_id}/files")
async def get_repository_files(
    repository_id: int,
    path: str = "/",
    recursive: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get files and folders in the repository (real Git data).
    """
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        if not repo.url:
            return {"files": []}

        access_token = None
        if repo.source == "github" and current_user.github_access_token:
            access_token = current_user.github_access_token
        elif repo.source == "gitlab" and current_user.gitlab_access_token:
            access_token = current_user.gitlab_access_token

        # Use the repository's default branch if no ref provided
        ref = repo.default_branch

        git = GitIntegration()
        files = await git.get_files(repo.url, path, recursive, ref, access_token)
        return {"files": files}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get files for repository {repository_id}: {str(e)}", exc_info=True)
        return {"files": []}


@router.get("/{repository_id}/pull-requests")
async def get_repository_pull_requests(
    repository_id: int,
    status: str = "open",
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get pull requests for the repository (real Git data).
    """
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        if not repo.url:
            return {"pull_requests": []}

        access_token = None
        if repo.source == "github" and current_user.github_access_token:
            access_token = current_user.github_access_token
        elif repo.source == "gitlab" and current_user.gitlab_access_token:
            access_token = current_user.gitlab_access_token

        git = GitIntegration()
        prs = await git.get_pull_requests(repo.url, status, limit, access_token, page=page)
        return {"pull_requests": prs}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pull requests for repository {repository_id}: {str(e)}", exc_info=True)
        return {"pull_requests": []}


@router.get("/{repository_id}/commits")
async def get_repository_commits(
    repository_id: int,
    branch: str = None,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get commit history for the repository (real Git data).
    """
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        if not repo.url:
            return {"commits": []}

        access_token = None
        if repo.source == "github" and current_user.github_access_token:
            access_token = current_user.github_access_token
        elif repo.source == "gitlab" and current_user.gitlab_access_token:
            access_token = current_user.gitlab_access_token

        # If branch not provided, use repo's default branch
        if not branch:
            branch = repo.default_branch or "main"

        git = GitIntegration()
        commits = await git.get_recent_commits(repo.url, branch, limit, access_token)
        return {"commits": commits}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get commits for repository {repository_id}: {str(e)}", exc_info=True)
        return {"commits": []}
    



@router.get("/{repository_id}/file")
async def get_file_content(
    repository_id: int,
    path: str,
    ref: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the content of a specific file from the repository.
    """
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        if not repo.url:
            raise HTTPException(status_code=400, detail="Repository URL not set")

        access_token = None
        if repo.source == "github" and current_user.github_access_token:
            access_token = current_user.github_access_token
        elif repo.source == "gitlab" and current_user.gitlab_access_token:
            access_token = current_user.gitlab_access_token

        # If ref not provided, use repo's default branch
        if not ref:
            ref = repo.default_branch or "main"

        git = GitIntegration()
        content = await git.get_file_content(repo.url, path, ref, access_token)
        if content is None:
            raise HTTPException(status_code=404, detail="File not found or could not be retrieved")
        return {"content": content, "path": path, "ref": ref}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file content for repository {repository_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve file content") 