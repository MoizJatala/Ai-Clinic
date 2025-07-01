"""
🎭 Enhanced Conversation Service for Dynamic AI Medical Agent

Advanced conversation management with personality adaptation, context awareness,
and intelligent conversation flow optimization.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from ..config.models import Conversation, Message, User
from ..config.database import get_db


class EnhancedConversationService:
    """Enhanced conversation service with AI-powered personality and context management."""
    
    def __init__(self, db: Session, openai_api_key: str):
        self.db = db
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=openai_api_key,
            temperature=0.8  # Higher temperature for more personality
        )
    
    def adapt_conversation_personality(self, session_id: str, user_communication_style: str, 
                                     conversation_history: List[Dict]) -> Dict[str, Any]:
        """Adapt conversation personality based on user's communication style and history."""
        
        personality_prompt = f"""
        Analyze this medical conversation and recommend personality adaptations:
        
        USER COMMUNICATION STYLE: {user_communication_style}
        
        RECENT CONVERSATION HISTORY:
        {json.dumps(conversation_history[-5:], indent=2)}
        
        Recommend personality adaptations in JSON format:
        {{
            "communication_approach": "formal/casual/warm/direct/gentle",
            "question_style": "detailed/concise/exploratory/focused",
            "empathy_level": "high/moderate/professional",
            "pacing": "slow/normal/quick",
            "language_complexity": "simple/moderate/medical",
            "encouragement_frequency": "high/moderate/low",
            "validation_style": "frequent/balanced/minimal",
            "personality_traits": ["caring", "professional", "patient", "thorough"],
            "conversation_energy": "calm/engaged/enthusiastic/serious",
            "adaptation_reasoning": "why these adaptations are recommended"
        }}
        
        Consider:
        - How does the user prefer to communicate?
        - What level of detail do they provide?
        - Do they seem anxious, cooperative, or frustrated?
        - What personality would make them most comfortable?
        """
        
        try:
            response = self.llm.invoke([SystemMessage(content=personality_prompt)])
            
            adaptation_text = response.content.strip()
            if adaptation_text.startswith("```json"):
                adaptation_text = adaptation_text.split("```json")[1].split("```")[0]
            elif adaptation_text.startswith("```"):
                adaptation_text = adaptation_text.split("```")[1].split("```")[0]
            
            personality_adaptation = json.loads(adaptation_text)
            
            # Store adaptation in conversation metadata
            conversation = self.db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()
            
            if conversation:
                if not conversation.variables:
                    conversation.variables = {}
                conversation.variables["personality_adaptation"] = personality_adaptation
                self.db.commit()
            
            print(f"🎭 Personality Adaptation: {personality_adaptation}")
            return personality_adaptation
            
        except Exception as e:
            print(f"Error in personality adaptation: {e}")
            return {
                "communication_approach": "warm",
                "question_style": "balanced",
                "empathy_level": "high",
                "pacing": "normal"
            }
    
    def generate_contextual_follow_up(self, session_id: str, last_response: str, 
                                    collected_data: Dict[str, Any]) -> Optional[str]:
        """Generate intelligent contextual follow-up questions or comments."""
        
        follow_up_prompt = f"""
        Generate a natural, contextual follow-up based on this medical conversation:
        
        PATIENT'S LAST RESPONSE: "{last_response}"
        
        COLLECTED MEDICAL DATA: {json.dumps(collected_data, indent=2)}
        
        Generate a brief, natural follow-up that:
        1. Shows active listening and understanding
        2. Validates their experience if appropriate
        3. Provides gentle encouragement or reassurance
        4. Smoothly transitions to the next question
        5. Feels conversational and caring
        
        Examples of good follow-ups:
        - "That sounds really concerning, and I can understand why you're worried about it."
        - "Thank you for being so detailed - that information is really helpful."
        - "I can hear how much this is affecting your daily life."
        - "It's good that you're paying attention to these patterns."
        
        Generate ONE brief, empathetic follow-up comment (or return empty if not needed):
        """
        
        try:
            response = self.llm.invoke([SystemMessage(content=follow_up_prompt)])
            follow_up = response.content.strip().replace('"', '')
            
            # Only return if it's a meaningful follow-up
            if len(follow_up) > 10 and not follow_up.lower().startswith("empty"):
                print(f"💬 Contextual Follow-up: {follow_up}")
                return follow_up
            
        except Exception as e:
            print(f"Error generating follow-up: {e}")
        
        return None
    
    def assess_conversation_pacing(self, session_id: str, message_count: int, 
                                 conversation_duration_minutes: float) -> Dict[str, Any]:
        """Assess and recommend conversation pacing adjustments."""
        
        pacing_prompt = f"""
        Assess the pacing of this medical conversation:
        
        MESSAGE COUNT: {message_count}
        CONVERSATION DURATION: {conversation_duration_minutes} minutes
        AVERAGE TIME PER MESSAGE: {conversation_duration_minutes / max(message_count, 1):.1f} minutes
        
        Provide pacing assessment in JSON format:
        {{
            "current_pace": "too_slow/appropriate/too_fast",
            "recommended_adjustment": "slow_down/maintain/speed_up",
            "pacing_strategy": "detailed_exploration/balanced_questioning/efficient_collection",
            "time_management": "plenty_of_time/normal_pace/need_to_focus",
            "user_engagement_indicator": "highly_engaged/moderately_engaged/losing_interest",
            "next_question_approach": "take_time/normal_flow/be_concise",
            "reasoning": "explanation of pacing assessment"
        }}
        
        Consider:
        - Is the conversation moving at a comfortable pace?
        - Are we gathering information efficiently?
        - Does the user seem engaged or impatient?
        - Should we adjust our questioning style?
        """
        
        try:
            response = self.llm.invoke([SystemMessage(content=pacing_prompt)])
            
            pacing_text = response.content.strip()
            if pacing_text.startswith("```json"):
                pacing_text = pacing_text.split("```json")[1].split("```")[0]
            elif pacing_text.startswith("```"):
                pacing_text = pacing_text.split("```")[1].split("```")[0]
            
            pacing_assessment = json.loads(pacing_text)
            
            print(f"⏱️ Pacing Assessment: {pacing_assessment}")
            return pacing_assessment
            
        except Exception as e:
            print(f"Error in pacing assessment: {e}")
            return {
                "current_pace": "appropriate",
                "recommended_adjustment": "maintain",
                "pacing_strategy": "balanced_questioning"
            }
    
    def generate_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Generate an intelligent conversation summary with insights."""
        
        # Get conversation data
        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        # Get messages
        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp).all()
        
        conversation_text = []
        for msg in messages:
            role = "Patient" if msg.role == "user" else "Assistant"
            conversation_text.append(f"{role}: {msg.content}")
        
        summary_prompt = f"""
        Generate an intelligent summary of this medical conversation:
        
        CONVERSATION:
        {chr(10).join(conversation_text)}
        
        COLLECTED DATA: {json.dumps(conversation.collected_data or {}, indent=2)}
        
        Generate a comprehensive summary in JSON format:
        {{
            "conversation_overview": "brief overview of the consultation",
            "primary_concerns": ["main", "health", "concerns"],
            "key_symptoms": ["identified", "symptoms"],
            "information_quality": "excellent/good/adequate/limited",
            "patient_communication": "detailed/cooperative/anxious/unclear",
            "conversation_highlights": ["notable", "moments", "or", "insights"],
            "medical_significance": "assessment of medical importance",
            "follow_up_recommendations": ["suggested", "next", "steps"],
            "conversation_effectiveness": "how well the conversation achieved its goals",
            "areas_for_improvement": ["potential", "improvements"],
            "overall_assessment": "comprehensive evaluation"
        }}
        
        Focus on providing valuable insights for healthcare providers and conversation improvement.
        """
        
        try:
            response = self.llm.invoke([SystemMessage(content=summary_prompt)])
            
            summary_text = response.content.strip()
            if summary_text.startswith("```json"):
                summary_text = summary_text.split("```json")[1].split("```")[0]
            elif summary_text.startswith("```"):
                summary_text = summary_text.split("```")[1].split("```")[0]
            
            conversation_summary = json.loads(summary_text)
            
            # Store summary in conversation
            if not conversation.variables:
                conversation.variables = {}
            conversation.variables["ai_conversation_summary"] = conversation_summary
            conversation.variables["summary_generated_at"] = datetime.now().isoformat()
            self.db.commit()
            
            print(f"📋 Conversation Summary Generated")
            return conversation_summary
            
        except Exception as e:
            print(f"Error generating conversation summary: {e}")
            return {"error": f"Failed to generate summary: {str(e)}"}
    
    def suggest_conversation_improvements(self, session_id: str) -> List[Dict[str, Any]]:
        """Suggest improvements for future conversations based on this interaction."""
        
        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            return []
        
        improvement_prompt = f"""
        Analyze this medical conversation and suggest improvements:
        
        CONVERSATION VARIABLES: {json.dumps(conversation.variables or {}, indent=2)}
        COLLECTED DATA: {json.dumps(conversation.collected_data or {}, indent=2)}
        STATUS: {conversation.status}
        EMERGENCY LEVEL: {conversation.emergency_level}
        
        Suggest improvements in JSON format as a list:
        [
            {{
                "improvement_area": "question_phrasing/pacing/empathy/information_gathering",
                "current_issue": "what could be improved",
                "suggested_change": "specific improvement recommendation",
                "expected_benefit": "how this would help",
                "implementation_priority": "high/medium/low"
            }}
        ]
        
        Focus on actionable improvements that would enhance:
        - Patient comfort and engagement
        - Information gathering efficiency
        - Conversation flow and naturalness
        - Emotional support and empathy
        - Medical accuracy and completeness
        """
        
        try:
            response = self.llm.invoke([SystemMessage(content=improvement_prompt)])
            
            improvements_text = response.content.strip()
            if improvements_text.startswith("```json"):
                improvements_text = improvements_text.split("```json")[1].split("```")[0]
            elif improvements_text.startswith("```"):
                improvements_text = improvements_text.split("```")[1].split("```")[0]
            
            improvements = json.loads(improvements_text)
            
            print(f"💡 Conversation Improvements: {len(improvements)} suggestions")
            return improvements
            
        except Exception as e:
            print(f"Error generating improvements: {e}")
            return []
    
    def enhance_question_with_personality(self, base_question: str, personality_adaptation: Dict[str, Any], 
                                        user_emotional_state: str) -> str:
        """Enhance a base question with personality and emotional awareness."""
        
        enhancement_prompt = f"""
        Enhance this medical question with personality and emotional awareness:
        
        BASE QUESTION: "{base_question}"
        
        PERSONALITY ADAPTATION: {json.dumps(personality_adaptation, indent=2)}
        
        USER EMOTIONAL STATE: {user_emotional_state}
        
        Enhance the question to:
        1. Match the recommended communication approach
        2. Adjust for the user's emotional state
        3. Maintain medical accuracy and purpose
        4. Feel more natural and personalized
        5. Show appropriate empathy and understanding
        
        Return only the enhanced question text:
        """
        
        try:
            response = self.llm.invoke([SystemMessage(content=enhancement_prompt)])
            enhanced_question = response.content.strip().replace('"', '')
            
            print(f"✨ Question Enhanced: {base_question[:50]}... → {enhanced_question[:50]}...")
            return enhanced_question
            
        except Exception as e:
            print(f"Error enhancing question: {e}")
            return base_question
    
    def detect_conversation_opportunities(self, session_id: str, latest_message: str) -> List[str]:
        """Detect opportunities to improve the conversation experience."""
        
        opportunity_prompt = f"""
        Detect opportunities to enhance this medical conversation:
        
        LATEST PATIENT MESSAGE: "{latest_message}"
        
        Identify opportunities for:
        - Providing reassurance or validation
        - Offering educational information
        - Showing empathy for their experience
        - Acknowledging their cooperation
        - Addressing potential concerns
        - Building rapport and trust
        
        Return a list of specific opportunities (or empty list if none):
        ["opportunity 1", "opportunity 2", ...]
        
        Examples:
        - "Acknowledge their detailed description"
        - "Validate their concern about the symptom"
        - "Reassure about the information gathering process"
        - "Appreciate their patience with questions"
        """
        
        try:
            response = self.llm.invoke([SystemMessage(content=opportunity_prompt)])
            
            opportunities_text = response.content.strip()
            if opportunities_text.startswith("["):
                opportunities = json.loads(opportunities_text)
                print(f"🎯 Conversation Opportunities: {opportunities}")
                return opportunities
            
        except Exception as e:
            print(f"Error detecting opportunities: {e}")
        
        return []