"""
🎯 Result Processing for Dynamic Vi Agent

Contains the main DynamicViAgent class that orchestrates the multi-agent medical conversation system.
Handles conversation processing, state management, and result generation.
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from sqlalchemy.orm import Session

# Fix imports to use absolute imports
try:
    from agent.config.models import Conversation, SessionStatus, EmergencyLevel
    from agent.config.database import get_db
except ImportError:
    from ..config.models import Conversation, SessionStatus, EmergencyLevel
    from ..config.database import get_db

# Import modular components
from .states import ViState, AgentStep
from .prompts import AGENT_SYSTEM_PROMPTS
from .agents import AgentFunctions

from dotenv import load_dotenv
load_dotenv()


class DynamicViAgent:
    """Fully dynamic multi-agent AI system for medical conversations."""
    
    def __init__(self, db: Session, api_key: str):
        self.db = db
        self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.7)
        self.agent_functions = AgentFunctions(self.llm, self.db)
        self.graph = self._build_dynamic_graph()
    
    def _build_dynamic_graph(self) -> StateGraph:
        """Build the dynamic multi-agent graph."""
        graph = StateGraph(ViState)
        
        # Add all AI agents
        for agent in AgentStep:
            graph.add_node(agent.value, self.agent_functions.run_ai_agent)
        
        # Set orchestrator as entry point
        graph.set_entry_point(AgentStep.ORCHESTRATOR.value)
        
        # Dynamic routing - orchestrator decides everything
        graph.add_conditional_edges(
            AgentStep.ORCHESTRATOR.value,
            self.agent_functions.route_to_agent,
            {
                AgentStep.GREETING_AGENT.value: AgentStep.GREETING_AGENT.value,
                AgentStep.EXTRACTION_AGENT.value: AgentStep.EXTRACTION_AGENT.value,
                AgentStep.EVALUATION_AGENT.value: AgentStep.EVALUATION_AGENT.value,
                AgentStep.QUESTION_AGENT.value: AgentStep.QUESTION_AGENT.value,
                AgentStep.COMPLETION_AGENT.value: AgentStep.COMPLETION_AGENT.value,
                AgentStep.EMERGENCY_AGENT.value: AgentStep.EMERGENCY_AGENT.value,
                "END": END
            }
        )
        
        # Greeting agent ends the turn (waits for user response)
        graph.add_edge(AgentStep.GREETING_AGENT.value, END)
        
        # Processing agents return to orchestrator for next decision
        for agent in [AgentStep.EXTRACTION_AGENT, AgentStep.QUESTION_AGENT]:
            graph.add_edge(agent.value, AgentStep.ORCHESTRATOR.value)
        
        # Evaluation agent can route to multiple destinations
        graph.add_conditional_edges(
            AgentStep.EVALUATION_AGENT.value,
            self.agent_functions.route_from_evaluation,
            {
                AgentStep.QUESTION_AGENT.value: AgentStep.QUESTION_AGENT.value,
                AgentStep.COMPLETION_AGENT.value: AgentStep.COMPLETION_AGENT.value,
                AgentStep.EMERGENCY_AGENT.value: AgentStep.EMERGENCY_AGENT.value,
                AgentStep.ORCHESTRATOR.value: AgentStep.ORCHESTRATOR.value,
                "END": END
            }
        )
        
        # Terminal agents end the conversation
        graph.add_edge(AgentStep.COMPLETION_AGENT.value, END)
        graph.add_edge(AgentStep.EMERGENCY_AGENT.value, END)
        
        return graph.compile()
    
    def _finalize_conversation(self, state: ViState):
        """Finalize the conversation in the database."""
        try:
            session_id = state.get("session_id")
            if not session_id:
                return
            
            conversation = self.db.query(Conversation).filter_by(session_id=session_id).first()
            if conversation:
                conversation.status = SessionStatus.COMPLETED.value
                conversation.collected_data = state.get("collected_fields", {})
                # Convert emergency level string to enum value
                emergency_level_str = state.get("emergency_level", "NONE")
                try:
                    conversation.emergency_level = EmergencyLevel(emergency_level_str)
                except ValueError:
                    conversation.emergency_level = EmergencyLevel.NONE
                conversation.completed_at = datetime.now()
                conversation.variables = {
                    "ai_context": state.get("ai_context", {}),
                    "completion_readiness": state.get("completion_readiness", 0.0),
                    "total_fields_collected": len(state.get("collected_fields", {}))
                }
                self.db.flush()  # Ensure data is written to database
                self.db.commit()
                print(f"💾 Conversation finalized: {len(state.get('collected_fields', {}))} fields")
        
        except Exception as e:
            print(f"❌ Error finalizing conversation: {e}")
    
    def process_message(self, session_id: Optional[str], user_id: str, message: str) -> Dict[str, Any]:
        """Process user message through the dynamic multi-agent system."""
        try:
            # Initialize or load state
            if session_id:
                # Load existing conversation - FORCE a fresh query and explicit commit first
                # This ensures we get the latest data and any pending transactions are committed
                self.db.commit()  # Commit any pending transactions first
                
                conversation = self.db.query(Conversation).filter_by(session_id=session_id).first()
                if conversation:
                    # Force refresh to get the latest data from database
                    self.db.refresh(conversation)
                    
                    collected_fields = conversation.collected_data or {}
                    ai_context = conversation.variables or {}
                    
                    # DEBUG: Log what we loaded from DB
                    print(f"🔄 DB LOADED - collected_data: {collected_fields}")
                    print(f"🔄 DB LOADED - variables keys: {list(ai_context.keys())}")
                    
                    # IMPROVED MESSAGE LOADING: Simplify and make more robust
                    saved_messages = []
                    
                    # Try to get messages from ai_context
                    if "ai_context" in ai_context and isinstance(ai_context["ai_context"], dict):
                        saved_messages = ai_context["ai_context"].get("conversation_messages", [])
                    
                    # DEBUG: Log message loading
                    print(f"🔄 MESSAGES DEBUG - Found {len(saved_messages)} saved messages")
                    for i, msg in enumerate(saved_messages):
                        print(f"   [{i}] {msg.get('type', 'unknown')}: {msg.get('content', '')[:50]}...")
                    
                    messages = []
                    for msg_data in saved_messages:
                        if isinstance(msg_data, dict):
                            if msg_data.get("type") == "human":
                                messages.append(HumanMessage(content=msg_data.get("content", "")))
                            elif msg_data.get("type") == "ai":
                                messages.append(AIMessage(content=msg_data.get("content", "")))
                    
                    # Also try to get the most recent collected_fields from the context if available
                    if isinstance(ai_context.get("ai_context"), dict) and "total_fields_collected" in ai_context["ai_context"]:
                        # The context might have more recent field data than the database
                        context_fields_count = ai_context["ai_context"].get("total_fields_collected", 0)
                        db_fields_count = len(collected_fields)
                        if context_fields_count > db_fields_count:
                            print(f"🔄 Context has more recent data ({context_fields_count} vs {db_fields_count} fields)")
                    
                    print(f"🔄 Loaded {len(messages)} messages from database: {len([m for m in messages if isinstance(m, AIMessage)])} AI, {len([m for m in messages if isinstance(m, HumanMessage)])} user")
                    print(f"🔄 Loaded {len(collected_fields)} fields: {list(collected_fields.keys())}")
                else:
                    collected_fields = {}
                    ai_context = {}
                    messages = []
            else:
                # Create new conversation
                session_id = f"vi_dynamic_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(user_id) % 10000}"
                conversation = Conversation(
                    user_id=user_id,
                    session_id=session_id,
                    status=SessionStatus.ACTIVE.value,
                    current_phase="dynamic_ai_conversation",
                    emergency_level=EmergencyLevel.NONE.value,
                    collected_data={},
                    variables={}
                )
                self.db.add(conversation)
                self.db.commit()
                collected_fields = {}
                ai_context = {}
                messages = []
            
            # Add current user message if provided
            if message:
                messages.append(HumanMessage(content=message))
            
            # Initialize state
            initial_state = ViState(
                messages=messages,
                session_id=session_id,
                user_id=user_id,
                conversation_complete=False,
                collected_fields=collected_fields,
                current_field="age",
                next_step=AgentStep.ORCHESTRATOR.value,
                conversation_memory={},
                ai_context=ai_context,
                emergency_level=EmergencyLevel.NONE.value,
                emergency_flags=[],
                retry_count=0,
                completion_readiness=0.0
            )
            
            # Run through the dynamic AI system
            final_state = self.graph.invoke(initial_state)
            
            # DEBUG: Check final state
            print(f"🔍 Final state debug:")
            print(f"  - conversation_complete: {final_state.get('conversation_complete', False)}")
            print(f"  - collected_fields: {final_state.get('collected_fields', {})}")
            print(f"  - session_id: {final_state.get('session_id', 'None')}")
            
            # Save conversation state back to database
            conversation_complete = final_state.get("conversation_complete", False)
            if not conversation_complete:
                print(f"💾 Attempting to save conversation state...")
                
                # IMPROVED SAVE LOGIC: Use merge and explicit flags to ensure persistence
                # Fetch a fresh conversation object to avoid session issues
                conversation = self.db.query(Conversation).filter_by(session_id=session_id).first()
                if conversation:
                    # Save messages to database
                    messages_to_save = []
                    for msg in final_state.get("messages", []):
                        if isinstance(msg, HumanMessage):
                            messages_to_save.append({"type": "human", "content": msg.content})
                        elif isinstance(msg, AIMessage):
                            messages_to_save.append({"type": "ai", "content": msg.content})
                    
                    # DEBUG: Log message saving
                    print(f"💾 MESSAGES TO SAVE - Found {len(messages_to_save)} messages")
                    for i, msg in enumerate(messages_to_save):
                        print(f"   [{i}] {msg.get('type', 'unknown')}: {msg.get('content', '')[:50]}...")
                    
                    # Update conversation in database - IMPROVED: Use explicit field assignment
                    final_collected_fields = final_state.get("collected_fields", {})
                    
                    # DEBUG: Log what we're about to save
                    print(f"💾 ABOUT TO SAVE - collected_fields: {final_collected_fields}")
                    
                    # CRITICAL FIX: Use SQLAlchemy's flag_modified to ensure JSON fields are detected as changed
                    from sqlalchemy.orm.attributes import flag_modified
                    
                    conversation.collected_data = dict(final_collected_fields)  # Create new dict to avoid reference issues
                    flag_modified(conversation, "collected_data")  # Explicitly mark as modified
                    
                    # FIX: Prevent nested ai_context by creating a clean context
                    clean_ai_context = final_state.get("ai_context", {})
                    clean_ai_context["conversation_messages"] = messages_to_save
                    
                    # DEBUG: Log the context we're saving
                    print(f"💾 SAVING AI CONTEXT - Keys: {list(clean_ai_context.keys())}")
                    print(f"💾 SAVING AI CONTEXT - Messages: {len(clean_ai_context.get('conversation_messages', []))}")
                    
                    conversation.variables = {
                        "ai_context": clean_ai_context,  # No nesting!
                        "completion_readiness": final_state.get("completion_readiness", 0.0),
                        "total_fields_collected": len(final_collected_fields),
                        "current_field": final_state.get("current_field", "age")
                    }
                    flag_modified(conversation, "variables")  # Explicitly mark as modified
                    
                    # IMPROVED COMMIT STRATEGY: Use merge and explicit flush/commit
                    self.db.merge(conversation)  # Merge changes
                    self.db.flush()  # Flush to database
                    self.db.commit()  # Commit transaction
                    
                    # VERIFICATION: Immediately verify the save worked
                    verification_conversation = self.db.query(Conversation).filter_by(session_id=session_id).first()
                    if verification_conversation:
                        self.db.refresh(verification_conversation)
                        saved_fields = verification_conversation.collected_data or {}
                        saved_variables = verification_conversation.variables or {}
                        saved_messages = saved_variables.get("ai_context", {}).get("conversation_messages", [])
                        
                        print(f"💾 VERIFICATION - saved fields: {list(saved_fields.keys())}")
                        print(f"💾 VERIFICATION - field values: {saved_fields}")
                        print(f"💾 VERIFICATION - saved messages: {len(saved_messages)}")
                        for i, msg in enumerate(saved_messages):
                            print(f"   [{i}] {msg.get('type', 'unknown')}: {msg.get('content', '')[:50]}...")
                    
                    print(f"💾 Conversation state saved: {len(messages_to_save)} messages, {len(final_collected_fields)} fields")
                    print(f"💾 Saved fields: {list(final_collected_fields.keys())}")
                else:
                    print(f"❌ Could not find conversation with session_id: {session_id}")
            else:
                print(f"⏭️ Skipping save because conversation is marked complete")
            
            # Extract AI response
            ai_message = ""
            if final_state.get("messages"):
                for msg in reversed(final_state["messages"]):
                    if isinstance(msg, AIMessage):
                        ai_message = msg.content
                        break
            
            # Calculate fields collected (excluding invalid values)
            collected_fields = final_state.get("collected_fields", {})
            valid_fields_count = len([f for f in collected_fields.values() 
                                    if f not in ["unclear_response", "skipped_by_user", "unclear", "skipped"]])
            
            # FIX PYDANTIC ERROR: Ensure next_field is never None
            next_field = final_state.get("current_field", "age")
            if next_field is None:
                # Determine next field based on collected data
                oldcarts_fields = ["age", "biological_sex", "primary_complaint", "onset", "location", 
                                 "duration", "character", "aggravating_factors", "relieving_factors", 
                                 "timing", "severity", "radiation", "progression", "related_symptoms", "treatment_attempted"]
                
                for field in oldcarts_fields:
                    if field not in collected_fields or collected_fields[field] in ["unclear_response", "skipped_by_user", "unclear", "skipped"]:
                        next_field = field
                        break
                else:
                    next_field = "completion"  # All fields collected
            
            # Return response with all required fields including fields_collected
            return {
                "session_id": final_state["session_id"],
                "message": ai_message,
                "collected_data": collected_fields,
                "conversation_complete": final_state.get("conversation_complete", False),
                "current_section": f"collecting_{next_field}",
                "next_field": next_field,  # Guaranteed to be a string
                "fields_collected": valid_fields_count,
                "emergency_level": final_state.get("emergency_level", EmergencyLevel.NONE.value),
                "completion_readiness": final_state.get("completion_readiness", 0.0),
                "ai_context": final_state.get("ai_context", {})
            }
            
        except Exception as e:
            print(f"❌ Error in dynamic AI processing: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "session_id": session_id or "",
                "message": "I apologize, but I'm having technical difficulties. Please try again.",
                "collected_data": {},
                "conversation_complete": False,
                "current_section": "error",
                "next_field": "age",
                "fields_collected": 0,
                "emergency_level": EmergencyLevel.NONE.value,
                "completion_readiness": 0.0,
                "ai_context": {},
                "error": str(e)
            }
