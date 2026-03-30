"""
Database session management - Synchronous SQLAlchemy setup
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
import logging
import os

logger = logging.getLogger(__name__)

# Convert async URL to sync URL if needed
db_url = settings.DATABASE_URL
if db_url.startswith('postgresql+asyncpg://'):
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')

# Create SQLAlchemy engine
try:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        pool_size=10,
        max_overflow=20
    )
    logger.info(f"✅ Database engine created successfully for {db_url.split('@')[0].split('://')[0]} database")
    
except Exception as e:
    logger.error(f"❌ Failed to create database engine: {e}")
    # Fallback to SQLite for development
    logger.warning("Falling back to SQLite database")
    db_url = "sqlite:///./code_review.db"
    os.makedirs(os.path.dirname("./code_review.db"), exist_ok=True)
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=settings.DEBUG,
    )

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db() -> Session:
    """
    Get database session - Synchronous
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables - Synchronous
    """
    try:
        # Import ALL models to ensure they're registered
        from app.models.user import User
        from app.models.code_review import CodeReview
        from app.models.repository import Repository
        from app.models.project import Project
        from app.models.ai_feedback import AIFeedback
        from app.models.review_comment import ReviewComment
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
        # Create test user if database is empty
        from app.core.security import get_password_hash
        
        db = SessionLocal()
        try:
            # Check if users table exists and has data
            try:
                user_count = db.query(User).count()
            except:
                user_count = 0
            
            if user_count == 0:
                test_user = User(
                    email="admin@example.com",
                    username="admin",
                    full_name="Administrator",
                    hashed_password=get_password_hash("admin123"),
                    is_active=True,
                    is_superuser=True
                )
                db.add(test_user)
                db.commit()
                logger.info("✅ Test user created: admin@example.com / admin123")
            else:
                logger.info(f"✅ Database already has {user_count} users")
        except Exception as e:
            logger.warning(f"Could not create test user: {e}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        raise


def close_db():
    """
    Close database connections - Synchronous
    """
    engine.dispose()
    logger.info("Database connections closed")


def test_connection():
    """
    Test database connection
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("✅ Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False
    finally:
        db.close()