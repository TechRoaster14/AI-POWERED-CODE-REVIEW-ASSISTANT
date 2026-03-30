# backend/app/services/repository_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import asyncio
import json
import os

from app.models.repository import Repository
from app.models.code_review import CodeReview
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryResponse,
    RepositoryUpdate,
    RepositorySyncRequest
)
from app.utils.git_integration import GitIntegration
from app.core.config import settings

logger = logging.getLogger(__name__)

class RepositoryService:
    def __init__(self, db: Session):
        self.db = db
        self.git_integration = GitIntegration()
        # Load GitHub token from settings or environment
        self.github_token = None
        
        # Try to get token from settings first
        if hasattr(settings, 'GITHUB_ACCESS_TOKEN') and settings.GITHUB_ACCESS_TOKEN:
            self.github_token = settings.GITHUB_ACCESS_TOKEN
            logger.info(f"✅ GitHub token loaded from settings: {self._mask_token(self.github_token)}")
        else:
            # Fallback to environment variable
            self.github_token = os.getenv("GITHUB_ACCESS_TOKEN")
            if self.github_token:
                logger.info(f"✅ GitHub token loaded from environment: {self._mask_token(self.github_token)}")
            else:
                logger.warning("⚠️ No GitHub token found. Rate limits: 60 requests/hour")
    
    def _mask_token(self, token: str) -> str:
        """Mask token for logging"""
        if not token:
            return "None"
        if len(token) > 8:
            return token[:8] + "..." + token[-4:]
        return "***"

    def create_repository(self, repo_data: RepositoryCreate, user_id: int) -> RepositoryResponse:
        """
        Create a new repository with GitHub metadata
        """
        try:
            logger.info(f"🚀 Creating repository '{repo_data.name}' for user {user_id}")
            logger.info(f"Repository data: {repo_data.dict(exclude_unset=True)}")
            
            # Check if repository with same name exists
            existing = self.get_repository_by_name(repo_data.name, user_id)
            if existing:
                logger.warning(f"Repository '{repo_data.name}' already exists for user {user_id}")
                raise ValueError("Repository with this name already exists")
            
            # Default values
            language = repo_data.language
            default_branch = repo_data.default_branch or "main"
            description = repo_data.description
            source = repo_data.source.value if repo_data.source else "github"
            
            # Try to fetch metadata from GitHub if URL is provided
            if repo_data.url and 'github.com' in repo_data.url:
                try:
                    logger.info(f"🔍 Fetching metadata from GitHub for {repo_data.url}")
                    
                    # Create new event loop for async call
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Fetch metadata from GitHub using the token
                    metadata = loop.run_until_complete(
                        self.git_integration.get_repository_metadata(
                            repo_data.url, 
                            self.github_token
                        )
                    )
                    loop.close()
                    
                    if metadata:
                        # Update with GitHub data
                        language = metadata.get("language") or language
                        default_branch = metadata.get("default_branch") or default_branch
                        description = metadata.get("description") or description
                        
                        logger.info(f"✅ GitHub metadata fetched successfully:")
                        logger.info(f"   - Language: {language}")
                        logger.info(f"   - Default branch: {default_branch}")
                        logger.info(f"   - Description: {description}")
                        logger.info(f"   - Private: {metadata.get('private')}")
                        logger.info(f"   - Stars: {metadata.get('stars')}")
                    else:
                        logger.warning(f"⚠️ Could not fetch metadata for {repo_data.url}")
                        
                except Exception as e:
                    logger.error(f"❌ Error fetching GitHub metadata: {str(e)}", exc_info=True)
                    # Continue with creation even if metadata fetch fails
            else:
                logger.info("ℹ️ No GitHub URL provided or not a GitHub repository, skipping metadata fetch")

            # Convert topics to JSON string
            topics_json = None
            if repo_data.topics:
                topics_json = json.dumps(repo_data.topics)

            # Create repository instance
            repository = Repository(
                name=repo_data.name,
                description=description,
                url=repo_data.url,
                source=source,
                private=repo_data.private,
                default_branch=default_branch,
                language=language,
                user_id=user_id,
                project_id=repo_data.project_id,
                topics=topics_json,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            self.db.add(repository)
            self.db.commit()
            self.db.refresh(repository)

            logger.info(f"✅ Repository created successfully with ID: {repository.id}")
            logger.info(f"   - Name: {repository.name}")
            logger.info(f"   - Language: {repository.language}")
            logger.info(f"   - Source: {repository.source}")
            
            return RepositoryResponse.from_orm(repository)

        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to create repository: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    def get_repositories(self, user_id: int, skip: int = 0, limit: int = 100) -> List[RepositoryResponse]:
        """
        Get all repositories for a user
        """
        try:
            logger.info(f"📋 Fetching repositories for user {user_id} (skip={skip}, limit={limit})")
            
            repositories = self.db.query(Repository).filter(
                Repository.user_id == user_id
            ).order_by(Repository.updated_at.desc()).offset(skip).limit(limit).all()
            
            logger.info(f"Found {len(repositories)} repositories")
            
            return [RepositoryResponse.from_orm(repo) for repo in repositories]

        except Exception as e:
            logger.error(f"❌ Failed to get repositories: {str(e)}", exc_info=True)
            raise

    def get_repository_by_id(self, repository_id: int) -> Optional[Repository]:
        """
        Get repository by ID
        """
        try:
            logger.info(f"🔍 Fetching repository by ID: {repository_id}")
            
            repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
            
            if repo:
                logger.info(f"✅ Found repository: {repo.name}")
            else:
                logger.warning(f"⚠️ Repository {repository_id} not found")
                
            return repo
            
        except Exception as e:
            logger.error(f"❌ Failed to get repository by ID: {str(e)}", exc_info=True)
            raise

    def get_repository_by_name(self, name: str, user_id: int) -> Optional[Repository]:
        """
        Get repository by name for a user
        """
        try:
            logger.info(f"🔍 Checking if repository '{name}' exists for user {user_id}")
            
            repo = self.db.query(Repository).filter(
                Repository.name == name,
                Repository.user_id == user_id
            ).first()
            
            if repo:
                logger.info(f"✅ Found existing repository: {name}")
            else:
                logger.info(f"✅ Repository '{name}' is available")
                
            return repo
            
        except Exception as e:
            logger.error(f"❌ Failed to get repository by name: {str(e)}", exc_info=True)
            raise

    def update_repository(self, repository_id: int, repo_update: RepositoryUpdate) -> RepositoryResponse:
        """
        Update repository
        """
        try:
            logger.info(f"🔄 Updating repository {repository_id}")
            
            repository = self.get_repository_by_id(repository_id)
            if not repository:
                raise ValueError(f"Repository {repository_id} not found")

            update_data = repo_update.dict(exclude_unset=True)
            logger.info(f"Update data: {update_data}")

            # Handle topics separately
            topics = update_data.pop("topics", None)
            if topics is not None:
                repository.topics = json.dumps(topics)

            # Update other fields
            for field, value in update_data.items():
                if value is not None:
                    setattr(repository, field, value)

            repository.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(repository)

            logger.info(f"✅ Repository {repository_id} updated successfully")
            
            return RepositoryResponse.from_orm(repository)

        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to update repository: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    def delete_repository(self, repository_id: int) -> None:
        """
        Delete repository
        """
        try:
            logger.info(f"🗑️ Deleting repository {repository_id}")
            
            repository = self.get_repository_by_id(repository_id)
            if not repository:
                raise ValueError(f"Repository {repository_id} not found")

            # Delete the repository
            self.db.delete(repository)
            self.db.commit()

            logger.info(f"✅ Repository {repository_id} deleted successfully")

        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to delete repository: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    def sync_repository(self, repository_id: int, sync_data: RepositorySyncRequest) -> RepositoryResponse:
        """
        Sync repository with external source
        """
        try:
            logger.info(f"🔄 Syncing repository {repository_id}")
            
            repository = self.get_repository_by_id(repository_id)
            if not repository:
                raise ValueError(f"Repository {repository_id} not found")

            # Update last synced timestamp
            repository.last_synced_at = datetime.utcnow()
            repository.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(repository)

            logger.info(f"✅ Repository {repository_id} synced successfully")
            
            return RepositoryResponse.from_orm(repository)

        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to sync repository: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    async def sync_repository_async(self, repository_id: int, sync_data: RepositorySyncRequest) -> RepositoryResponse:
        """
        Async version of sync repository - fetches real data from GitHub
        """
        try:
            logger.info(f"🔄 Async syncing repository {repository_id}")
            
            repository = self.get_repository_by_id(repository_id)
            if not repository:
                raise ValueError(f"Repository {repository_id} not found")

            # Fetch fresh metadata from GitHub
            if repository.url and 'github.com' in repository.url:
                try:
                    metadata = await self.git_integration.get_repository_metadata(
                        repository.url,
                        self.github_token
                    )
                    
                    if metadata:
                        # Update repository with latest metadata
                        if metadata.get("language"):
                            repository.language = metadata.get("language")
                        if metadata.get("default_branch"):
                            repository.default_branch = metadata.get("default_branch")
                        if metadata.get("description"):
                            repository.description = metadata.get("description")
                        
                        logger.info(f"✅ Updated repository with fresh GitHub data")
                        logger.info(f"   - Language: {repository.language}")
                        logger.info(f"   - Default branch: {repository.default_branch}")
                except Exception as e:
                    logger.error(f"❌ Failed to fetch GitHub metadata during sync: {str(e)}")

            repository.last_synced_at = datetime.utcnow()
            repository.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(repository)

            logger.info(f"✅ Repository {repository_id} async sync completed")
            
            return RepositoryResponse.from_orm(repository)

        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to sync repository async: {str(e)}", exc_info=True)
            self.db.rollback()
            raise

    def get_repository_stats(self, repository_id: int) -> Dict[str, Any]:
        """
        Get repository statistics including review counts and scores
        """
        try:
            logger.info(f"📊 Fetching stats for repository {repository_id}")
            
            # Get total code reviews for this repository
            total_reviews = self.db.query(func.count(CodeReview.id)).filter(
                CodeReview.repository_id == repository_id
            ).scalar() or 0

            # Get average scores
            avg_scores = self.db.query(
                func.avg(CodeReview.quality_score),
                func.avg(CodeReview.security_score),
                func.avg(CodeReview.overall_score)
            ).filter(CodeReview.repository_id == repository_id).first()

            # Get recent activity (last 5 reviews)
            recent_reviews = self.db.query(CodeReview).filter(
                CodeReview.repository_id == repository_id
            ).order_by(CodeReview.created_at.desc()).limit(5).all()

            # Count issues from all reviews
            total_issues = 0
            security_issues = 0
            quality_issues = 0
            
            all_reviews = self.db.query(CodeReview).filter(
                CodeReview.repository_id == repository_id
            ).all()
            
            for review in all_reviews:
                if review.ai_analysis:
                    security_issues += review.ai_analysis.get('security', {}).get('issues_found', 0)
                    quality_issues += review.ai_analysis.get('quality', {}).get('issues_found', 0)
            
            total_issues = security_issues + quality_issues

            stats = {
                "repository_id": repository_id,
                "total_reviews": total_reviews,
                "total_issues": total_issues,
                "security_issues": security_issues,
                "quality_issues": quality_issues,
                "avg_quality_score": round(avg_scores[0] or 0, 2) if avg_scores else 0,
                "avg_security_score": round(avg_scores[1] or 0, 2) if avg_scores else 0,
                "avg_overall_score": round(avg_scores[2] or 0, 2) if avg_scores else 0,
                "recent_activity": [
                    {
                        "id": review.id,
                        "title": review.title,
                        "created_at": review.created_at.isoformat() if review.created_at else None,
                        "status": review.status,
                        "overall_score": review.overall_score
                    }
                    for review in recent_reviews
                ]
            }

            logger.info(f"✅ Stats for repository {repository_id}: {stats}")
            return stats

        except Exception as e:
            logger.error(f"❌ Failed to get repository stats: {str(e)}", exc_info=True)
            raise