"""
Main FastAPI application - Corrected version
"""
from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.database.session import init_db, close_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events
    """
    # Startup
    logger.info("Starting AI Code Review Assistant...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.warning("Starting without database...")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)


# Global exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Log validation errors and return a 422 response with details.
    """
    logger.error(f"Request validation error for {request.method} {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


# ✅ FIX: Add CORS middleware with explicit settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# ✅ FIX: Add manual CORS middleware as fallback
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """Add CORS headers to all responses"""
    response = await call_next(request)
    
    # Get the origin from the request
    origin = request.headers.get("origin")
    
    # Check if origin is allowed
    if origin and origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Type"
    
    return response


# ✅ FIX: Add OPTIONS handler for all routes
@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str, request: Request):
    """Handle OPTIONS requests for CORS preflight"""
    origin = request.headers.get("origin")
    if origin and origin in settings.ALLOWED_ORIGINS:
        return JSONResponse(
            content={},
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
                "Access-Control-Max-Age": "600",
            }
        )
    return JSONResponse(content={}, status_code=200)


# Log CORS settings
logger.info(f"CORS configured with origins: {settings.ALLOWED_ORIGINS}")


@app.get("/")
async def root():
    """
    Root endpoint
    """
    return {
        "message": "Welcome to AI Code Review Assistant API",
        "version": settings.APP_VERSION,
        "docs": "/api/docs" if settings.DEBUG else None,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    from datetime import datetime
    import sys
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": settings.APP_VERSION,
        "python_version": sys.version
    }


# Import and include routers
from app.api.endpoints import auth, code_review, repositories, users, webhooks, analytics, projects
from app.api.endpoints import review_comments

app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["authentication"])
app.include_router(users.router, prefix=settings.API_V1_PREFIX, tags=["users"])

# ✅ Mount code_review router
app.include_router(code_review.router, prefix=settings.API_V1_PREFIX, tags=["code-review"])

# ✅ Mount repositories router
app.include_router(
    repositories.router, 
    prefix=settings.API_V1_PREFIX + "/repositories",
    tags=["repositories"]
)

# ✅ Mount projects router
app.include_router(
    projects.router, 
    prefix=settings.API_V1_PREFIX + "/projects",
    tags=["projects"]
)

# ✅ Mount review_comments router
app.include_router(
    review_comments.router, 
    prefix=settings.API_V1_PREFIX + "/review-comments",
    tags=["review-comments"]
)

app.include_router(webhooks.router, prefix=settings.API_V1_PREFIX, tags=["webhooks"])
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX, tags=["analytics"])

logger.info("All API routers loaded successfully")


# Debug endpoint to see all routes
@app.get("/api/v1/debug/routes")
async def debug_routes():
    """
    Debug endpoint to see all available routes
    """
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, 'methods') else []
        })
    
    return {"routes": routes}