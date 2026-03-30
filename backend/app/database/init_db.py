from app.database.session import Base, engine
from app.models.user import User
from app.models.repository import Repository
from app.models.code_review import CodeReview
from app.models.review_comment import ReviewComment
from app.models.ai_feedback import AIFeedback

async def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)