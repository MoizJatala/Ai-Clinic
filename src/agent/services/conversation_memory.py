"""
🧠 Conversation Memory Service

Manages conversation memory, context, and prevents duplicate questions.
Ensures continuity and intelligent question progression.
"""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import json
import hashlib

from ..config.models import Conversation, Message, QuestionTracking
from ..config.database import get_db


class ConversationMemory:
    """Manages conversation memory and context."""
    
    def __init__(self, db: Session):
        self.db = db
        self.conversation_cache = {}  # In-memory cache for active conversations
    
    def get_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """Get complete conversation context including history and asked questions."""
        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        # Get all messages in chronological order
        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp).all()
        
        # Get all asked questions
        asked_questions = self.db.query(QuestionTracking).filter(
            QuestionTracking.conversation_id == conversation.id
        ).all()
        
        # Build conversation history
        conversation_history = []
        for msg in messages:
            conversation_history.append({
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "phase": msg.phase,
                "medical_category": msg.medical_category
            })
        
        # Build asked questions map
        asked_questions_map = {}
        question_attempts = {}
        for q in asked_questions:
            question_hash = self._hash_question_intent(q.question_text)
            asked_questions_map[question_hash] = {
                "question_id": q.question_id,
                "question_text": q.question_text,
                "category": q.question_category,
                "status": q.status,
                "attempt_count": q.attempt_count,
                "last_asked": q.created_at.isoformat(),
                "response_received": q.response_received,
                "response_clarity": q.response_clarity
            }
            question_attempts[q.question_category] = question_attempts.get(q.question_category, 0) + q.attempt_count
        
        # Get collected data
        collected_data = conversation.variables or {}
        
        # Analyze what information is missing
        missing_info = self._analyze_missing_information(collected_data, asked_questions_map)
        
        context = {
            "session_id": session_id,
            "conversation_id": conversation.id,
            "user_id": conversation.user_id,
            "status": conversation.status,
            "current_phase": conversation.current_phase,
            "emergency_level": conversation.emergency_level,
            
            # Conversation memory
            "conversation_history": conversation_history,
            "message_count": len(conversation_history),
            "asked_questions": asked_questions_map,
            "question_attempts": question_attempts,
            
            # Data context
            "collected_data": collected_data,
            "data_completeness": self._calculate_data_completeness(collected_data),
            "missing_information": missing_info,
            
            # Conversation flow
            "last_user_message": self._get_last_user_message(conversation_history),
            "last_ai_message": self._get_last_ai_message(conversation_history),
            "conversation_tone": self._analyze_conversation_tone(conversation_history),
            
            # Memory metadata
            "context_retrieved_at": datetime.now().isoformat(),
            "cache_key": f"conv_{session_id}_{len(conversation_history)}"
        }
        
        # Cache the context
        self.conversation_cache[session_id] = context
        
        return context
    
    def add_message_to_memory(self, session_id: str, role: str, content: str, 
                             phase: str = None, medical_category: str = None) -> bool:
        """Add a message to conversation memory."""
        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            return False
        
        # Create message record
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            timestamp=datetime.now(),
            phase=phase or conversation.current_phase,
            medical_category=medical_category
        )
        
        self.db.add(message)
        
        # Update conversation last activity
        conversation.last_activity = datetime.now()
        
        self.db.commit()
        
        # Invalidate cache
        if session_id in self.conversation_cache:
            del self.conversation_cache[session_id]
        
        return True
    
    def track_question_asked(self, session_id: str, question_text: str, 
                           category: str, question_id: str = None) -> Dict[str, Any]:
        """Track that a question has been asked to prevent duplicates."""
        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        question_hash = self._hash_question_intent(question_text)
        
        # Check if similar question already asked
        existing_question = self.db.query(QuestionTracking).filter(
            QuestionTracking.conversation_id == conversation.id,
            QuestionTracking.question_hash == question_hash
        ).first()
        
        if existing_question:
            # Update attempt count
            existing_question.attempt_count += 1
            existing_question.last_asked_at = datetime.now()
            self.db.commit()
            
            return {
                "already_asked": True,
                "question_id": existing_question.question_id,
                "attempt_count": existing_question.attempt_count,
                "should_rephrase": existing_question.attempt_count > 1,
                "alternative_needed": existing_question.attempt_count > 2
            }
        
        # Create new question tracking
        question_track = QuestionTracking(
            conversation_id=conversation.id,
            question_id=question_id or f"q_{category}_{datetime.now().strftime('%H%M%S')}",
            question_text=question_text,
            question_hash=question_hash,
            question_category=category,
            status="asked",
            attempt_count=1,
            created_at=datetime.now(),
            last_asked_at=datetime.now()
        )
        
        self.db.add(question_track)
        self.db.commit()
        
        return {
            "already_asked": False,
            "question_id": question_track.question_id,
            "attempt_count": 1,
            "tracked": True
        }
    
    def mark_question_answered(self, session_id: str, question_id: str, 
                              user_response: str, clarity: str = "clear") -> bool:
        """Mark a question as answered with response quality."""
        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).first()
        
        if not conversation:
            return False
        
        question_track = self.db.query(QuestionTracking).filter(
            QuestionTracking.conversation_id == conversation.id,
            QuestionTracking.question_id == question_id
        ).first()
        
        if question_track:
            question_track.status = "answered"
            question_track.response_received = True
            question_track.user_response = user_response
            question_track.response_clarity = clarity
            question_track.answered_at = datetime.now()
            
            self.db.commit()
            return True
        
        return False
    
    def get_alternative_question_style(self, category: str, attempt_count: int, 
                                     collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate alternative question styles when previous attempts failed."""
        
        # Define alternative questioning strategies
        strategies = {
            1: "direct",      # First attempt - direct question
            2: "example",     # Second attempt - with examples
            3: "choice",      # Third attempt - multiple choice
            4: "story",       # Fourth attempt - story-based
            5: "skip_offer"   # Fifth attempt - offer to skip
        }
        
        strategy = strategies.get(attempt_count, "skip_offer")
        
        # Category-specific alternative questions
        alternative_questions = {
            "onset": {
                "direct": "When did this symptom first start?",
                "example": "When did this begin? For example, was it this morning, yesterday, last week?",
                "choice": "Did this start: A) Today, B) This week, C) This month, or D) Longer ago?",
                "story": "Think back to when you first noticed this. What were you doing when it started?",
                "skip_offer": "If you're not sure exactly when it started, that's okay. We can move on to other important details."
            },
            "location": {
                "direct": "Where exactly do you feel this symptom?",
                "example": "Can you point to where it hurts? For example, is it on the left side, right side, or center?",
                "choice": "Where is the pain located: A) Left side, B) Right side, C) Center, or D) All over?",
                "story": "Imagine you're describing this to a friend - where would you point to show them?",
                "skip_offer": "If the location is hard to describe, we can focus on other aspects of your symptom."
            },
            "character": {
                "direct": "How would you describe the quality of this pain or sensation?",
                "example": "What does it feel like? Is it sharp like a knife, dull like an ache, or throbbing like a heartbeat?",
                "choice": "The sensation feels: A) Sharp/stabbing, B) Dull/aching, C) Throbbing/pulsing, or D) Burning/tingling?",
                "story": "If you had to compare this feeling to something familiar, what would it be like?",
                "skip_offer": "Pain can be hard to describe in words. Let's talk about other aspects that might be easier."
            },
            "severity": {
                "direct": "On a scale of 1 to 10, how severe is this symptom?",
                "example": "How bad is it? 1 would be barely noticeable, 10 would be the worst pain imaginable.",
                "choice": "Would you say it's: A) Mild (1-3), B) Moderate (4-6), C) Severe (7-8), or D) Extreme (9-10)?",
                "story": "How much does this interfere with your daily activities?",
                "skip_offer": "If rating the pain is difficult, can you tell me how it affects your daily life?"
            }
        }
        
        question_data = alternative_questions.get(category, {})
        question_text = question_data.get(strategy, f"Can you tell me more about the {category}?")
        
        return {
            "question_text": question_text,
            "strategy": strategy,
            "attempt_count": attempt_count,
            "category": category,
            "should_offer_skip": attempt_count >= 4,
            "needs_encouragement": attempt_count >= 3,
            "encouragement": "I know these questions can be challenging. You're doing great helping me understand your symptoms."
        }
    
    def should_change_topic(self, session_id: str, category: str) -> Dict[str, Any]:
        """Determine if we should move to a different topic/category."""
        context = self.get_conversation_context(session_id)
        
        if "error" in context:
            return context
        
        question_attempts = context.get("question_attempts", {})
        category_attempts = question_attempts.get(category, 0)
        
        # If we've tried a category too many times, suggest moving on
        if category_attempts >= 5:
            return {
                "should_change": True,
                "reason": "too_many_attempts",
                "suggestion": f"Let's move on from {category} and focus on other important aspects of your symptoms.",
                "next_priority": self._get_next_priority_category(context["collected_data"], question_attempts)
            }
        
        # If we have some data in this category, consider it sufficient
        collected_data = context.get("collected_data", {})
        if self._has_sufficient_data_for_category(category, collected_data):
            return {
                "should_change": True,
                "reason": "sufficient_data",
                "suggestion": f"Great! I have good information about {category}. Let's explore other aspects.",
                "next_priority": self._get_next_priority_category(collected_data, question_attempts)
            }
        
        return {
            "should_change": False,
            "continue_category": category,
            "attempts_remaining": 5 - category_attempts
        }
    
    def _hash_question_intent(self, question_text: str) -> str:
        """Create a hash of question intent to detect similar questions."""
        # Normalize the question to detect similar intents
        normalized = question_text.lower()
        
        # Remove common question words to focus on intent
        remove_words = ["what", "when", "where", "how", "can", "you", "tell", "me", "about", "the", "is", "are", "do", "does"]
        words = [word for word in normalized.split() if word not in remove_words]
        
        # Create hash of remaining meaningful words
        intent_string = " ".join(sorted(words))
        return hashlib.md5(intent_string.encode()).hexdigest()[:8]
    
    def _analyze_missing_information(self, collected_data: Dict[str, Any], 
                                   asked_questions: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze what information is still missing."""
        
        # Define required information categories
        required_categories = {
            "chief_complaint": ["primary_symptom", "what_brings_you_in"],
            "onset": ["when_started", "onset", "how_it_began"],
            "location": ["location", "where_pain", "body_part"],
            "character": ["character", "quality", "type_of_pain"],
            "severity": ["severity", "pain_scale", "intensity"],
            "duration": ["duration", "how_long", "episode_length"],
            "timing": ["timing", "pattern", "frequency"],
            "aggravating": ["aggravating_factors", "makes_worse"],
            "relieving": ["relieving_factors", "makes_better", "treatments_tried"]
        }
        
        missing_categories = []
        partially_complete = []
        
        for category, fields in required_categories.items():
            has_data = any(field in collected_data and collected_data[field] for field in fields)
            
            if not has_data:
                missing_categories.append(category)
            elif len([field for field in fields if field in collected_data and collected_data[field]]) < len(fields) / 2:
                partially_complete.append(category)
        
        return {
            "missing_categories": missing_categories,
            "partially_complete": partially_complete,
            "completion_percentage": ((9 - len(missing_categories)) / 9) * 100,
            "next_priority": missing_categories[0] if missing_categories else None
        }
    
    def _calculate_data_completeness(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall data completeness."""
        total_fields = len(collected_data)
        meaningful_fields = len([v for v in collected_data.values() if v and v != "null" and v != ""])
        
        return {
            "total_fields": total_fields,
            "meaningful_fields": meaningful_fields,
            "completion_percentage": (meaningful_fields / max(total_fields, 1)) * 100 if total_fields > 0 else 0,
            "meets_minimum_threshold": meaningful_fields >= 8
        }
    
    def _get_last_user_message(self, conversation_history: List[Dict]) -> Optional[str]:
        """Get the last user message from conversation history."""
        for msg in reversed(conversation_history):
            if msg["role"] == "user":
                return msg["content"]
        return None
    
    def _get_last_ai_message(self, conversation_history: List[Dict]) -> Optional[str]:
        """Get the last AI message from conversation history."""
        for msg in reversed(conversation_history):
            if msg["role"] == "assistant":
                return msg["content"]
        return None
    
    def _analyze_conversation_tone(self, conversation_history: List[Dict]) -> str:
        """Analyze the overall tone of the conversation."""
        if len(conversation_history) < 4:
            return "initial"
        
        user_messages = [msg["content"].lower() for msg in conversation_history if msg["role"] == "user"]
        
        # Look for indicators of user frustration or confusion
        frustration_indicators = ["don't know", "not sure", "confused", "already told", "repeat"]
        confusion_indicators = ["what do you mean", "don't understand", "unclear"]
        
        frustration_count = sum(1 for msg in user_messages for indicator in frustration_indicators if indicator in msg)
        confusion_count = sum(1 for msg in user_messages for indicator in confusion_indicators if indicator in msg)
        
        if frustration_count >= 2:
            return "frustrated"
        elif confusion_count >= 2:
            return "confused"
        elif len(conversation_history) > 10:
            return "engaged"
        else:
            return "cooperative"
    
    def _get_next_priority_category(self, collected_data: Dict[str, Any], 
                                  question_attempts: Dict[str, int]) -> str:
        """Determine the next priority category to ask about."""
        
        # Priority order for medical information
        priority_order = [
            "chief_complaint", "onset", "severity", "location", 
            "character", "duration", "timing", "aggravating", "relieving"
        ]
        
        for category in priority_order:
            # Skip if we've tried too many times
            if question_attempts.get(category, 0) >= 5:
                continue
            
            # Check if we have sufficient data for this category
            if not self._has_sufficient_data_for_category(category, collected_data):
                return category
        
        return "additional_symptoms"  # Fallback
    
    def _has_sufficient_data_for_category(self, category: str, collected_data: Dict[str, Any]) -> bool:
        """Check if we have sufficient data for a category."""
        
        category_fields = {
            "chief_complaint": ["primary_symptom"],
            "onset": ["when_started", "onset"],
            "location": ["location"],
            "character": ["character"],
            "severity": ["severity"],
            "duration": ["duration"],
            "timing": ["timing", "pattern"],
            "aggravating": ["aggravating_factors"],
            "relieving": ["relieving_factors"]
        }
        
        required_fields = category_fields.get(category, [])
        return any(field in collected_data and collected_data[field] for field in required_fields)
    
    def clear_conversation_cache(self, session_id: str = None):
        """Clear conversation cache."""
        if session_id:
            self.conversation_cache.pop(session_id, None)
        else:
            self.conversation_cache.clear()
    
    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the conversation for context."""
        context = self.get_conversation_context(session_id)
        
        if "error" in context:
            return context
        
        return {
            "session_id": session_id,
            "message_count": context["message_count"],
            "data_completeness": context["data_completeness"],
            "missing_information": context["missing_information"],
            "conversation_tone": context["conversation_tone"],
            "questions_asked": len(context["asked_questions"]),
            "last_user_message": context["last_user_message"],
            "ready_for_completion": context["data_completeness"]["meets_minimum_threshold"]
        } 