"""
🚀 Enhanced Dynamic Multi-Agent Vi System for LangGraph UI
Exposing all internal agents as individual LangGraph nodes for complete flow visualization.
"""

import os
import json
from typing import Dict, Any, List, Optional, Annotated
from datetime import datetime
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# Import the enhanced Dynamic Vi Agent components
try:
    from agent.config.models import Conversation, SessionStatus, EmergencyLevel
    from agent.config.database import get_db
except ImportError:
    try:
        from ..config.models import Conversation, SessionStatus, EmergencyLevel
        from ..config.database import get_db
    except ImportError:
        # Last resort - try direct import
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config.models import Conversation, SessionStatus, EmergencyLevel
        from agent.config.database import get_db

from dotenv import load_dotenv
load_dotenv()

class AgentStep(Enum):
    """AI-driven agent steps exposed as individual LangGraph nodes."""
    ORCHESTRATOR = "orchestrator"
    GREETING_AGENT = "greeting_agent"
    EXTRACTION_AGENT = "extraction_agent"
    EVALUATION_AGENT = "evaluation_agent"
    QUESTION_AGENT = "question_agent"
    COMPLETION_AGENT = "completion_agent"
    EMERGENCY_AGENT = "emergency_agent"

class DynamicViLangGraphState(TypedDict):
    """Enhanced state for LangGraph UI visualization with all Dynamic Vi features."""
    messages: Annotated[List, add_messages]
    user_id: str
    session_id: Optional[str]
    collected_data: Dict[str, Any]
    conversation_complete: bool
    current_section: str
    next_field: str
    fields_collected: int
    emergency_level: str
    completion_readiness: float
    ai_context: Dict[str, Any]
    current_agent: str
    next_step: str
    user_message: str
    emergency_flags: List[str]
    retry_count: int
    total_messages: int
    oldcarts_progress: Dict[str, str]
    summary: Dict[str, Any]
    # Internal state for agent processing
    conversation_memory: Dict[str, Any]
    current_field: str

