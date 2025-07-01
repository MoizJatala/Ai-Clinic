"""
🏗️ State Management for Dynamic Vi Agent

Contains state definitions, enums, and data structures for the multi-agent medical system.
"""

from typing import Any, Dict, List
from enum import Enum
from typing_extensions import TypedDict


class ViState(TypedDict):
    """Dynamic state for multi-agent AI system."""
    messages: List
    session_id: str
    user_id: str
    conversation_complete: bool
    collected_fields: Dict[str, Any]
    current_field: str
    next_step: str
    conversation_memory: Dict[str, Any]
    ai_context: Dict[str, Any]
    emergency_level: str
    emergency_flags: List[str]
    retry_count: int
    completion_readiness: float


class AgentStep(Enum):
    """AI-driven agent steps."""
    ORCHESTRATOR = "orchestrator"
    GREETING_AGENT = "greeting_agent"
    EXTRACTION_AGENT = "extraction_agent"
    EVALUATION_AGENT = "evaluation_agent"
    QUESTION_AGENT = "question_agent"
    COMPLETION_AGENT = "completion_agent"
    EMERGENCY_AGENT = "emergency_agent"
