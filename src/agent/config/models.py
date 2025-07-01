"""
🗄️ Enhanced Database Models with Conversation Memory

Complete database schema including conversation memory, message tracking,
and question management for intelligent conversation flow.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class SessionStatus(Enum):
    """Enumeration for session status."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    EXPIRED = "EXPIRED"
    PAUSED = "PAUSED"
    EMERGENCY = "EMERGENCY"
    INCOMPLETE = "INCOMPLETE"  # Data collection not complete
    TIMEOUT = "TIMEOUT"  # Session timed out
    ABANDONED = "ABANDONED"


class EmergencyLevel(Enum):
    """Emergency triage levels."""
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DataCompletenessLevel(Enum):
    """Data completeness levels for transaction handling."""
    MINIMAL = "MINIMAL"  # Basic info only
    BASIC = "BASIC"  # Some key areas covered
    ADEQUATE = "ADEQUATE"  # Most areas covered
    COMPREHENSIVE = "COMPREHENSIVE"  # All required areas covered
    COMPLETE = "COMPLETE"  # All required areas covered


class QuestionStatus(Enum):
    """Status of individual questions."""
    PENDING = "PENDING"
    ASKED = "ASKED"
    ANSWERED = "ANSWERED"
    SKIPPED = "SKIPPED"
    UNCLEAR = "UNCLEAR"
    TIMEOUT = "TIMEOUT"


class User(Base):
    """User model with comprehensive health data."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True)
    name = Column(String(255))
    phone = Column(String(50))
    date_of_birth = Column(DateTime)
    gender = Column(String(20))
    
    # Demographics
    age = Column(Integer, nullable=True)
    birth_sex = Column(String, nullable=True)  # 'male', 'female', 'other', 'prefer_not_to_say'
    
    # Physical measurements
    height = Column(Float, nullable=True)  # in cm
    weight = Column(Float, nullable=True)  # in kg
    
    # Medical background
    blood_type = Column(String, nullable=True)
    allergies = Column(JSON, default=list, nullable=False)  # List of allergies
    chronic_conditions = Column(JSON, default=list, nullable=False)  # List of conditions
    current_medications = Column(JSON, default=list, nullable=False)  # List of medications
    past_surgeries = Column(JSON, default=list, nullable=False)  # List of surgeries
    hospitalizations = Column(JSON, default=list, nullable=False)  # Past hospitalizations
    
    # Family history
    family_history = Column(JSON, default=dict, nullable=False)  # Family medical history
    
    # Social history
    smoking_status = Column(String, nullable=True)  # 'never', 'former', 'current'
    alcohol_use = Column(String, nullable=True)  # 'none', 'occasional', 'regular', 'heavy'
    substance_use = Column(JSON, default=dict, nullable=False)  # Substance use history
    occupation = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    symptoms = relationship("Symptom", back_populates="user")
    emergency_alerts = relationship("EmergencyAlert", back_populates="user")


class Conversation(Base):
    """Conversation model for tracking medical session state."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE)
    
    # Medical session state
    current_node = Column(String, default="Introduction", nullable=False)
    current_phase = Column(String, default="intro", nullable=False)  # intro, chief_complaint, hpi, ros, etc.
    question_index = Column(Integer, default=0, nullable=False)
    invalid_attempts = Column(Integer, default=0, nullable=False)
    current_question_id = Column(String, nullable=True)
    
    # Multi-symptom management
    symptoms_queue = Column(JSON, default=list, nullable=False)  # Queue of symptoms to process
    current_symptom_id = Column(Integer, ForeignKey("symptoms.id"), nullable=True)
    processed_symptoms = Column(JSON, default=list, nullable=False)  # Completed symptom IDs
    
    # Emergency and triage
    emergency_level = Column(SQLEnum(EmergencyLevel), default=EmergencyLevel.NONE)
    red_flags = Column(JSON, default=list, nullable=False)  # List of detected red flags
    
    # Session variables and state
    variables = Column(JSON, default=dict, nullable=False)
    collected_data = Column(JSON, default=dict, nullable=False)  # Structured medical data
    
    # Data completeness tracking
    data_completeness_level = Column(SQLEnum(DataCompletenessLevel), default=DataCompletenessLevel.MINIMAL)
    required_fields_completed = Column(JSON, default=dict, nullable=False)  # Track completion by category
    skipped_questions = Column(JSON, default=list, nullable=False)  # Questions user chose to skip
    unclear_responses = Column(JSON, default=list, nullable=False)  # Responses needing clarification
    
    # Transaction and persistence control
    min_data_threshold_met = Column(Boolean, default=False, nullable=False)  # Minimum data for storage
    can_be_saved = Column(Boolean, default=False, nullable=False)  # Whether session can be persisted
    completion_score = Column(Float, default=0.0, nullable=False)  # 0-100 completion percentage
    
    # Timeout and session management
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    timeout_warnings = Column(Integer, default=0, nullable=False)
    idle_timeout_minutes = Column(Integer, default=5, nullable=False)
    session_timeout_minutes = Column(Integer, default=30, nullable=False)
    auto_save_enabled = Column(Boolean, default=True, nullable=False)
    
    # Resume and continuation
    can_resume = Column(Boolean, default=True, nullable=False)
    resume_count = Column(Integer, default=0, nullable=False)
    last_resume_at = Column(DateTime(timezone=True), nullable=True)
    
    # Human handoff
    requested_human_handoff = Column(Boolean, default=False, nullable=False)
    handoff_reason = Column(String, nullable=True)
    escalated_to_human = Column(Boolean, default=False, nullable=False)
    
    # Vitals (if provided)
    current_bp_systolic = Column(Integer, nullable=True)
    current_bp_diastolic = Column(Integer, nullable=True)
    current_temperature = Column(Float, nullable=True)
    current_heart_rate = Column(Integer, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_timeout_warning = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")
    current_symptom = relationship("Symptom", foreign_keys=[current_symptom_id])
    question_tracking = relationship("QuestionTracking", back_populates="conversation")
    emergency_alerts = relationship("EmergencyAlert", back_populates="conversation")


class Symptom(Base):
    """Individual symptom with OLDCARTS data structure."""
    __tablename__ = "symptoms"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # Basic symptom info
    name = Column(String, nullable=False)  # e.g., "chest pain", "headache"
    description = Column(Text, nullable=True)  # User's description
    is_primary = Column(Boolean, default=False)  # Is this the chief complaint?
    
    # OLDCARTS Framework
    onset = Column(String, nullable=True)  # When did it start?
    location = Column(String, nullable=True)  # Where exactly?
    duration = Column(String, nullable=True)  # Constant or intermittent?
    character = Column(String, nullable=True)  # Sharp, dull, burning, etc.
    aggravating_factors = Column(JSON, default=list, nullable=False)  # What makes it worse?
    relieving_factors = Column(JSON, default=list, nullable=False)  # What helps?
    timing = Column(String, nullable=True)  # Time patterns
    severity = Column(Integer, nullable=True)  # 1-10 scale
    radiation = Column(String, nullable=True)  # Does it spread?
    
    # Additional clinical data
    progression = Column(String, nullable=True)  # improving, worsening, unchanged
    associated_symptoms = Column(JSON, default=list, nullable=False)  # Related symptoms
    similar_episodes = Column(Text, nullable=True)  # Past similar episodes
    treatments_tried = Column(JSON, default=list, nullable=False)  # What they've tried
    
    # Data completeness tracking
    oldcarts_completion = Column(JSON, default=dict, nullable=False)  # Track what's been asked
    requires_followup = Column(Boolean, default=False)  # Needs clarification
    followup_questions = Column(JSON, default=list, nullable=False)  # Questions to re-ask
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="symptoms")
    conversation = relationship("Conversation", foreign_keys=[conversation_id])