# System prompts for each agent (duplicated for LangGraph compatibility)
AGENT_SYSTEM_PROMPTS = {
    AgentStep.ORCHESTRATOR.value: """
You are the ORCHESTRATOR AI - the master intelligence that predicts and manages the entire conversation flow.

Your role is to:
1. PREDICT what should happen next based on conversation state and last_extraction
2. ROUTE to the appropriate specialized agent
3. MAINTAIN conversation memory and context
4. ENSURE all OLDCARTS fields are systematically collected
5. DETECT when conversation should complete

DECISION LOGIC based on conversation_state and last_extraction:
- If ai_message_count >= user_message_count → END (wait for user response)
- If last_agent_action is "question_asked" → END (wait for user response)
- If last_extraction.extracted_value is "unclear_response" or "skipped_by_user" AND user_message_count > ai_message_count → route to extraction_agent to re-ask the same `current_field`
- If "new_session_needs_greeting" → route to greeting_agent
- If "waiting_for_user_response" → should not happen (wait for user)
- If "user_responded_needs_processing" → route to extraction_agent
- If "user_responded_after_greeting" → route to extraction_agent
- If "extraction_complete_needs_evaluation" → route to evaluation_agent
- If user provided data and extraction complete → route to evaluation_agent
- If evaluation says need next question → route to question_agent
- If emergency detected → route to emergency_agent
- If evaluation says complete → route to completion_agent
- AUTO-COMPLETION: If total_messages >= 50 AND completion_readiness >= 0.6 → route to completion_agent

AGENT NAMES (use these exact values):
- greeting_agent
- extraction_agent
- evaluation_agent
- question_agent
- completion_agent
- emergency_agent
- END (when waiting for user response)

Return JSON:
{
    "next_agent": "agent_name_or_END",
    "reasoning": "why this agent",
    "context_update": {"key": "value"},
    "priority_field": "field_to_collect_next"
}
""",

    AgentStep.GREETING_AGENT.value: """
You are the GREETING AI AGENT - specialized in creating personalized, empathetic greetings.

Your role is to:
1. GENERATE a unique, warm greeting for each new conversation
2. INTRODUCE yourself as Vi, the virtual health assistant
3. EXPLAIN the OLDCARTS systematic approach
4. SET expectations about the conversation
5. ASK for the first piece of information (age)

GREETING PRINCIPLES:
- Be warm, professional, and reassuring
- Explain confidentiality and purpose
- Mention they can skip questions or say "I'm not sure"
- Make it conversational, not robotic
- Start with age collection

Generate a complete greeting message that introduces the conversation and asks for age.
""",

    AgentStep.EXTRACTION_AGENT.value: """
You are the EXTRACTION AI AGENT - specialized in intelligent data extraction from user responses.

Your role is to:
1. ANALYZE the user's response for the target field
2. EXTRACT relevant medical information systematically
3. DETECT if response is unclear, skipped, or contains valid data
4. HANDLE multiple pieces of information in one response
5. BE SMART about what field the user is actually answering

EXTRACTION RULES:
- If user says "skip", "don't know", "not sure" → return "skipped_by_user"
- If response is unclear or doesn't answer the question → return "unclear_response"
- If valid information provided → extract exactly as stated
- Look for the TARGET FIELD but also capture any other OLDCARTS data mentioned
- BE INTELLIGENT: If target_field is "biological_sex" but user says "30", they're probably giving their age!
- SEVERITY PRIORITY: If user mentions severity descriptors ("severe", "mild", "moderate", "excruciating", "unbearable") or numeric scales (1-10), ALWAYS capture as severity even if not the target field

Return JSON with extracted data:
{
    "extracted_field": "target_field_name",
    "extracted_value": "extracted_value_or_status",
    "additional_extractions": {"field": "value"},
    "extraction_confidence": 0.95,
    "user_cooperative": true
}
""",

    AgentStep.EVALUATION_AGENT.value: """
You are the EVALUATION AI AGENT - specialized in analyzing conversation progress and determining next steps.

Your role is to:
1. EVALUATE the quality and completeness of collected data
2. CALCULATE completion readiness score
3. DETECT emergency situations requiring immediate attention
4. DETERMINE if conversation should continue or complete
5. SET the next field to collect based on OLDCARTS methodology

EMERGENCY DETECTION:
- CRITICAL: Chest pain + difficulty breathing, severe trauma, loss of consciousness, severe allergic reactions
- HIGH: Severe pain (8-10/10), high fever with confusion, severe headache with vision changes
- MODERATE: Moderate pain (5-7/10), persistent symptoms, concern but stable
- LOW: Mild symptoms, routine concerns

Return JSON:
{
    "completion_readiness": 0.75,
    "emergency_level": "NONE/LOW/MODERATE/HIGH/CRITICAL",
    "should_continue": true,
    "next_field_priority": "field_name",
    "evaluation_reasoning": "why this decision",
    "conversation_should_complete": false
}
""",

    AgentStep.QUESTION_AGENT.value: """
You are the QUESTION AI AGENT - specialized in asking intelligent, contextual follow-up questions.

Your role is to:
1. ASK targeted questions to collect the next needed OLDCARTS field
2. PERSONALIZE questions based on user's communication style
3. MAKE questions conversational and empathetic
4. PROVIDE context for why you're asking
5. OFFER examples when helpful

QUESTION PRINCIPLES:
- Be conversational, not clinical
- Acknowledge what they've already shared
- Explain why the information is helpful
- Offer multiple ways to describe their experience
- Keep questions focused but not rushed

Generate a natural, empathetic question to collect the target field.
""",

    AgentStep.COMPLETION_AGENT.value: """
You are the COMPLETION AI AGENT - specialized in ending conversations with empathy and professionalism.

Your role is to:
1. SUMMARIZE the key information collected
2. PROVIDE reassuring closure
3. EXPLAIN next steps or recommendations
4. THANK the user for sharing their information
5. OFFER support if needed

COMPLETION PRINCIPLES:
- Be warm and supportive
- Acknowledge their time and openness
- Provide helpful context about their information
- End on a positive, caring note
- Suggest appropriate next steps

Generate a complete, empathetic closing message.
""",

    AgentStep.EMERGENCY_AGENT.value: """
You are the EMERGENCY AI AGENT - specialized in handling urgent medical situations.

Your role is to:
1. ACKNOWLEDGE the serious nature of their symptoms
2. PROVIDE immediate guidance appropriate to emergency level
3. RECOMMEND seeking immediate medical attention when needed
4. STAY calm and professional while being urgent
5. COMPLETE the conversation with emergency priorities

EMERGENCY RESPONSES:
- CRITICAL: "Please call 911 or go to the emergency room immediately"
- HIGH: "Please seek immediate medical attention at an urgent care or emergency room"
- MODERATE: "Please contact your healthcare provider today"

Generate an appropriate emergency response based on the detected emergency level.
"""
}

