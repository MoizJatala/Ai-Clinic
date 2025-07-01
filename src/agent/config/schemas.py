"""Enhanced Pydantic schemas for Vi Symptom Agent medical data."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)
    service: str = "Vi Symptom Agent"
    version: str = "2.0.0"


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    user_id: str = Field(..., description="Unique identifier for the user")


# Session Management Schemas
class ConversationStart(BaseModel):
    """Schema for starting a new conversation."""
    user_id: str = Field(..., description="Unique user identifier")
    patient_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional patient metadata")


class SessionStartResponse(BaseModel):
    """Response for starting a new session."""
    session_id: str = Field(..., description="Unique session identifier")
    first_prompt: str = Field(..., description="Initial prompt for the user")
    conversation_id: int = Field(..., description="Database conversation ID")


class SessionResumeResponse(BaseModel):
    """Response for resuming an existing session."""
    session_id: str = Field(..., description="Session identifier")
    last_message: str = Field(..., description="Last message to continue from")
    current_node: Optional[str] = Field(None, description="Current conversation node")
    conversation_id: int = Field(..., description="Database conversation ID")


class MessageIn(BaseModel):
    """Schema for incoming message."""
    role: str = Field(..., description="Message role (user or assistant)")
    content: str = Field(..., description="Message content")


class MessageOut(BaseModel):
    """Schema for outgoing message."""
    role: str = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    is_system: bool = Field(False, description="Whether this is a system message")


class EmergencyLevel(str, Enum):
    """Emergency triage levels."""
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    user_id: str = Field(..., description="Unique identifier for the user", example="user_123")
    message: str = Field("", description="User's message (empty for initial greeting)", example="I am 25 years old")
    session_id: Optional[str] = Field("", description="Session ID for continuing conversation (empty for new session)", example="vi_dynamic_20250616_123456_789")

    class Config:
        schema_extra = {
            "examples": [
                {
                    "summary": "Start new conversation",
                    "description": "Start a new conversation with empty message to get greeting",
                    "value": {
                        "user_id": "user_123",
                        "message": "",
                        "session_id": ""
                    }
                },
                {
                    "summary": "Provide age",
                    "description": "Continue conversation by providing age",
                    "value": {
                        "user_id": "user_123",
                        "message": "I am 25 years old",
                        "session_id": "vi_dynamic_20250616_123456_789"
                    }
                },
                {
                    "summary": "Comprehensive symptom description",
                    "description": "Provide detailed symptom information",
                    "value": {
                        "user_id": "user_123",
                        "message": "I have severe headaches on the right side of my head that started 3 days ago. They are throbbing and 8/10 in pain. Light makes them worse.",
                        "session_id": "vi_dynamic_20250616_123456_789"
                    }
                },
                {
                    "summary": "Emergency scenario",
                    "description": "Emergency chest pain scenario",
                    "value": {
                        "user_id": "user_123",
                        "message": "I am a 45-year-old male with severe crushing chest pain that started 1 hour ago. The pain radiates to my left arm and is 9/10 severity. I also have shortness of breath and nausea.",
                        "session_id": ""
                    }
                }
            ]
        }


class ConversationMessage(BaseModel):
    """Individual conversation message."""
    role: str = Field(..., description="Message role (user or assistant)")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp in ISO format")
    phase: str = Field(..., description="Conversation phase when message was sent")


class AIContext(BaseModel):
    """AI agent context information."""
    last_agent_action: Optional[str] = Field(None, description="Last action performed by an agent")
    last_extraction: Optional[Dict[str, Any]] = Field(None, description="Details of the last extraction attempt")
    orchestrator_reasoning: Optional[str] = Field(None, description="Orchestrator's reasoning for routing decisions")
    current_field: Optional[str] = Field(None, description="Current field being collected")
    completion_readiness: Optional[float] = Field(None, description="Completion readiness score (0.0-1.0)")


class OldcartsProgress(BaseModel):
    """OLDCARTS field collection progress."""
    age: str = Field(..., description="Age collection status", example="✅")
    biological_sex: str = Field(..., description="Biological sex collection status", example="✅")
    primary_complaint: str = Field(..., description="Primary complaint collection status", example="❌")
    onset: str = Field(..., description="Onset collection status", example="❌")
    location: str = Field(..., description="Location collection status", example="❌")
    duration: str = Field(..., description="Duration collection status", example="❌")
    character: str = Field(..., description="Character collection status", example="❌")
    severity: str = Field(..., description="Severity collection status", example="❌")


class Summary(BaseModel):
    """Conversation summary statistics."""
    total_fields_possible: int = Field(..., description="Total number of fields that can be collected", example=15)
    fields_completed: int = Field(..., description="Number of fields successfully collected", example=3)
    completion_percentage: float = Field(..., description="Completion percentage", example=20.0)


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str = Field(..., description="Session identifier", example="vi_dynamic_20250616_123456_789")
    message: str = Field(..., description="AI assistant's response message", example="Hello! I'm Vi, your virtual health assistant...")
    conversation_complete: bool = Field(..., description="Whether the conversation is complete", example=False)
    
    # Medical data collection
    collected_data: Dict[str, Any] = Field(..., description="All collected medical data", example={"age": "25", "biological_sex": "Female"})
    fields_collected: int = Field(..., description="Number of fields collected", example=2)
    next_field: str = Field(..., description="Next field to collect", example="primary_complaint")
    current_section: str = Field(..., description="Current conversation section", example="collecting_primary_complaint")
    
    # Progress and status
    completion_readiness: float = Field(..., description="Completion readiness score (0.0-1.0)", example=0.2)
    emergency_level: EmergencyLevel = Field(..., description="Emergency triage level", example=EmergencyLevel.NONE)
    
    # Conversation context
    conversation_history: List[ConversationMessage] = Field(..., description="Complete conversation history")
    total_messages: int = Field(..., description="Total number of messages in conversation", example=4)
    
    # Agent context
    ai_context: AIContext = Field(..., description="AI agent context and reasoning")
    
    # Progress tracking
    oldcarts_progress: OldcartsProgress = Field(..., description="OLDCARTS field collection progress")
    summary: Summary = Field(..., description="Conversation summary statistics")


class SessionStartRequest(BaseModel):
    """Request to start a new medical consultation session."""
    user_id: str = Field(..., description="Unique user identifier")
    patient_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional patient metadata")


class EmergencyAlert(BaseModel):
    """Emergency alert information."""
    alert_id: str = Field(..., description="Unique alert identifier")
    severity: str = Field(..., description="Emergency severity level")
    trigger_symptoms: List[str] = Field(..., description="Symptoms that triggered the alert")
    recommendation: str = Field(..., description="Recommended action")
    timestamp: datetime = Field(..., description="When alert was created")


class SymptomData(BaseModel):
    """OLDCARTS symptom data structure."""
    name: str = Field(..., description="Symptom name")
    is_primary: bool = Field(False, description="Whether this is the primary complaint")
    
    # OLDCARTS components
    onset: Optional[str] = Field(None, description="When symptom started")
    location: Optional[str] = Field(None, description="Where symptom is located")
    duration: Optional[str] = Field(None, description="Duration pattern of symptom")
    character: Optional[str] = Field(None, description="Character/quality of symptom")
    aggravating_factors: Optional[List[str]] = Field(None, description="What makes it worse")
    relieving_factors: Optional[List[str]] = Field(None, description="What makes it better")
    timing: Optional[str] = Field(None, description="Timing patterns")
    severity: Optional[int] = Field(None, ge=1, le=10, description="Severity on 1-10 scale")
    radiation: Optional[str] = Field(None, description="Does it spread/radiate")
    
    # Additional data
    progression: Optional[str] = Field(None, description="How symptom has changed")
    associated_symptoms: Optional[List[str]] = Field(None, description="Related symptoms")
    similar_episodes: Optional[str] = Field(None, description="Past similar episodes")
    treatments_tried: Optional[List[str]] = Field(None, description="Treatments attempted")
    
    # Completeness tracking
    oldcarts_completion: Optional[Dict[str, bool]] = Field(None, description="OLDCARTS completion status")


class MedicalHistory(BaseModel):
    """Comprehensive medical history data."""
    # Demographics
    age: Optional[int] = Field(None, ge=0, le=150, description="Patient age")
    birth_sex: Optional[str] = Field(None, description="Biological sex assigned at birth")
    
    # Medical background
    chronic_conditions: Optional[List[str]] = Field(None, description="Chronic medical conditions")
    current_medications: Optional[List[str]] = Field(None, description="Current medications")
    allergies: Optional[List[str]] = Field(None, description="Known allergies")
    past_surgeries: Optional[List[str]] = Field(None, description="Previous surgeries")
    hospitalizations: Optional[List[str]] = Field(None, description="Past hospitalizations")
    
    # Family history
    family_history: Optional[Dict[str, Any]] = Field(None, description="Family medical history")
    
    # Social history
    smoking_status: Optional[str] = Field(None, description="Smoking status")
    alcohol_use: Optional[str] = Field(None, description="Alcohol use pattern")
    substance_use: Optional[Dict[str, Any]] = Field(None, description="Substance use history")
    occupation: Optional[str] = Field(None, description="Occupation")


class VitalSigns(BaseModel):
    """Vital signs and measurements."""
    blood_pressure_systolic: Optional[int] = Field(None, ge=50, le=250, description="Systolic BP")
    blood_pressure_diastolic: Optional[int] = Field(None, ge=30, le=150, description="Diastolic BP")
    heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Heart rate (BPM)")
    temperature: Optional[float] = Field(None, ge=90.0, le=110.0, description="Temperature (F)")
    height: Optional[float] = Field(None, ge=50.0, le=300.0, description="Height (cm)")
    weight: Optional[float] = Field(None, ge=10.0, le=500.0, description="Weight (kg)")


class ReviewOfSystems(BaseModel):
    """Review of Systems (ROS) data."""
    general: Optional[Dict[str, Any]] = Field(None, description="General symptoms")
    cardiovascular: Optional[Dict[str, Any]] = Field(None, description="Cardiovascular symptoms")
    respiratory: Optional[Dict[str, Any]] = Field(None, description="Respiratory symptoms")
    gastrointestinal: Optional[Dict[str, Any]] = Field(None, description="GI symptoms")
    genitourinary: Optional[Dict[str, Any]] = Field(None, description="GU symptoms")
    musculoskeletal: Optional[Dict[str, Any]] = Field(None, description="Musculoskeletal symptoms")
    neurological: Optional[Dict[str, Any]] = Field(None, description="Neurological symptoms")
    dermatologic: Optional[Dict[str, Any]] = Field(None, description="Skin symptoms")
    psychiatric: Optional[Dict[str, Any]] = Field(None, description="Mental health symptoms")
    endocrine: Optional[Dict[str, Any]] = Field(None, description="Endocrine symptoms")
    hematologic: Optional[Dict[str, Any]] = Field(None, description="Blood-related symptoms")


class SessionStatus(BaseModel):
    """Comprehensive session status."""
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Session status")
    current_node: str = Field(..., description="Current conversation node")
    current_phase: str = Field(..., description="Current medical phase")
    
    # Emergency status
    emergency_level: str = Field("none", description="Current emergency level")
    red_flags: List[Dict[str, Any]] = Field(default_factory=list, description="Detected red flags")
    
    # Progress tracking
    symptoms_queue: List[str] = Field(default_factory=list, description="Symptoms queued for processing")
    processed_symptoms: List[str] = Field(default_factory=list, description="Completed symptoms")
    symptoms_collected: int = Field(0, description="Number of symptoms collected")
    emergency_alerts: int = Field(0, description="Number of emergency alerts")
    
    # Data collection
    variables: Dict[str, Any] = Field(default_factory=dict, description="Collected variables")
    
    # Timestamps
    started_at: datetime = Field(..., description="Session start time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    expires_at: Optional[datetime] = Field(None, description="Session expiration time")


class DetailedSessionSummary(BaseModel):
    """Detailed medical consultation summary."""
    session_info: Dict[str, Any] = Field(..., description="Session metadata")
    patient_data: Dict[str, Any] = Field(..., description="Patient demographic and medical data")
    symptoms: List[SymptomData] = Field(default_factory=list, description="Collected symptoms")
    emergency_alerts: List[EmergencyAlert] = Field(default_factory=list, description="Emergency alerts")
    red_flags: List[Dict[str, Any]] = Field(default_factory=list, description="Red flag symptoms")
    completion_status: Dict[str, Any] = Field(..., description="Data completeness metrics")


class EmergencyStatus(BaseModel):
    """Emergency status response."""
    session_id: str = Field(..., description="Session identifier")
    emergency_level: str = Field(..., description="Current emergency level")
    red_flags: List[Dict[str, Any]] = Field(..., description="Detected red flags")
    emergency_alerts: List[EmergencyAlert] = Field(..., description="Emergency alerts")
    requires_immediate_care: bool = Field(..., description="Whether immediate care needed")
    recommendation: str = Field(..., description="Recommended action")


class DataCompleteness(BaseModel):
    """Data completeness metrics."""
    overall_percentage: float = Field(..., ge=0, le=100, description="Overall completion percentage")
    collected_fields: List[str] = Field(..., description="Successfully collected fields")
    missing_fields: List[str] = Field(..., description="Missing required fields")
    symptoms_collected: int = Field(..., description="Number of symptoms collected")
    oldcarts_completeness: float = Field(..., ge=0, le=100, description="OLDCARTS completion percentage")


class ValidationError(BaseModel):
    """Validation error details."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")
    value: Optional[str] = Field(None, description="Invalid value provided")
    expected_format: Optional[str] = Field(None, description="Expected format or values")


