"""Authentication and user management service."""

import sys
import os
from typing import Optional
from sqlalchemy.orm import Session

# Handle both direct execution and package imports
try:
    from ..config.models import User
    from ..config.schemas import UserCreate
except ImportError:
    # Direct execution - add parent directory to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from agent.config.models import User
    from agent.config.schemas import UserCreate


class AuthService:
    """Service for user authentication and management."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_user_id(self, user_id: str) -> Optional[User]:
        """Get user by user_id."""
        return self.db.query(User).filter(User.user_id == user_id).first()

    def create_user(self, user_create: UserCreate) -> User:
        """Create a new user."""
        db_user = User(user_id=user_create.user_id)
        self.db.add(db_user)
        self.db.flush()  # Get the ID without committing
        return db_user

    def get_or_create_user(self, user_id: str) -> User:
        """Get existing user or create new one."""
        user = self.get_user_by_user_id(user_id)
        if not user:
            user_create = UserCreate(user_id=user_id)
            user = self.create_user(user_create)
        return user

    def update_user_context(self, user: User, age: Optional[int] = None, 
                          sex_assigned_at_birth: Optional[str] = None) -> User:
        """Update user context information."""
        if age is not None:
            user.age = age
        if sex_assigned_at_birth is not None:
            user.sex_assigned_at_birth = sex_assigned_at_birth
        
        self.db.flush()
        return user 