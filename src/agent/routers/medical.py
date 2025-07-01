"""
🏥 Medical Router for Dynamic Vi LangGraph Agent

Updated router using the new LangGraph architecture with individual agent nodes
for real-time testing of the multi-agent system.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
import os

from ..config.database import get_db
from ..medical_assistant_agent.result import DynamicViAgent
from ..config.models import Conversation, SessionStatus, Message
from ..config.schemas import (
    ChatRequest, 
    ChatResponse, 
    SessionStatusResponse, 
    AICapabilitiesResponse,
    ConversationMessage,
    AIContext,
    OldcartsProgress,
    Summary,
    EmergencyLevel
)

router = APIRouter(
    prefix="/medical",
    tags=["Medical AI Assistant"],
    responses={404: {"description": "Not found"}},
)

def get_dynamic_vi_agent(db: Session = Depends(get_db)) -> DynamicViAgent:
    """Get Dynamic Vi Agent instance."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    return DynamicViAgent(db, openai_api_key)

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with Vi Medical Assistant",
    description="""
    **Chat with Vi, the AI Medical Assistant using LangGraph multi-agent architecture.**
    
    This endpoint provides comprehensive medical data collection with:
    - 🤖 **Multi-agent AI system** with specialized agents for different tasks
    - 📋 **OLDCARTS medical history collection** (Onset, Location, Duration, Character, etc.)
    - 🚨 **Emergency detection and triage** with automatic escalation
    - 💬 **Complete conversation history** with timestamps and phases
    - 📊 **Real-time progress tracking** with completion percentages
    - 🔍 **AI context and reasoning** for debugging and transparency
    
    **Usage Examples:**
    1. **Start new conversation**: Send empty message with user_id
    2. **Continue conversation**: Include session_id from previous response
    3. **Provide medical info**: Describe symptoms, age, medical history
    4. **Emergency scenarios**: System automatically detects and escalates
    
    **Response includes:**
    - AI assistant's response message
    - Complete conversation history with timestamps
    - All collected medical data with progress tracking
    - Emergency level assessment
    - Agent routing and reasoning details
    """
)
async def chat_with_dynamic_vi(
    request: ChatRequest,
    db: Session = Depends(get_db),
    vi_agent: DynamicViAgent = Depends(get_dynamic_vi_agent)
) -> ChatResponse:
    """
    Chat with Dynamic Vi Agent using LangGraph multi-agent architecture.
    """
    try:
        # Process message with Dynamic Vi Agent
        response = vi_agent.process_message(
            request.session_id, 
            request.user_id, 
            request.message
        )
        
        # Get conversation history
        conversation_history = []
        if response.get("session_id"):
            conversation = db.query(Conversation).filter(
                Conversation.session_id == response["session_id"]
            ).first()
            
            if conversation:
                # Add message to database if we have a user message
                if request.message:
                    # Add user message
                    user_msg = Message(
                        conversation_id=conversation.id,
                        role="user",
                        content=request.message,
                        phase=response.get("current_section", "unknown")
                    )
                    db.add(user_msg)
                    
                    # Add Vi's response
                    vi_msg = Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=response.get("message", ""),
                        phase=response.get("current_section", "unknown")
                    )
                    db.add(vi_msg)
                    db.commit()
                
                # Get all messages for conversation history
                messages = db.query(Message).filter(
                    Message.conversation_id == conversation.id
                ).order_by(Message.timestamp).all()
                
                conversation_history = [
                    ConversationMessage(
                        role=msg.role,
                        content=msg.content,
                        timestamp=msg.timestamp.isoformat(),
                        phase=msg.phase
                    )
                    for msg in messages
                ]
        
        # Build enhanced response using Pydantic models
        collected_data = response.get("collected_data", {})
        fields_completed = len([v for v in collected_data.values() if v and v not in ["unclear_response", "skipped_by_user"]])
        
        enhanced_response = ChatResponse(
            # Core response data
            session_id=response.get("session_id", ""),
            message=response.get("message", ""),
            conversation_complete=response.get("conversation_complete", False),
            
            # Medical data collection
            collected_data=collected_data,
            fields_collected=response.get("fields_collected", 0),
            next_field=response.get("next_field", ""),
            current_section=response.get("current_section", ""),
            
            # Progress and status
            completion_readiness=response.get("completion_readiness", 0.0),
            emergency_level=EmergencyLevel(response.get("emergency_level", "NONE")),
            
            # Conversation history
            conversation_history=conversation_history,
            total_messages=len(conversation_history),
            
            # Agent context
            ai_context=AIContext(
                last_agent_action=response.get("ai_context", {}).get("last_agent_action"),
                last_extraction=response.get("ai_context", {}).get("last_extraction"),
                orchestrator_reasoning=response.get("ai_context", {}).get("orchestrator_reasoning"),
                current_field=response.get("current_field"),
                completion_readiness=response.get("completion_readiness")
            ),
            
            # OLDCARTS progress breakdown
            oldcarts_progress=OldcartsProgress(
                age="✅" if collected_data.get("age") else "❌",
                biological_sex="✅" if collected_data.get("biological_sex") else "❌",
                primary_complaint="✅" if collected_data.get("primary_complaint") else "❌",
                onset="✅" if collected_data.get("onset") else "❌",
                location="✅" if collected_data.get("location") else "❌",
                duration="✅" if collected_data.get("duration") else "❌",
                character="✅" if collected_data.get("character") else "❌",
                severity="✅" if collected_data.get("severity") else "❌"
            ),
            
            # Summary statistics
            summary=Summary(
                total_fields_possible=15,
                fields_completed=fields_completed,
                completion_percentage=round((fields_completed / 15) * 100, 1)
            )
        )
        
        return enhanced_response
        
    except Exception as e:
        print(f"Error in Dynamic Vi chat: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.get(
    "/session/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Get Session Status",
    description="Get current session status, progress, and collected data for a specific session."
)
async def get_session_status(
    session_id: str,
    db: Session = Depends(get_db)
) -> SessionStatusResponse:
    """Get current session status and progress."""
    try:
        conversation = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get message count
        message_count = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).count()
        
        # Get collected fields
        collected_data = conversation.collected_data or {}
        fields_collected = len(collected_data)
        
        return SessionStatusResponse(
            session_id=session_id,
            status=conversation.status,
            current_phase=conversation.current_phase,
            emergency_level=conversation.emergency_level,
            message_count=message_count,
            fields_collected=fields_collected,
            collected_data=collected_data,
            conversation_complete=conversation.status in [SessionStatus.COMPLETED.value, SessionStatus.EMERGENCY.value],
            created_at=conversation.started_at.isoformat(),
            updated_at=conversation.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving session status: {str(e)}")

@router.get("/session/{session_id}/summary")
async def get_session_summary(
    session_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get a summary of the collected medical data."""
    try:
        conversation = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Session not found")
        
        collected_data = conversation.collected_data or {}
        
        # Organize data by SOAP sections
        summary = {
            "session_id": session_id,
            "patient_context": {
                "age": collected_data.get("age"),
                "biological_sex": collected_data.get("biological_sex")
            },
            "chief_complaint": {
                "primary_complaint": collected_data.get("primary_complaint"),
                "detailed_description": collected_data.get("detailed_description")
            },
            "oldcarts": {
                "onset": collected_data.get("onset"),
                "location": collected_data.get("location"),
                "duration": collected_data.get("duration"),
                "character": collected_data.get("character"),
                "aggravating_factors": collected_data.get("aggravating_factors"),
                "relieving_factors": collected_data.get("relieving_factors"),
                "timing": collected_data.get("timing"),
                "severity": collected_data.get("severity"),
                "radiation": collected_data.get("radiation"),
                "progression": collected_data.get("progression"),
                "related_symptoms": collected_data.get("related_symptoms"),
                "treatment_attempted": collected_data.get("treatment_attempted")
            },
            "medical_history": {
                "chronic_conditions": collected_data.get("chronic_conditions"),
                "current_medications": collected_data.get("current_medications"),
                "allergies": collected_data.get("allergies"),
                "past_surgeries": collected_data.get("past_surgeries"),
                "hospitalizations": collected_data.get("hospitalizations"),
                "similar_episodes": collected_data.get("similar_episodes")
            },
            "emergency_flags": collected_data.get("emergency_flags", []),
            "total_fields_collected": len([v for v in collected_data.values() if v]),
            "conversation_status": conversation.status
        }
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting session summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving session summary: {str(e)}")

@router.get(
    "/user/{user_id}/sessions",
    summary="Get All Sessions for User",
    description="Get all conversation sessions for a specific user ID, including session details and progress."
)
async def get_user_sessions(
    user_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get all sessions for a specific user."""
    try:
        # Query all conversations for the user
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.started_at.desc()).all()
        
        if not conversations:
            return {
                "user_id": user_id,
                "total_sessions": 0,
                "sessions": [],
                "message": "No sessions found for this user"
            }
        
        # Build session list with details
        sessions = []
        for conversation in conversations:
            # Get all messages for this session from Message table
            messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.timestamp.asc()).all()
            
            # Build conversation history from Message table
            conversation_history = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "phase": msg.phase
                }
                for msg in messages
            ]
            
            # If no messages in Message table, try to get from conversation variables (ai_context)
            if not conversation_history and conversation.variables:
                try:
                    variables = conversation.variables or {}
                    ai_context = variables.get("ai_context", {})
                    if isinstance(ai_context, dict):
                        saved_messages = ai_context.get("conversation_messages", [])
                        conversation_history = [
                            {
                                "role": msg.get("type", "unknown"),
                                "content": msg.get("content", ""),
                                "timestamp": None,  # No timestamp in saved format
                                "phase": "dynamic_ai_conversation"
                            }
                            for msg in saved_messages if isinstance(msg, dict)
                        ]
                except Exception as e:
                    print(f"Error parsing ai_context for session {conversation.session_id}: {e}")
                    conversation_history = []
            
            # Get collected fields count
            collected_data = conversation.collected_data or {}
            fields_collected = len([v for v in collected_data.values() if v and v not in ["unclear_response", "skipped_by_user"]])
            
            session_info = {
                "session_id": conversation.session_id,
                "status": conversation.status.value if conversation.status else "UNKNOWN",
                "current_phase": conversation.current_phase,
                "emergency_level": conversation.emergency_level.value if conversation.emergency_level else "NONE",
                "message_count": len(conversation_history),
                "fields_collected": fields_collected,
                "completion_percentage": round((fields_collected / 15) * 100, 1),
                "created_at": conversation.started_at.isoformat() if conversation.started_at else None,
                "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
                "completed_at": conversation.completed_at.isoformat() if conversation.completed_at else None,
                "collected_data": collected_data,  # Full collected data instead of just preview
                "conversation_history": conversation_history,  # Complete conversation
                "collected_data_preview": {
                    "age": collected_data.get("age"),
                    "primary_complaint": collected_data.get("primary_complaint"),
                    "severity": collected_data.get("severity")
                }
            }
            sessions.append(session_info)
        
        return {
            "user_id": user_id,
            "total_sessions": len(sessions),
            "sessions": sessions,
            "summary": {
                "active_sessions": len([s for s in sessions if s["status"] == "ACTIVE"]),
                "completed_sessions": len([s for s in sessions if s["status"] == "COMPLETED"]),
                "emergency_sessions": len([s for s in sessions if s["status"] == "EMERGENCY"])
            }
        }
        
    except Exception as e:
        print(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving user sessions: {str(e)}")

@router.get(
    "/session/{session_id}/conversations",
    summary="Get Completed Conversations",
    description="Get all conversations for a specific session ID, but only those with completed status."
)
async def get_session_conversations(
    session_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get all completed conversations for a specific session."""
    try:
        # Query only completed conversations for the session
        conversations = db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.status == SessionStatus.COMPLETED.value
        ).order_by(Conversation.started_at.desc()).all()
        
        if not conversations:
            # Check if session exists but has no completed conversations
            session_exists = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()
            
            if not session_exists:
                raise HTTPException(status_code=404, detail="Session not found")
            else:
                return {
                    "session_id": session_id,
                    "total_completed_conversations": 0,
                    "conversations": [],
                    "message": "No completed conversations found for this session"
                }
        
        # Build conversation details with messages
        conversation_details = []
        for conversation in conversations:
            # Get all messages for this conversation
            messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.timestamp.asc()).all()
            
            # Build message history
            message_history = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "phase": msg.phase
                }
                for msg in messages
            ]
            
            # Get collected data
            collected_data = conversation.collected_data or {}
            fields_collected = len([v for v in collected_data.values() if v and v not in ["unclear_response", "skipped_by_user"]])
            
            conversation_info = {
                "conversation_id": conversation.id,
                "session_id": conversation.session_id,
                "user_id": conversation.user_id,
                "status": conversation.status.value if conversation.status else "UNKNOWN",
                "current_phase": conversation.current_phase,
                "emergency_level": conversation.emergency_level.value if conversation.emergency_level else "NONE",
                "message_count": len(message_history),
                "fields_collected": fields_collected,
                "completion_percentage": round((fields_collected / 15) * 100, 1),
                "created_at": conversation.started_at.isoformat() if conversation.started_at else None,
                "completed_at": conversation.completed_at.isoformat() if conversation.completed_at else None,
                "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
                "collected_data": collected_data,
                "message_history": message_history,
                "summary": {
                    "primary_complaint": collected_data.get("primary_complaint", "Not provided"),
                    "severity": collected_data.get("severity", "Not provided"),
                    "emergency_flags": collected_data.get("emergency_flags", []),
                    "total_fields": len(collected_data),
                    "conversation_duration_minutes": None  # Could calculate if needed
                }
            }
            conversation_details.append(conversation_info)
        
        return {
            "session_id": session_id,
            "total_completed_conversations": len(conversation_details),
            "conversations": conversation_details,
            "session_summary": {
                "most_recent_completion": conversation_details[0]["completed_at"] if conversation_details else None,
                "total_messages_across_conversations": sum(c["message_count"] for c in conversation_details),
                "average_fields_collected": round(sum(c["fields_collected"] for c in conversation_details) / len(conversation_details), 1) if conversation_details else 0,
                "emergency_conversations": len([c for c in conversation_details if c["emergency_level"] != "NONE"])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting session conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving session conversations: {str(e)}")