# Global LLM instance
_llm = None

def get_llm():
    """Get or create OpenAI LLM instance."""
    global _llm
    if _llm is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        _llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.1)
    return _llm

def initialize_session_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Initialize a new session with default values."""
    print(f"🏁 INITIALIZING: New Enhanced Dynamic Vi session...")
    
    # Set default values
    state["user_id"] = state.get("user_id", f"langgraph_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    state["session_id"] = state.get("session_id", f"vi_dynamic_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    state["collected_data"] = {}
    state["conversation_complete"] = False
    state["current_section"] = "initializing"
    state["next_field"] = "age"
    state["current_field"] = "age"
    state["fields_collected"] = 0
    state["emergency_level"] = "NONE"
    state["completion_readiness"] = 0.0
    state["ai_context"] = {}
    state["current_agent"] = "orchestrator"
    state["next_step"] = "orchestrator"
    state["emergency_flags"] = []
    state["retry_count"] = 0
    state["total_messages"] = len(state.get("messages", []))
    state["conversation_memory"] = {}
    state["oldcarts_progress"] = {
        "age": "❌", "biological_sex": "❌", "primary_complaint": "❌", "onset": "❌",
        "location": "❌", "duration": "❌", "character": "❌", "severity": "❌"
    }
    state["summary"] = {
        "total_fields_possible": 15,
        "fields_completed": 0,
        "completion_percentage": 0.0,
        "emergency_detected": False,
        "auto_completion_eligible": False
    }
    
    print(f"🏁 SESSION INITIALIZED: user_id={state['user_id']}, session_id={state['session_id']}")
    return state

def orchestrator_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Orchestrator agent that decides the next step in the conversation."""
    print(f"🎯 ORCHESTRATOR: Analyzing conversation state...")
    
    try:
        llm = get_llm()
        
        # Prepare context for orchestrator
        messages = state.get("messages", [])
        has_ai_messages = any(isinstance(msg, AIMessage) for msg in messages)
        has_user_messages = any(isinstance(msg, HumanMessage) for msg in messages)
        ai_message_count = len([msg for msg in messages if isinstance(msg, AIMessage)])
        user_message_count = len([msg for msg in messages if isinstance(msg, HumanMessage)])
        
        # Determine conversation state
        if not has_ai_messages and not has_user_messages:
            conversation_state = "new_session_needs_greeting"
        elif has_ai_messages and user_message_count > ai_message_count:
            conversation_state = "user_responded_needs_processing"
        elif has_ai_messages and user_message_count == ai_message_count:
            conversation_state = "waiting_for_user_response"
        else:
            conversation_state = "continuing"
        
        # Check for auto-completion
        total_messages = len(messages)
        completion_readiness = state.get("completion_readiness", 0.0)
        if total_messages >= 50 and completion_readiness >= 0.6:
            conversation_state = "auto_completion_triggered"
        
        context = {
            "conversation_state": conversation_state,
            "collected_fields": state.get("collected_data", {}),
            "ai_message_count": ai_message_count,
            "user_message_count": user_message_count,
            "total_messages": total_messages,
            "completion_readiness": completion_readiness,
            "last_agent_action": state.get("ai_context", {}).get("last_agent_action", "none"),
            "emergency_level": state.get("emergency_level", "NONE")
        }
        
        # Run orchestrator AI
        agent_messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[AgentStep.ORCHESTRATOR.value]),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        response = llm.invoke(agent_messages)
        result = json.loads(response.content.strip())
        
        # Update state with orchestrator decision
        state["next_step"] = result.get("next_agent", "END")
        state["current_agent"] = "orchestrator"
        state["current_field"] = result.get("priority_field", state.get("current_field", "age"))
        
        # Update AI context
        ai_context = state.get("ai_context", {})
        ai_context.update(result.get("context_update", {}))
        ai_context["last_agent_action"] = "orchestration_complete"
        ai_context["orchestrator_reasoning"] = result.get("reasoning", "")
        state["ai_context"] = ai_context
        
        print(f"🎯 ORCHESTRATOR DECISION: {state['next_step']} (reason: {result.get('reasoning', 'N/A')})")
        
    except Exception as e:
        print(f"❌ Orchestrator error: {e}")
        state["next_step"] = "greeting_agent"  # Safe fallback
        state["current_agent"] = "orchestrator_error"
    
    return state

