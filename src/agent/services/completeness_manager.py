"""
Comprehensive Data Completeness and Transaction Manager for Vi Medical Assistant.

This service handles:
1. Transaction control - only complete data is stored
2. Data completeness validation
3. Timeout and idle handling
4. Multi-symptom queueing
5. Skip handling and unclear response management
6. Human handoff protocols
7. Session resume logic
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from enum import Enum

# Handle both direct execution and package imports
try:
    from ..config.models import (
        Conversation, QuestionTracking, DataCompletenessCheck, TimeoutEvent,
        SessionStatus, DataCompletenessLevel, QuestionStatus, EmergencyLevel
    )
except ImportError:
    # Direct execution - add parent directory to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from agent.config.models import (
        Conversation, QuestionTracking, DataCompletenessCheck, TimeoutEvent,
        SessionStatus, DataCompletenessLevel, QuestionStatus, EmergencyLevel
    )


class CompletenessThreshold(Enum):
    """Thresholds for data completeness."""
    MINIMUM_FOR_STORAGE = 8  # Minimum fields required to save session
    SUBSTANTIAL_COMPLETION = 15  # Fields needed for substantial completion
    COMPREHENSIVE_COMPLETION = 25  # Fields for comprehensive completion


class CompletenessManager:
    """Manages data completeness, transactions, and session quality."""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Define required fields by category
        self.required_fields = {
            "chief_complaint": [
                "primary_symptom", "when_started", "what_brings_you_in"
            ],
            "symptom_details": [
                "onset", "location", "duration", "character", "severity", 
                "timing", "aggravating_factors", "relieving_factors"
            ],
            "medical_history": [
                "past_medical_history", "current_conditions", "surgeries", "hospitalizations"
            ],
            "medications": [
                "current_medications", "dosages", "over_the_counter", "supplements"
            ],
            "allergies": [
                "drug_allergies", "food_allergies", "environmental_allergies", "reactions"
            ],
            "social_history": [
                "smoking", "alcohol", "drugs", "occupation", "work_exposures"
            ],
            "family_history": [
                "family_medical_conditions", "genetic_history"
            ],
            "review_of_systems": [
                "cardiovascular", "respiratory", "gastrointestinal", "neurological",
                "skin", "genitourinary", "musculoskeletal", "psychiatric"
            ]
        }
        
        # Scoring weights for different categories
        self.category_weights = {
            "chief_complaint": 25,  # Most important
            "symptom_details": 20,
            "medical_history": 15,
            "medications": 10,
            "allergies": 10,
            "social_history": 8,
            "family_history": 7,
            "review_of_systems": 5
        }
    
    def evaluate_data_completeness(self, conversation_id: int, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the completeness of collected medical data."""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        # Get or create completeness check record
        completeness_check = self.db.query(DataCompletenessCheck).filter(
            DataCompletenessCheck.conversation_id == conversation_id
        ).first()
        
        if not completeness_check:
            completeness_check = DataCompletenessCheck(
                conversation_id=conversation_id,
                min_fields_required=CompletenessThreshold.MINIMUM_FOR_STORAGE.value
            )
            self.db.add(completeness_check)
        
        # Evaluate each category
        category_scores = {}
        total_fields_collected = 0
        total_possible_fields = 0
        
        for category, fields in self.required_fields.items():
            collected_in_category = 0
            for field in fields:
                if self._field_has_meaningful_data(collected_data, field):
                    collected_in_category += 1
                    total_fields_collected += 1
                total_possible_fields += 1
            
            category_completion = (collected_in_category / len(fields)) * 100
            category_scores[category] = {
                "collected": collected_in_category,
                "total": len(fields),
                "percentage": category_completion,
                "complete": category_completion >= 70  # 70% threshold for category completion
            }
        
        # Update completeness check record
        completeness_check.chief_complaint_complete = category_scores["chief_complaint"]["complete"]
        completeness_check.symptom_details_complete = category_scores["symptom_details"]["complete"]
        completeness_check.medical_history_complete = category_scores["medical_history"]["complete"]
        completeness_check.medications_complete = category_scores["medications"]["complete"]
        completeness_check.allergies_complete = category_scores["allergies"]["complete"]
        completeness_check.social_history_complete = category_scores["social_history"]["complete"]
        completeness_check.family_history_complete = category_scores["family_history"]["complete"]
        completeness_check.review_of_systems_complete = category_scores["review_of_systems"]["complete"]
        
        completeness_check.min_fields_collected = total_fields_collected
        
        # Calculate weighted completion score
        weighted_score = 0
        for category, score_data in category_scores.items():
            weight = self.category_weights.get(category, 5)
            weighted_score += (score_data["percentage"] / 100) * weight
        
        completion_percentage = (weighted_score / sum(self.category_weights.values())) * 100
        completeness_check.completion_percentage = completion_percentage
        completeness_check.points_earned = int(completion_percentage)
        
        # Determine completeness level and transaction control
        if total_fields_collected >= CompletenessThreshold.COMPREHENSIVE_COMPLETION.value:
            completeness_level = DataCompletenessLevel.COMPREHENSIVE
        elif total_fields_collected >= CompletenessThreshold.SUBSTANTIAL_COMPLETION.value:
            completeness_level = DataCompletenessLevel.SUBSTANTIAL
        elif total_fields_collected >= CompletenessThreshold.MINIMUM_FOR_STORAGE.value:
            completeness_level = DataCompletenessLevel.PARTIAL
        else:
            completeness_level = DataCompletenessLevel.MINIMAL
        
        # Transaction control decisions
        meets_storage_threshold = total_fields_collected >= CompletenessThreshold.MINIMUM_FOR_STORAGE.value
        can_complete_session = total_fields_collected >= CompletenessThreshold.SUBSTANTIAL_COMPLETION.value
        
        completeness_check.meets_storage_threshold = meets_storage_threshold
        completeness_check.can_complete_session = can_complete_session
        completeness_check.last_calculated = datetime.now()
        
        # Update conversation record
        conversation.data_completeness_level = completeness_level.value
        conversation.min_data_threshold_met = meets_storage_threshold
        conversation.can_be_saved = meets_storage_threshold
        conversation.completion_score = completion_percentage
        
        self.db.commit()
        
        return {
            "completeness_level": completeness_level.value,
            "completion_percentage": completion_percentage,
            "total_fields_collected": total_fields_collected,
            "total_possible_fields": total_possible_fields,
            "meets_storage_threshold": meets_storage_threshold,
            "can_complete_session": can_complete_session,
            "category_scores": category_scores,
            "missing_critical_areas": self._identify_missing_critical_areas(category_scores),
            "next_priority_questions": self._get_next_priority_questions(category_scores, collected_data)
        }
    
    def _field_has_meaningful_data(self, collected_data: Dict[str, Any], field: str) -> bool:
        """Check if a field contains meaningful data (not empty, null, or generic)."""
        if field not in collected_data:
            return False
        
        value = collected_data[field]
        
        # Check for empty or null values
        if value is None or value == "" or value == "null":
            return False
        
        # Check for empty lists or dicts
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        
        # Check for generic/meaningless responses
        meaningless_responses = [
            "unknown", "not sure", "maybe", "i don't know", "n/a", "none",
            "no", "yes", "ok", "fine", "normal", "regular"
        ]
        
        if isinstance(value, str) and value.lower().strip() in meaningless_responses:
            return False
        
        return True
    
    def _identify_missing_critical_areas(self, category_scores: Dict[str, Any]) -> List[str]:
        """Identify critical areas that are missing or incomplete."""
        missing_areas = []
        
        # Critical areas that must be completed
        critical_categories = ["chief_complaint", "symptom_details", "medical_history"]
        
        for category in critical_categories:
            if not category_scores[category]["complete"]:
                missing_areas.append(category)
        
        return missing_areas
    
    def _get_next_priority_questions(self, category_scores: Dict[str, Any], collected_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get the next priority questions to ask based on completeness analysis."""
        priority_questions = []
        
        # Prioritize by importance and completion status
        for category in ["chief_complaint", "symptom_details", "medical_history", "medications", "allergies"]:
            if not category_scores[category]["complete"]:
                missing_fields = []
                for field in self.required_fields[category]:
                    if not self._field_has_meaningful_data(collected_data, field):
                        missing_fields.append(field)
                
                if missing_fields:
                    priority_questions.append({
                        "category": category,
                        "missing_fields": missing_fields[:2],  # Top 2 missing fields
                        "priority": "high" if category in ["chief_complaint", "symptom_details"] else "medium"
                    })
        
        return priority_questions[:3]  # Return top 3 priority areas
    
    def handle_skip_request(self, conversation_id: int, question_id: str, skip_reason: str = "user_preference") -> Dict[str, Any]:
        """Handle when a user wants to skip a question."""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        # Add to skipped questions list
        skipped_questions = conversation.skipped_questions or []
        skip_entry = {
            "question_id": question_id,
            "skipped_at": datetime.now().isoformat(),
            "reason": skip_reason,
            "can_return_later": True
        }
        skipped_questions.append(skip_entry)
        conversation.skipped_questions = skipped_questions
        
        # Update question tracking
        question_track = self.db.query(QuestionTracking).filter(
            QuestionTracking.conversation_id == conversation_id,
            QuestionTracking.question_id == question_id
        ).first()
        
        if question_track:
            question_track.status = QuestionStatus.SKIPPED.value
            question_track.skip_reason = skip_reason
            question_track.answered_at = datetime.now()
        
        self.db.commit()
        
        return {
            "skipped": True,
            "message": "Question skipped. You can return to it later if needed.",
            "can_continue": True
        }
    
    def handle_unclear_response(self, conversation_id: int, question_id: str, user_response: str) -> Dict[str, Any]:
        """Handle unclear or vague responses that need clarification."""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        # Add to unclear responses list
        unclear_responses = conversation.unclear_responses or []
        unclear_entry = {
            "question_id": question_id,
            "response": user_response,
            "flagged_at": datetime.now().isoformat(),
            "needs_clarification": True,
            "clarification_attempts": 0
        }
        unclear_responses.append(unclear_entry)
        conversation.unclear_responses = unclear_responses
        
        # Update question tracking
        question_track = self.db.query(QuestionTracking).filter(
            QuestionTracking.conversation_id == conversation_id,
            QuestionTracking.question_id == question_id
        ).first()
        
        if question_track:
            question_track.status = QuestionStatus.UNCLEAR.value
            question_track.response_clarity = "vague"
            question_track.needs_followup = True
            question_track.attempt_count += 1
        
        self.db.commit()
        
        # Generate clarification request
        clarification_prompts = [
            "Could you be more specific about that?",
            "Can you give me an example or more details?",
            "I want to make sure I understand correctly. Could you explain that a bit more?",
            "To help your doctor, I need a clearer picture. Can you describe that in more detail?"
        ]
        
        return {
            "needs_clarification": True,
            "clarification_prompt": clarification_prompts[0],  # Could randomize
            "can_skip": True,
            "skip_message": "If you're not sure, you can say 'skip' and we'll move on."
        }
    
    def check_timeout_status(self, conversation_id: int) -> Dict[str, Any]:
        """Check if conversation has timed out and handle accordingly."""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        now = datetime.now()
        last_activity = conversation.last_activity
        idle_minutes = (now - last_activity).total_seconds() / 60
        
        # Check for different timeout levels
        if idle_minutes >= conversation.session_timeout_minutes:
            # Session timeout - end session
            return self._handle_session_timeout(conversation)
        elif idle_minutes >= conversation.idle_timeout_minutes:
            # Idle timeout - send warning
            return self._handle_idle_timeout(conversation, idle_minutes)
        elif idle_minutes >= (conversation.idle_timeout_minutes * 0.7):
            # Approaching timeout - gentle nudge
            return self._handle_approaching_timeout(conversation, idle_minutes)
        
        return {"status": "active", "no_timeout": True}
    
    def _handle_session_timeout(self, conversation: Conversation) -> Dict[str, Any]:
        """Handle complete session timeout."""
        # Create timeout event
        timeout_event = TimeoutEvent(
            conversation_id=conversation.id,
            event_type="timeout",
            timeout_duration=int((datetime.now() - conversation.last_activity).total_seconds()),
            warning_message="Session timed out due to inactivity"
        )
        self.db.add(timeout_event)
        
        # Update conversation status
        if conversation.min_data_threshold_met:
            # Save what we have
            conversation.status = SessionStatus.PAUSED.value
            message = ("Your session has been paused due to inactivity, but don't worry - "
                      "I've saved all the information you've shared. You can return anytime "
                      "to continue where you left off.")
        else:
            # Not enough data to save
            conversation.status = SessionStatus.TIMEOUT.value
            message = ("Your session has timed out. Since we didn't collect enough information "
                      "to save your progress, you'll need to start over when you return.")
        
        self.db.commit()
        
        return {
            "status": "timeout",
            "message": message,
            "can_resume": conversation.min_data_threshold_met,
            "session_saved": conversation.min_data_threshold_met
        }
    
    def _handle_idle_timeout(self, conversation: Conversation, idle_minutes: float) -> Dict[str, Any]:
        """Handle idle timeout warning."""
        conversation.timeout_warnings += 1
        conversation.last_timeout_warning = datetime.now()
        
        timeout_event = TimeoutEvent(
            conversation_id=conversation.id,
            event_type="warning" if conversation.timeout_warnings == 1 else "final_warning",
            timeout_duration=int(idle_minutes * 60),
            warning_message="Idle timeout warning sent"
        )
        self.db.add(timeout_event)
        self.db.commit()
        
        if conversation.timeout_warnings == 1:
            message = ("Still with me? Let me know if you'd like to continue or take a break. "
                      "I can save your progress if you need to step away.")
        else:
            message = ("I'll pause our conversation for now to save your progress. "
                      "You can come back anytime to continue where we left off.")
        
        return {
            "status": "idle_warning",
            "message": message,
            "warning_count": conversation.timeout_warnings,
            "can_continue": True,
            "can_pause": True
        }
    
    def _handle_approaching_timeout(self, conversation: Conversation, idle_minutes: float) -> Dict[str, Any]:
        """Handle approaching timeout with gentle nudge."""
        return {
            "status": "approaching_timeout",
            "gentle_nudge": "How are you doing? Ready for the next question?",
            "minutes_until_warning": conversation.idle_timeout_minutes - idle_minutes
        }
    
    def request_human_handoff(self, conversation_id: int, reason: str) -> Dict[str, Any]:
        """Handle request for human handoff."""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return {"error": "Conversation not found"}
        
        conversation.requested_human_handoff = True
        conversation.handoff_reason = reason
        
        # Save current progress if meets threshold
        if conversation.min_data_threshold_met:
            conversation.status = SessionStatus.PAUSED.value
            message = ("I understand you'd prefer to speak with a human. I've saved all the "
                      "information you've shared so far. You can discuss this further with "
                      "your doctor during your appointment, or if this is urgent, please "
                      "contact your healthcare provider directly.")
        else:
            message = ("I understand you'd prefer to speak with a human. If you're unsure "
                      "or uncomfortable continuing now, we can stop here. You can always "
                      "discuss your concerns directly with your doctor during your appointment.")
        
        self.db.commit()
        
        return {
            "handoff_requested": True,
            "message": message,
            "progress_saved": conversation.min_data_threshold_met,
            "next_steps": "Contact your healthcare provider or continue during your appointment"
        }
    
    def generate_completion_message(self, conversation_id: int) -> str:
        """Generate appropriate completion message based on data completeness."""
        completeness_data = self.evaluate_data_completeness(conversation_id, {})
        completion_percentage = completeness_data.get("completion_percentage", 0)
        
        if completion_percentage >= 90:
            return (
                "🎉 Excellent! I've gathered comprehensive information about your health concerns. "
                "This detailed information will be invaluable for your healthcare team to provide "
                "you with the best possible care. Thank you for being so thorough in sharing your "
                "medical history and symptoms."
            )
        elif completion_percentage >= 70:
            return (
                "✅ Great job! I've collected substantial information about your health concerns. "
                "This gives your healthcare team a solid foundation to work with. If you think "
                "of anything else important before your appointment, feel free to mention it then."
            )
        elif completion_percentage >= 50:
            return (
                "👍 Thank you for sharing this information with me. I've recorded the key details "
                "about your symptoms and medical background. While we could gather more details, "
                "what you've shared provides a good starting point for your healthcare team."
            )
        else:
            return (
                "Thank you for the information you've shared. I've saved what we discussed. "
                "You may want to continue this conversation with your healthcare provider "
                "to ensure they have all the details they need for your care."
            )
    
    def should_save_session(self, conversation_id: int) -> bool:
        """Determine if session has enough data to be worth saving."""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        return conversation and conversation.min_data_threshold_met 