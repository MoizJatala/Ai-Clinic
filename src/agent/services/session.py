"""Session management service."""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ..config.models import Conversation, SessionStatus, Message, User


class SessionService:
    """Service for managing conversation sessions."""

    def __init__(self, db: Session):
        self.db = db

    def begin_conversation(self, user: User) -> Conversation:
        """Begin a new conversation transaction."""
        session_id = str(uuid.uuid4())
        
        conversation = Conversation(
            user_id=user.id,
            session_id=session_id,
            status=SessionStatus.INCOMPLETE.value,
            current_node="initialization",
            context_data=json.dumps({})
        )
        self.db.add(conversation)
        self.db.flush()  # Get the ID without committing
        return conversation

    def get_latest_incomplete_conversation(self, user: User) -> Optional[Conversation]:
        """Get the latest incomplete conversation for a user."""
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.user_id == user.id,
                Conversation.status == SessionStatus.INCOMPLETE.value
            )
            .order_by(Conversation.started_at.desc())
            .first()
        )

    def is_conversation_expired(self, conversation: Conversation, hours: int = 24) -> bool:
        """Check if conversation is expired based on last update."""
        if not conversation.updated_at:
            return False
        
        expiry_time = conversation.updated_at + timedelta(hours=hours)
        return datetime.now() > expiry_time

    def update_conversation_node(self, conversation: Conversation, node: str, 
                                context: Optional[Dict[str, Any]] = None) -> Conversation:
        """Update conversation's current node and context."""
        conversation.current_node = node
        
        if context:
            # Merge with existing context
            existing_context = {}
            if conversation.context_data:
                try:
                    existing_context = json.loads(conversation.context_data)
                except json.JSONDecodeError:
                    existing_context = {}
            
            existing_context.update(context)
            conversation.context_data = json.dumps(existing_context)
        
        self.db.flush()
        return conversation

    def add_message(self, conversation: Conversation, role: str, content: str, 
                   is_system: bool = False) -> Message:
        """Add a message to the conversation."""
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            is_system=is_system
        )
        self.db.add(message)
        self.db.flush()
        return message

    def get_conversation_messages(self, conversation: Conversation) -> list[Message]:
        """Get all messages for a conversation."""
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.timestamp.asc())
            .all()
        )

    def complete_conversation(self, conversation: Conversation) -> Conversation:
        """Mark conversation as completed."""
        conversation.status = SessionStatus.COMPLETED.value
        conversation.completed_at = datetime.now()
        self.db.flush()
        return conversation

    def abort_conversation(self, conversation: Conversation) -> Conversation:
        """Mark conversation as aborted and rollback."""
        conversation.status = SessionStatus.ABORTED.value
        self.db.flush()
        return conversation

    def expire_conversation(self, conversation: Conversation) -> Conversation:
        """Mark conversation as expired."""
        conversation.status = SessionStatus.EXPIRED.value
        self.db.flush()
        return conversation

    def rollback_conversation(self, conversation: Conversation):
        """Rollback and discard conversation."""
        # Delete all messages associated with this conversation
        self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).delete()
        
        # Delete the conversation
        self.db.delete(conversation)
        self.db.flush()

    def get_conversation_context(self, conversation: Conversation) -> Dict[str, Any]:
        """Get parsed context data from conversation."""
        if not conversation.context_data:
            return {}
        
        try:
            return json.loads(conversation.context_data)
        except json.JSONDecodeError:
            return {}

    def should_send_idle_nudge(self, conversation: Conversation, minutes: int = 2) -> bool:
        """Check if idle nudge should be sent."""
        if not conversation.updated_at:
            return False
        
        nudge_time = conversation.updated_at + timedelta(minutes=minutes)
        return datetime.now() > nudge_time

    def should_offer_pause(self, conversation: Conversation, minutes: int = 5) -> bool:
        """Check if pause offer should be sent."""
        if not conversation.updated_at:
            return False
        
        pause_time = conversation.updated_at + timedelta(minutes=minutes)
        return datetime.now() > pause_time 