class Message(Base):
    """Message model for storing conversation history with medical context."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    symptom_id = Column(Integer, ForeignKey("symptoms.id"), nullable=True)
    
    # Message details
    question_id = Column(String, nullable=True)  # Which node/question
    phase = Column(String, nullable=True)  # Which medical phase (hpi, ros, etc.)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    
    # Medical context
    medical_category = Column(String, nullable=True)  # e.g., 'oldcarts', 'ros', 'emergency'
    oldcarts_component = Column(String, nullable=True)  # onset, location, etc.
    
    # Validation and processing
    is_valid = Column(Boolean, default=True)
    validation_error = Column(String, nullable=True)
    attempt_number = Column(Integer, default=1)
    requires_clarification = Column(Boolean, default=False)
    
    # AI processing
    extracted_data = Column(JSON, default=dict, nullable=False)  # Structured data extracted
    confidence_score = Column(Float, nullable=True)  # AI confidence in extraction
    
    # Metadata
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_system = Column(Boolean, default=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    symptom = relationship("Symptom")


class EmergencyAlert(Base):
    """Emergency alerts and red flag tracking."""
    __tablename__ = "emergency_alerts"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Alert details
    alert_type = Column(String, nullable=False)  # 'red_flag', 'emergency', 'urgent'
    severity = Column(String, nullable=False)  # EmergencyLevel enum
    trigger_symptoms = Column(JSON, default=list, nullable=False)  # What triggered it
    
    # Medical context
    detected_condition = Column(String, nullable=True)  # Suspected condition
    recommendation = Column(Text, nullable=False)  # What to recommend
    
    # Response tracking
    user_notified = Column(Boolean, default=False)
    user_response = Column(Text, nullable=True)
    escalated = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation = relationship("Conversation")
    user = relationship("User")


class ReviewOfSystems(Base):
    """Review of Systems (ROS) responses."""
    __tablename__ = "review_of_systems"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # System categories
    general = Column(JSON, default=dict, nullable=False)  # fever, weight changes, fatigue
    cardiovascular = Column(JSON, default=dict, nullable=False)  # chest pain, palpitations
    respiratory = Column(JSON, default=dict, nullable=False)  # cough, shortness of breath
    gastrointestinal = Column(JSON, default=dict, nullable=False)  # nausea, abdominal pain
    genitourinary = Column(JSON, default=dict, nullable=False)  # urinary symptoms
    musculoskeletal = Column(JSON, default=dict, nullable=False)  # joint pain, stiffness
    neurological = Column(JSON, default=dict, nullable=False)  # headache, dizziness
    dermatologic = Column(JSON, default=dict, nullable=False)  # rash, skin changes
    psychiatric = Column(JSON, default=dict, nullable=False)  # mood, anxiety
    endocrine = Column(JSON, default=dict, nullable=False)  # thirst, heat/cold intolerance
    hematologic = Column(JSON, default=dict, nullable=False)  # bruising, bleeding
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    conversation = relationship("Conversation")
    user = relationship("User")


class SessionState(Base):
    """Redis-like session state for active conversations."""
    __tablename__ = "session_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    
    # Current state
    current_node = Column(String, nullable=False)
    question_index = Column(Integer, default=0)
    invalid_attempts = Column(Integer, default=0)
    current_question_id = Column(String, nullable=True)
    
    # Collected variables (JSON)
    variables = Column(JSON, default=dict)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False) 


class QuestionTracking(Base):
    """Track individual questions and their completion status."""
    __tablename__ = "question_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # Question identification
    question_id = Column(String, nullable=False)  # Unique question identifier
    question_category = Column(String, nullable=False)  # chief_complaint, hpi, ros, etc.
    oldcarts_component = Column(String, nullable=True)  # onset, location, etc.
    question_text = Column(Text, nullable=False)  # The actual question asked
    question_hash = Column(String, nullable=True)  # Hash for duplicate detection
    
    # Response tracking
    status = Column(String, default=QuestionStatus.PENDING.value, nullable=False)
    user_response = Column(Text, nullable=True)  # User's answer
    extracted_data = Column(JSON, default=dict, nullable=False)  # Structured data extracted
    
    # Quality and completeness
    response_clarity = Column(String, nullable=True)  # clear, vague, unclear
    needs_followup = Column(Boolean, default=False, nullable=False)
    followup_questions = Column(JSON, default=list, nullable=False)
    skip_reason = Column(String, nullable=True)  # Why was this skipped
    
    # Attempts and validation
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    validation_errors = Column(JSON, default=list, nullable=False)
    
    # Additional tracking fields for conversation memory
    last_asked_at = Column(DateTime(timezone=True), nullable=True)
    response_received = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Metadata
    asked_at = Column(DateTime(timezone=True), server_default=func.now())
    answered_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="question_tracking")


class DataCompletenessCheck(Base):
    """Track data completeness requirements and validation."""
    __tablename__ = "data_completeness_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # Completeness categories
    chief_complaint_complete = Column(Boolean, default=False, nullable=False)
    symptom_details_complete = Column(Boolean, default=False, nullable=False)
    medical_history_complete = Column(Boolean, default=False, nullable=False)
    medications_complete = Column(Boolean, default=False, nullable=False)
    allergies_complete = Column(Boolean, default=False, nullable=False)
    social_history_complete = Column(Boolean, default=False, nullable=False)
    family_history_complete = Column(Boolean, default=False, nullable=False)
    review_of_systems_complete = Column(Boolean, default=False, nullable=False)
    
    # Minimum thresholds
    min_fields_required = Column(Integer, default=8, nullable=False)  # Minimum fields for storage
    min_fields_collected = Column(Integer, default=0, nullable=False)
    
    # Completion scoring
    total_possible_points = Column(Integer, default=100, nullable=False)
    points_earned = Column(Integer, default=0, nullable=False)
    completion_percentage = Column(Float, default=0.0, nullable=False)
    
    # Transaction control
    meets_storage_threshold = Column(Boolean, default=False, nullable=False)
    can_complete_session = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    last_calculated = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("Conversation")


class TimeoutEvent(Base):
    """Track timeout events and warnings."""
    __tablename__ = "timeout_events"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # Timeout details
    event_type = Column(String, nullable=False)  # warning, final_warning, timeout
    timeout_duration = Column(Integer, nullable=False)  # seconds of inactivity
    warning_message = Column(Text, nullable=True)  # Message sent to user
    
    # User response
    user_responded = Column(Boolean, default=False, nullable=False)
    response_time = Column(Integer, nullable=True)  # seconds to respond
    user_action = Column(String, nullable=True)  # continue, pause, exit
    
    # Metadata
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    conversation = relationship("Conversation") 