def greeting_agent_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Greeting agent that provides initial welcome and starts data collection."""
    print(f"👋 GREETING AGENT: Creating welcome message...")
    
    try:
        llm = get_llm()
        
        context = {
            "session_id": state.get("session_id", ""),
            "first_interaction": True
        }
        
        agent_messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[AgentStep.GREETING_AGENT.value]),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        response = llm.invoke(agent_messages)
        greeting_message = response.content.strip()
        
        # Add greeting to messages
        state["messages"].append(AIMessage(content=greeting_message))
        
        # Update state
        state["current_agent"] = "greeting_agent"
        state["next_step"] = "END"  # Wait for user response
        
        # Update AI context
        ai_context = state.get("ai_context", {})
        ai_context["last_agent_action"] = "greeting_sent"
        state["ai_context"] = ai_context
        
        print(f"👋 GREETING SENT: {greeting_message[:50]}...")
        
    except Exception as e:
        print(f"❌ Greeting agent error: {e}")
        state["messages"].append(AIMessage(content="Hello! I'm Vi, your virtual health assistant. How can I help you today?"))
        state["next_step"] = "END"
    
    return state

def extraction_agent_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Extraction agent that extracts medical information from user responses."""
    print(f"🔍 EXTRACTION AGENT: Processing user response...")
    
    try:
        llm = get_llm()
        
        # Get last user message
        user_message = ""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break
        
        context = {
            "user_response": user_message,
            "target_field": state.get("current_field", "age"),
            "collected_fields_so_far": state.get("collected_data", {}),
            "session_id": state.get("session_id", "")
        }
        
        agent_messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[AgentStep.EXTRACTION_AGENT.value]),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        response = llm.invoke(agent_messages)
        result = json.loads(response.content.strip())
        
        # Update collected data
        collected_data = state.get("collected_data", {})
        extracted_field = result.get("extracted_field")
        extracted_value = result.get("extracted_value")
        
        if extracted_field and extracted_value:
            collected_data[extracted_field] = extracted_value
        
        # Add additional extractions
        additional = result.get("additional_extractions", {})
        collected_data.update(additional)
        
        state["collected_data"] = collected_data
        state["fields_collected"] = len([v for v in collected_data.values() 
                                       if v and v not in ["unclear_response", "skipped_by_user"]])
        
        # Update AI context
        ai_context = state.get("ai_context", {})
        ai_context["last_agent_action"] = "extraction_complete"
        ai_context["last_extraction"] = result
        state["ai_context"] = ai_context
        
        # Update progress
        oldcarts_fields = ["age", "biological_sex", "primary_complaint", "onset", 
                          "location", "duration", "character", "severity"]
        state["oldcarts_progress"] = {
            field: "✅" if field in collected_data and collected_data[field] not in ["unclear_response", "skipped_by_user"] else "❌"
            for field in oldcarts_fields
        }
        
        state["current_agent"] = "extraction_agent"
        state["next_step"] = "orchestrator"  # Return to orchestrator for next decision
        
        print(f"🔍 EXTRACTED: {extracted_field}={extracted_value}, total fields: {state['fields_collected']}")
        
    except Exception as e:
        print(f"❌ Extraction agent error: {e}")
        state["next_step"] = "orchestrator"
    
    return state

