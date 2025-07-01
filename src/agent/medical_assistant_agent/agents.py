"""
🤖 Agent Functions for Dynamic Vi Agent

Contains all agent-related functions for the multi-agent medical conversation system.
Handles agent execution, context preparation, response processing, and routing logic.
"""

import json
from typing import Any, Dict, List
from datetime import datetime

from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from .states import ViState, AgentStep
from .prompts import AGENT_SYSTEM_PROMPTS

# Fix imports to use absolute imports
try:
    from agent.config.models import EmergencyLevel
except ImportError:
    from ..config.models import EmergencyLevel


class AgentFunctions:
    """Class containing all agent-related functions for the dynamic multi-agent system."""
    
    def __init__(self, llm: ChatOpenAI, db):
        """Initialize agent functions with LLM and database."""
        self.llm = llm
        self.db = db
    
    def run_ai_agent(self, state: ViState) -> ViState:
        """Run the appropriate AI agent based on current step."""
        current_agent = state.get("next_step", AgentStep.ORCHESTRATOR.value)
        
        print(f"🤖 Running AI Agent: {current_agent}")
        
        # Get the system prompt for this agent
        system_prompt = AGENT_SYSTEM_PROMPTS.get(current_agent)
        if not system_prompt:
            print(f"❌ No system prompt found for agent: {current_agent}")
            return state
        
        # Prepare context for the agent
        context = self.prepare_agent_context(state, current_agent)
        
        # Create messages for the LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        try:
            # Run the AI agent
            response = self.llm.invoke(messages)
            result = response.content.strip()
            
            print(f"🧠 {current_agent} response: {result[:100]}...")
            
            # Process the agent's response
            state = self.process_agent_response(state, current_agent, result)
            
        except Exception as e:
            print(f"❌ Error in {current_agent}: {e}")
            # Fallback handling
            state = self.handle_agent_error(state, current_agent, str(e))
        
        return state
    
    def prepare_agent_context(self, state: ViState, agent: str) -> Dict[str, Any]:
        """Prepare context for each AI agent."""
        base_context = {
            "session_id": state.get("session_id", ""),
            "collected_fields": state.get("collected_fields", {}),
            "current_field": state.get("current_field", "age"),
            "conversation_memory": state.get("conversation_memory", {}),
            "retry_count": state.get("retry_count", 0),
            "completion_readiness": state.get("completion_readiness", 0.0)
        }
        
        # Agent-specific context
        if agent == AgentStep.ORCHESTRATOR.value:
            # Determine conversation state more accurately
            messages = state.get("messages", [])
            has_ai_messages = any(isinstance(msg, AIMessage) for msg in messages)
            has_user_messages = any(isinstance(msg, HumanMessage) for msg in messages)
            has_collected_data = bool(state.get("collected_fields", {}))
            last_user_message = self.get_last_user_message(state)
            last_agent_action = state.get("ai_context", {}).get("last_agent_action", "none")
            last_extraction = state.get("ai_context", {}).get("last_extraction")
            
            # Count messages for better state detection
            ai_message_count = len([msg for msg in messages if isinstance(msg, AIMessage)])
            user_message_count = len([msg for msg in messages if isinstance(msg, HumanMessage)])
            
            print(f"🔍 Messages Debug: total={len(messages)}, ai={ai_message_count}, user={user_message_count}")
            for i, msg in enumerate(messages):
                msg_type = "AI" if isinstance(msg, AIMessage) else "USER" if isinstance(msg, HumanMessage) else "OTHER"
                print(f"  [{i}] {msg_type}: {msg.content[:50]}...")
            
            # Determine the actual conversation state
            if not has_ai_messages and not has_user_messages:
                conversation_state = "new_session_needs_greeting"
            elif has_ai_messages and user_message_count > ai_message_count:
                conversation_state = "user_responded_needs_processing"
            elif has_ai_messages and user_message_count == ai_message_count:
                conversation_state = "waiting_for_user_response"
            elif last_agent_action == "greeting_sent" and last_user_message:
                conversation_state = "user_responded_after_greeting"
            else:
                conversation_state = "continuing"
            
            # CRITICAL: Prevent infinite extraction loops
            if last_agent_action == "extraction_complete":
                conversation_state = "extraction_complete_needs_evaluation"
                print(f"🛡️ LOOP PREVENTION: Forcing evaluation after extraction complete")
            
            print(f"🔍 Orchestrator Debug: ai_msgs={ai_message_count}, user_msgs={user_message_count}, last_action={last_agent_action}, state={conversation_state}")
            
            # AUTO-COMPLETION CHECK: If messages >= 50 and completion >= 60%
            total_messages = len(messages)
            completion_readiness = state.get("completion_readiness", 0.0)
            
            if total_messages >= 50 and completion_readiness >= 0.6:
                print(f"🚀 AUTO-COMPLETION TRIGGERED: {total_messages} messages, {completion_readiness:.1f} completion")
                conversation_state = "auto_completion_triggered"
            
            base_context.update({
                "conversation_state": conversation_state,
                "last_user_message": last_user_message,
                "conversation_complete": state.get("conversation_complete", False),
                "has_ai_messages": has_ai_messages,
                "has_user_messages": has_user_messages,
                "has_collected_data": has_collected_data,
                "ai_message_count": ai_message_count,
                "user_message_count": user_message_count,
                "total_messages": len(messages),
                "last_agent_action": last_agent_action,
                "last_extraction": last_extraction,
                "auto_completion_check": {
                    "total_messages": total_messages,
                    "completion_readiness": completion_readiness,
                    "should_auto_complete": total_messages >= 50 and completion_readiness >= 0.6
                }
            })
        
        elif agent == AgentStep.EXTRACTION_AGENT.value:
            # Get the current field we're trying to collect
            current_field = state.get("current_field", "age")
            user_response = self.get_last_user_message(state)
            
            # If we don't have age yet and user provided a number, assume it's age
            collected_fields = state.get("collected_fields", {})
            if not collected_fields.get("age") and user_response.strip().isdigit():
                current_field = "age"
            
            base_context.update({
                "user_response": user_response,
                "target_field": current_field,
                "collected_fields_so_far": collected_fields,
                "fields_still_needed": [f for f in ["age", "biological_sex", "primary_complaint", "onset", "location", "duration", "character", "severity"] if f not in collected_fields]
            })
        
        elif agent == AgentStep.EVALUATION_AGENT.value:
            base_context.update({
                "total_fields_possible": 15,
                "fields_collected": len(state.get("collected_fields", {})),
                "last_extraction_result": state.get("ai_context", {}).get("last_extraction"),
                "auto_completion_check": {
                    "total_messages": len(state.get("messages", [])),
                    "completion_readiness": state.get("completion_readiness", 0.0),
                    "should_auto_complete": len(state.get("messages", [])) >= 50 and state.get("completion_readiness", 0.0) >= 0.6
                }
            })
        
        elif agent == AgentStep.QUESTION_AGENT.value:
            base_context.update({
                "target_field": state.get("current_field", "age"),
                "user_communication_style": state.get("conversation_memory", {}).get("communication_style", "cooperative"),
                "previous_responses": self.get_recent_messages(state, 3)
            })
        
        elif agent == AgentStep.COMPLETION_AGENT.value:
            auto_completion_reason = state.get("ai_context", {}).get("auto_completion_reason")
            collected_fields = state.get("collected_fields", {})
            
            # Organize collected data for better summary generation
            organized_data = {
                "patient_context": {
                    "age": collected_fields.get("age", "Not provided"),
                    "biological_sex": collected_fields.get("biological_sex", "Not provided")
                },
                "chief_complaint": {
                    "primary_complaint": collected_fields.get("primary_complaint", "Not provided"),
                    "onset": collected_fields.get("onset", "Not provided"),
                    "location": collected_fields.get("location", "Not provided")
                },
                "symptom_details": {
                    "character": collected_fields.get("character", "Not provided"),
                    "severity": collected_fields.get("severity", "Not provided"),
                    "duration": collected_fields.get("duration", "Not provided"),
                    "timing": collected_fields.get("timing", "Not provided")
                },
                "modifying_factors": {
                    "aggravating_factors": collected_fields.get("aggravating_factors", "Not provided"),
                    "relieving_factors": collected_fields.get("relieving_factors", "Not provided")
                },
                "additional_information": {
                    "radiation": collected_fields.get("radiation", "Not provided"),
                    "progression": collected_fields.get("progression", "Not provided"),
                    "related_symptoms": collected_fields.get("related_symptoms", "Not provided"),
                    "treatment_attempted": collected_fields.get("treatment_attempted", "Not provided")
                }
            }
            
            # Calculate data completeness for context
            total_possible_fields = 14  # Based on OLDCARTS structure
            filled_fields = len([v for v in collected_fields.values() if v and v not in ["Not provided", "unclear_response", "skipped_by_user"]])
            completion_percentage = (filled_fields / total_possible_fields) * 100
            
            base_context.update({
                "is_auto_completion": bool(auto_completion_reason),
                "auto_completion_reason": auto_completion_reason,
                "total_messages": len(state.get("messages", [])),
                "completion_type": "auto" if auto_completion_reason else "natural",
                "organized_data": organized_data,
                "raw_collected_fields": collected_fields,
                "data_completeness": {
                    "filled_fields": filled_fields,
                    "total_possible": total_possible_fields,
                    "percentage": round(completion_percentage, 1),
                    "completion_readiness": state.get("completion_readiness", 0.0)
                },
                "conversation_stats": {
                    "total_messages": len(state.get("messages", [])),
                    "user_messages": len([m for m in state.get("messages", []) if isinstance(m, HumanMessage)]),
                    "ai_messages": len([m for m in state.get("messages", []) if isinstance(m, AIMessage)])
                }
            })
        
        return base_context
    
    def process_agent_response(self, state: ViState, agent: str, response: str) -> ViState:
        """Process the response from each AI agent."""
        
        if agent == AgentStep.ORCHESTRATOR.value:
            try:
                # Parse orchestrator decision
                if response.startswith("```json"):
                    response = response.split("```json")[1].split("```")[0]
                
                decision = json.loads(response)
                # Fix agent name mapping - normalize to lowercase values
                next_agent = decision.get("next_agent", "greeting_agent")
                
                # Normalize agent names to match graph node names
                if next_agent in ["GREETING_AGENT", "greeting_agent"]:
                    next_agent = AgentStep.GREETING_AGENT.value
                elif next_agent in ["EXTRACTION_AGENT", "extraction_agent"]:
                    next_agent = AgentStep.EXTRACTION_AGENT.value
                elif next_agent in ["EVALUATION_AGENT", "evaluation_agent"]:
                    next_agent = AgentStep.EVALUATION_AGENT.value
                elif next_agent in ["QUESTION_AGENT", "question_agent"]:
                    next_agent = AgentStep.QUESTION_AGENT.value
                elif next_agent in ["COMPLETION_AGENT", "completion_agent"]:
                    next_agent = AgentStep.COMPLETION_AGENT.value
                elif next_agent in ["EMERGENCY_AGENT", "emergency_agent"]:
                    next_agent = AgentStep.EMERGENCY_AGENT.value
                elif next_agent in ["END", "end"]:
                    next_agent = "END"
                else:
                    # Default fallback
                    next_agent = AgentStep.GREETING_AGENT.value
                
                state["next_step"] = next_agent
                state["current_field"] = decision.get("priority_field", state.get("current_field", "age"))
                
                # Update AI context
                if "ai_context" not in state:
                    state["ai_context"] = {}
                state["ai_context"]["orchestrator_reasoning"] = decision.get("reasoning", "")
                state["ai_context"]["context_update"] = decision.get("context_update", {})
                
                print(f"🎯 Orchestrator Decision: {state['next_step']} → {state['current_field']}")
                
            except Exception as e:
                print(f"❌ Error parsing orchestrator response: {e}")
                state["next_step"] = AgentStep.GREETING_AGENT.value
        
        elif agent == AgentStep.GREETING_AGENT.value:
            # Add greeting message to conversation
            state["messages"].append(AIMessage(content=response))
            # Greeting agent ends the turn - user will respond and trigger new orchestrator decision
            state["ai_context"]["last_agent_action"] = "greeting_sent"
            print(f"👋 Greeting generated: {response[:50]}...")
        
        elif agent == AgentStep.EXTRACTION_AGENT.value:
            try:
                # Parse extraction results
                if response.startswith("```json"):
                    response = response.split("```json")[1].split("```")[0]
                
                extraction = json.loads(response)
                target_field = extraction.get("target_field")
                extracted_value = extraction.get("extracted_value")
                
                # Update collected fields
                if extracted_value not in ["unclear_response", "skipped_by_user"]:
                    state["collected_fields"][target_field] = extracted_value
                    state["retry_count"] = 0
                    print(f"📊 Extraction SUCCESS: {target_field} = {extracted_value}")
                else:
                    state["retry_count"] = state.get("retry_count", 0) + 1
                    print(f"📊 Extraction UNCLEAR/SKIPPED: {target_field} = {extracted_value}")
                
                # Store additional data if found
                additional_data = extraction.get("additional_data", {})
                for field, value in additional_data.items():
                    if value and field not in state["collected_fields"]:
                        state["collected_fields"][field] = value
                        print(f"📊 Additional data found: {field} = {value}")
                        
                        # Special logging for severity
                        if field == "severity":
                            print(f"🎯 SEVERITY DEBUG: Captured severity '{value}' from user input")
                
                # Special debugging for severity extraction
                user_message = self.get_last_user_message(state)
                severity_keywords = ["severe", "mild", "moderate", "excruciating", "unbearable", "pain level", "scale", "out of 10", "/10"]
                if any(keyword in user_message.lower() for keyword in severity_keywords):
                    has_severity = "severity" in state["collected_fields"]
                    print(f"🎯 SEVERITY DEBUG: User message contains severity keywords, captured: {has_severity}")
                    if not has_severity:
                        print(f"⚠️ SEVERITY WARNING: Keywords detected but severity not captured from: '{user_message}'")
                
                # Update AI context
                state["ai_context"]["last_extraction"] = extraction
                state["ai_context"]["last_agent_action"] = "extraction_complete"
                state["next_step"] = AgentStep.ORCHESTRATOR.value
                
                print(f"📊 Extraction: {target_field} = {extracted_value}")
                
            except Exception as e:
                print(f"❌ Error parsing extraction response: {e}")
                state["ai_context"]["last_agent_action"] = "extraction_error"
                state["next_step"] = AgentStep.ORCHESTRATOR.value
        
        elif agent == AgentStep.EVALUATION_AGENT.value:
            try:
                # Parse evaluation results
                if response.startswith("```json"):
                    response = response.split("```json")[1].split("```")[0]
                
                evaluation = json.loads(response)
                state["completion_readiness"] = evaluation.get("completion_readiness", 0.0)
                state["current_field"] = evaluation.get("next_field_to_collect", "age")
                state["conversation_complete"] = evaluation.get("should_complete", False)
                
                # AUTO-COMPLETION CHECK: Override evaluation if thresholds met
                total_messages = len(state.get("messages", []))
                completion_readiness = state.get("completion_readiness", 0.0)
                
                if total_messages >= 50 and completion_readiness >= 0.6:
                    print(f"🚀 EVALUATION AUTO-COMPLETION: {total_messages} messages, {completion_readiness:.1f} completion - FORCING COMPLETION")
                    state["conversation_complete"] = True
                    evaluation["should_complete"] = True
                    state["ai_context"]["auto_completion_reason"] = f"Reached {total_messages} messages with {completion_readiness:.1f} completion"
                
                # Handle emergency detection
                if evaluation.get("emergency_detected", False):
                    emergency_level = evaluation.get("emergency_level", "MODERATE").upper()
                    state["emergency_level"] = emergency_level
                    state["next_step"] = AgentStep.EMERGENCY_AGENT.value
                    state["ai_context"]["last_agent_action"] = "emergency_detected"
                elif state["conversation_complete"]:
                    state["next_step"] = AgentStep.COMPLETION_AGENT.value
                    state["ai_context"]["last_agent_action"] = "ready_for_completion"
                else:
                    # Evaluation complete, need to ask next question
                    state["next_step"] = AgentStep.QUESTION_AGENT.value
                    state["ai_context"]["last_agent_action"] = "evaluation_complete_need_question"
                
                # Update AI context
                state["ai_context"]["evaluation"] = evaluation
                
                print(f"📈 Evaluation: {state['completion_readiness']:.1f} readiness, next={state['current_field']} → {state['next_step']}")
                
            except Exception as e:
                print(f"❌ Error parsing evaluation response: {e}")
                state["ai_context"]["last_agent_action"] = "evaluation_error"
                state["next_step"] = AgentStep.ORCHESTRATOR.value
        
        elif agent == AgentStep.QUESTION_AGENT.value:
            # Add question to conversation
            state["messages"].append(AIMessage(content=response))
            state["ai_context"]["last_agent_action"] = "question_asked"
            state["next_step"] = AgentStep.ORCHESTRATOR.value
            print(f"❓ Question generated: {response[:50]}...")
        
        elif agent == AgentStep.COMPLETION_AGENT.value:
            # Add completion message and finalize
            state["messages"].append(AIMessage(content=response))
            state["conversation_complete"] = True
            
            # Log completion type
            auto_completion_reason = state.get("ai_context", {}).get("auto_completion_reason")
            if auto_completion_reason:
                print(f"✅ AUTO-COMPLETION: {auto_completion_reason}")
            else:
                print(f"✅ NATURAL COMPLETION: User interaction complete")
            
            print(f"✅ Completion: {response[:50]}...")
        
        elif agent == AgentStep.EMERGENCY_AGENT.value:
            # Add emergency message and finalize
            state["messages"].append(AIMessage(content=response))
            state["conversation_complete"] = True
            print(f"🚨 Emergency: {response[:50]}...")
        
        return state
    
    def route_to_agent(self, state: ViState) -> str:
        """Route to appropriate agent based on conversation state."""
        next_step = state.get("next_step", AgentStep.ORCHESTRATOR.value)
        last_agent_action = state.get("ai_context", {}).get("last_agent_action", "none")
        
        # Count messages
        messages = state.get("messages", [])
        ai_message_count = len([msg for msg in messages if isinstance(msg, AIMessage)])
        user_message_count = len([msg for msg in messages if isinstance(msg, HumanMessage)])
        
        print(f"🔍 Messages Debug: total={len(messages)}, ai={ai_message_count}, user={user_message_count}")
        for i, msg in enumerate(messages):
            msg_type = "AI" if isinstance(msg, AIMessage) else "USER"
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"  [{i}] {msg_type}: {content_preview}")
        
        print(f"🔍 Orchestrator Debug: ai_msgs={ai_message_count}, user_msgs={user_message_count}, last_action={last_agent_action}, state={next_step}")
        
        # Allow initial greeting even with no messages
        if ai_message_count == 0 and user_message_count == 0 and next_step == AgentStep.GREETING_AGENT.value:
            print(f"🎯 INITIAL GREETING: Allowing greeting agent to run")
            return next_step
        
        # FIXED LOGIC: Allow processing when user has responded and we need to extract/process
        # Only force END if we've already processed the user's latest message
        if ai_message_count > user_message_count:
            print(f"🛑 FORCED END: ai_msgs={ai_message_count} > user_msgs={user_message_count} (already processed)")
            return "END"
        
        # Allow extraction and evaluation agents to run even when message counts are equal
        # because they need to process the user's response
        if next_step in [AgentStep.EXTRACTION_AGENT.value, AgentStep.EVALUATION_AGENT.value]:
            print(f"🎯 ALLOWING PROCESSING: {next_step} can run to process user response")
            return next_step
        
        # If we just asked a question, we should wait for response
        if last_agent_action == "question_asked" and ai_message_count >= user_message_count:
            print(f"🛑 FORCED END: last_agent_action={last_agent_action}")
            return "END"
        
        return next_step
    
    def route_from_evaluation(self, state: ViState) -> str:
        """Route from evaluation agent based on its decision."""
        next_step = state.get("next_step", AgentStep.ORCHESTRATOR.value)
        
        # Check for completion
        if state.get("conversation_complete", False):
            return "END"
        
        return next_step
    
    def get_last_user_message(self, state: ViState) -> str:
        """Get the last user message from the conversation."""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                return msg.content
        return ""
    
    def get_recent_messages(self, state: ViState, count: int) -> List[Dict[str, str]]:
        """Get recent messages for context."""
        messages = []
        for msg in state.get("messages", [])[-count:]:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            messages.append({"role": role, "content": msg.content})
        return messages
    
    def handle_agent_error(self, state: ViState, agent: str, error: str) -> ViState:
        """Handle errors in AI agents gracefully."""
        print(f"🔧 Handling error in {agent}: {error}")
        
        # Default fallback actions
        if agent == AgentStep.ORCHESTRATOR.value:
            state["next_step"] = AgentStep.GREETING_AGENT.value
        elif agent == AgentStep.GREETING_AGENT.value:
            state["messages"].append(AIMessage(content="Hello! I'm Vi, your virtual health assistant. How can I help you today?"))
            state["next_step"] = AgentStep.ORCHESTRATOR.value
        else:
            state["next_step"] = AgentStep.ORCHESTRATOR.value
        
        return state
