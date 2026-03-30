"""
API Endpoints
"""
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.users import router as users_router
from app.api.endpoints.code_review import router as code_review_router
from app.api.endpoints.repositories import router as repositories_router
from app.api.endpoints.webhooks import router as webhooks_router
from app.api.endpoints.analytics import router as analytics_router

__all__ = [
    "auth_router",
    "users_router", 
    "code_review_router",
    "repositories_router",
    "webhooks_router",
    "analytics_router",
]