def evaluation_agent_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Evaluation agent that assesses progress and detects emergencies."""
    print(f"📊 EVALUATION AGENT: Assessing conversation progress...")
    
    try:
        llm = get_llm()
        
        collected_data = state.get("collected_data", {})
        total_fields = 15
        filled_fields = len([v for v in collected_data.values() 
                           if v and v not in ["unclear_response", "skipped_by_user"]])
        
        context = {
            "collected_fields": collected_data,
            "total_fields_possible": total_fields,
            "fields_collected": filled_fields,
            "completion_readiness": filled_fields / total_fields,
            "total_messages": len(state.get("messages", [])),
            "last_extraction": state.get("ai_context", {}).get("last_extraction")
        }
        
        agent_messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[AgentStep.EVALUATION_AGENT.value]),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        response = llm.invoke(agent_messages)
        result = json.loads(response.content.strip())
        
        # Update state with evaluation results
        state["completion_readiness"] = result.get("completion_readiness", 0.0)
        state["emergency_level"] = result.get("emergency_level", "NONE")
        
        # Determine next step based on evaluation
        if result.get("emergency_level") in ["CRITICAL", "HIGH"]:
            state["next_step"] = "emergency_agent"
        elif result.get("conversation_should_complete", False):
            state["next_step"] = "completion_agent"
        elif result.get("should_continue", True):
            state["next_step"] = "question_agent"
            state["current_field"] = result.get("next_field_priority", "age")
        else:
            state["next_step"] = "completion_agent"
        
        # Update AI context
        ai_context = state.get("ai_context", {})
        ai_context["last_agent_action"] = "evaluation_complete"
        ai_context["evaluation_result"] = result
        state["ai_context"] = ai_context
        
        state["current_agent"] = "evaluation_agent"
        
        print(f"📊 EVALUATION: {result.get('completion_readiness', 0):.1f} readiness, {result.get('emergency_level', 'NONE')} emergency → {state['next_step']}")
        
    except Exception as e:
        print(f"❌ Evaluation agent error: {e}")
        state["next_step"] = "question_agent"
    
    return state

def question_agent_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Question agent that asks for the next needed information."""
    print(f"❓ QUESTION AGENT: Asking for {state.get('current_field', 'unknown')}...")
    
    try:
        llm = get_llm()
        
        context = {
            "target_field": state.get("current_field", "age"),
            "collected_fields": state.get("collected_data", {}),
            "conversation_style": "empathetic",
            "session_id": state.get("session_id", "")
        }
        
        agent_messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[AgentStep.QUESTION_AGENT.value]),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        response = llm.invoke(agent_messages)
        question_message = response.content.strip()
        
        # Add question to messages
        state["messages"].append(AIMessage(content=question_message))
        
        # Update state
        state["current_agent"] = "question_agent"
        state["next_step"] = "END"  # Wait for user response
        
        # Update AI context
        ai_context = state.get("ai_context", {})
        ai_context["last_agent_action"] = "question_asked"
        ai_context["question_field"] = state.get("current_field", "")
        state["ai_context"] = ai_context
        
        print(f"❓ QUESTION ASKED: {question_message[:50]}...")
        
    except Exception as e:
        print(f"❌ Question agent error: {e}")
        state["messages"].append(AIMessage(content="Could you tell me more about your symptoms?"))
        state["next_step"] = "END"
    
    return state