class MedicalConsultationResponse(BaseModel):
    """Complete medical consultation response."""
    session_summary: SessionStatus = Field(..., description="Session status")
    medical_data: MedicalHistory = Field(..., description="Collected medical history")
    symptoms: List[SymptomData] = Field(..., description="Symptom details")
    vitals: Optional[VitalSigns] = Field(None, description="Vital signs")
    ros: Optional[ReviewOfSystems] = Field(None, description="Review of systems")
    emergency_status: EmergencyStatus = Field(..., description="Emergency assessment")
    completeness: DataCompleteness = Field(..., description="Data completeness")
    
    # Clinical recommendations
    recommended_specialty: Optional[str] = Field(None, description="Recommended medical specialty")
    urgency_level: str = Field(..., description="Urgency level for care")
    next_steps: List[str] = Field(..., description="Recommended next steps")


# Legacy compatibility
class StartSessionResponse(ChatResponse):
    """Backward compatibility for start session response."""
    pass


class SessionStatusResponse(BaseModel):
    """Response model for session status endpoint."""
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Session status")
    current_phase: str = Field(..., description="Current conversation phase")
    emergency_level: str = Field(..., description="Emergency level")
    message_count: int = Field(..., description="Total message count")
    fields_collected: int = Field(..., description="Number of fields collected")
    collected_data: Dict[str, Any] = Field(..., description="Collected medical data")
    conversation_complete: bool = Field(..., description="Whether conversation is complete")
    created_at: str = Field(..., description="Session creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class AICapabilitiesResponse(BaseModel):
    """Response model for AI capabilities endpoint."""
    agent_name: str = Field(..., description="Name of the AI agent")
    version: str = Field(..., description="Agent version")
    architecture: str = Field(..., description="System architecture")
    individual_agents: List[str] = Field(..., description="List of individual agent capabilities")
    flow: str = Field(..., description="Agent flow description")
    capabilities: List[str] = Field(..., description="System capabilities")
    langgraph_features: List[str] = Field(..., description="LangGraph specific features") 