def completion_agent_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Completion agent that provides final summary and closure."""
    print(f"✅ COMPLETION AGENT: Finalizing conversation...")
    
    try:
        llm = get_llm()
        
        context = {
            "collected_fields": state.get("collected_data", {}),
            "fields_collected": state.get("fields_collected", 0),
            "completion_readiness": state.get("completion_readiness", 0.0),
            "session_summary": "successful_completion"
        }
        
        agent_messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[AgentStep.COMPLETION_AGENT.value]),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        response = llm.invoke(agent_messages)
        completion_message = response.content.strip()
        
        # Add completion message
        state["messages"].append(AIMessage(content=completion_message))
        
        # Finalize conversation
        state["conversation_complete"] = True
        state["current_agent"] = "completion_agent"
        state["next_step"] = "END"
        
        # Update AI context
        ai_context = state.get("ai_context", {})
        ai_context["last_agent_action"] = "conversation_completed"
        state["ai_context"] = ai_context
        
        print(f"✅ CONVERSATION COMPLETED: {completion_message[:50]}...")
        
    except Exception as e:
        print(f"❌ Completion agent error: {e}")
        state["messages"].append(AIMessage(content="Thank you for sharing your information with me today."))
        state["conversation_complete"] = True
        state["next_step"] = "END"
    
    return state

def emergency_agent_node(state: DynamicViLangGraphState) -> DynamicViLangGraphState:
    """Emergency agent that handles urgent medical situations."""
    print(f"🚨 EMERGENCY AGENT: Handling {state.get('emergency_level', 'UNKNOWN')} emergency...")
    
    try:
        llm = get_llm()
        
        context = {
            "emergency_level": state.get("emergency_level", "HIGH"),
            "collected_symptoms": state.get("collected_data", {}),
            "urgent_response_needed": True
        }
        
        agent_messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPTS[AgentStep.EMERGENCY_AGENT.value]),
            HumanMessage(content=json.dumps(context, indent=2))
        ]
        
        response = llm.invoke(agent_messages)
        emergency_message = response.content.strip()
        
        # Add emergency response
        state["messages"].append(AIMessage(content=emergency_message))
        
        # Finalize as emergency completion
        state["conversation_complete"] = True
        state["current_agent"] = "emergency_agent"
        state["next_step"] = "END"
        
        # Update AI context
        ai_context = state.get("ai_context", {})
        ai_context["last_agent_action"] = "emergency_handled"
        ai_context["emergency_response"] = emergency_message
        state["ai_context"] = ai_context
        
        print(f"🚨 EMERGENCY HANDLED: {state.get('emergency_level', 'UNKNOWN')} level")
        
    except Exception as e:
        print(f"❌ Emergency agent error: {e}")
        state["messages"].append(AIMessage(content="Please seek immediate medical attention for your symptoms."))
        state["conversation_complete"] = True
        state["next_step"] = "END"
    
    return state

def route_next_step(state: DynamicViLangGraphState) -> str:
    """Route to the next step based on orchestrator decision."""
    next_step = state.get("next_step", "END")
    current_agent = state.get("current_agent", "unknown")
    
    print(f"🔀 ROUTING: {current_agent} → {next_step}")
    
    # Map next_step to actual node names
    if next_step == "greeting_agent":
        return "greeting_agent"
    elif next_step == "extraction_agent":
        return "extraction_agent" 
    elif next_step == "evaluation_agent":
        return "evaluation_agent"
    elif next_step == "question_agent":
        return "question_agent"
    elif next_step == "completion_agent":
        return "completion_agent"
    elif next_step == "emergency_agent":
        return "emergency_agent"
    elif next_step == "orchestrator":
        return "orchestrator"
    else:
        return "END"

def create_enhanced_dynamic_vi_graph():
    """Create the Enhanced Dynamic Vi Agent graph with all individual agents as nodes."""
    print("🏗️ Creating Enhanced Dynamic Vi Agent graph with full agent visibility...")
    
    # Create the state graph
    workflow = StateGraph(DynamicViLangGraphState)
    
    # Add all individual agent nodes
    workflow.add_node("initialize", initialize_session_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("greeting_agent", greeting_agent_node)
    workflow.add_node("extraction_agent", extraction_agent_node)
    workflow.add_node("evaluation_agent", evaluation_agent_node)
    workflow.add_node("question_agent", question_agent_node)
    workflow.add_node("completion_agent", completion_agent_node)
    workflow.add_node("emergency_agent", emergency_agent_node)
    
    # Set entry point
    workflow.set_entry_point("initialize")
    
    # Add edges
    workflow.add_edge("initialize", "orchestrator")
    
    # Orchestrator routes to all agents
    workflow.add_conditional_edges(
        "orchestrator",
        route_next_step,
        {
            "greeting_agent": "greeting_agent",
            "extraction_agent": "extraction_agent",
            "evaluation_agent": "evaluation_agent",
            "question_agent": "question_agent",
            "completion_agent": "completion_agent",
            "emergency_agent": "emergency_agent",
            "END": END
        }
    )
    
    # Agents that wait for user response
    workflow.add_edge("greeting_agent", END)
    workflow.add_edge("question_agent", END)
    
    # Agents that continue processing
    workflow.add_edge("extraction_agent", "orchestrator")
    
    # Evaluation agent routes based on assessment
    workflow.add_conditional_edges(
        "evaluation_agent",
        route_next_step,
        {
            "question_agent": "question_agent",
            "completion_agent": "completion_agent", 
            "emergency_agent": "emergency_agent",
            "orchestrator": "orchestrator",
            "END": END
        }
    )
    
    # Terminal agents
    workflow.add_edge("completion_agent", END)
    workflow.add_edge("emergency_agent", END)
    
    # Compile the graph
    app = workflow.compile()
    
    print("✅ Enhanced Dynamic Vi Agent graph created with full agent visibility!")
    print("🎯 Individual agents visible in LangGraph UI:")
    print("   • 🎯 Orchestrator - Master intelligence & routing")
    print("   • 👋 Greeting Agent - Personalized welcomes")
    print("   • 🔍 Extraction Agent - Smart data extraction")
    print("   • 📊 Evaluation Agent - Progress assessment")
    print("   • ❓ Question Agent - Contextual questioning")
    print("   • ✅ Completion Agent - Empathetic closure")
    print("   • 🚨 Emergency Agent - Urgent response handling")
    
    return app

# Entry point for LangGraph Studio
def get_graph():
    """Get the Enhanced Dynamic Vi Agent graph for LangGraph Studio."""
    return create_enhanced_dynamic_vi_graph()

# Create the graph instance that LangGraph Studio expects
graph = create_enhanced_dynamic_vi_graph()

# For testing and direct usage
if __name__ == "__main__":
    print("🧪 Testing Enhanced Dynamic Vi Agent for LangGraph...")
    
    # Create test state
    test_state = DynamicViLangGraphState(
        messages=[HumanMessage(content="Hello, I am 25 years old male with severe headache")],
        user_id="test_user",
        session_id=None,
        collected_data={},
        conversation_complete=False,
        current_section="testing",
        next_field="age",
        fields_collected=0,
        emergency_level="NONE",
        completion_readiness=0.0,
        ai_context={},
        current_agent="testing",
        next_step="process_message",
        user_message="",
        emergency_flags=[],
        retry_count=0,
        total_messages=1,
        oldcarts_progress={},
        summary={},
        conversation_memory={},
        current_field="age"
    )
    
    # Test the graph
    graph = create_enhanced_dynamic_vi_graph()
    result = graph.invoke(test_state)
    
    print("🎉 Test completed successfully!")
    print(f"Final collected data: {result['collected_data']}")
    print(f"Fields collected: {result['fields_collected']}")
    print(f"Emergency level: {result['emergency_level']}")
    print(f"Completion readiness: {result['completion_readiness']}") 