"""
🏥 SOAP Data Manager for Vi Symptom Agent

Manages structured collection of subjective data following OLDCARTS methodology
for proper EMR documentation and systematic symptom assessment.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import json

class SOAPSection(Enum):
    """SOAP note sections for systematic data collection."""
    PATIENT_CONTEXT = "patient_context"
    CHIEF_COMPLAINT = "chief_complaint"
    HPI_OLDCARTS = "hpi_oldcarts"
    EMERGENCY_SCREENING = "emergency_screening"
    MEDICAL_HISTORY = "medical_history"
    VITALS = "vitals"
    INVESTIGATIONS = "investigations"
    REVIEW_OF_SYSTEMS = "review_of_systems"
    FAMILY_SOCIAL_HISTORY = "family_social_history"
    COMPLETION = "completion"

class OLDCARTSField(Enum):
    """OLDCARTS fields for systematic symptom assessment."""
    ONSET = "onset"
    LOCATION = "location"
    DURATION = "duration"
    CHARACTER = "character"
    AGGRAVATING = "aggravating_factors"
    RELIEVING = "relieving_factors"
    TIMING = "timing"
    SEVERITY = "severity"
    RADIATION = "radiation"
    PROGRESSION = "progression"
    RELATED_SYMPTOMS = "related_symptoms"
    TREATMENT_ATTEMPTED = "treatment_attempted"

class SOAPDataManager:
    """Manages structured SOAP data collection with OLDCARTS methodology."""
    
    def __init__(self):
        self.required_fields = self._initialize_required_fields()
        self.emergency_flags = self._initialize_emergency_flags()
        self.system_specific_questions = self._initialize_system_questions()
    
    def _initialize_required_fields(self) -> Dict[str, List[str]]:
        """Initialize required fields for each SOAP section."""
        return {
            SOAPSection.PATIENT_CONTEXT.value: [
                "age", "biological_sex"
            ],
            SOAPSection.CHIEF_COMPLAINT.value: [
                "primary_complaint", "detailed_description"
            ],
            SOAPSection.HPI_OLDCARTS.value: [
                "onset", "location", "duration", "character",
                "aggravating_factors", "relieving_factors", "timing", 
                "severity", "radiation", "progression", "related_symptoms",
                "treatment_attempted"
            ],
            SOAPSection.MEDICAL_HISTORY.value: [
                "chronic_conditions", "current_medications", "allergies",
                "past_surgeries", "hospitalizations", "similar_episodes"
            ],
            SOAPSection.VITALS.value: [
                "blood_pressure", "temperature", "heart_rate", "height", "weight"
            ],
            SOAPSection.INVESTIGATIONS.value: [
                "recent_tests", "test_results", "specialist_care"
            ],
            SOAPSection.REVIEW_OF_SYSTEMS.value: [
                "general", "cardiovascular", "respiratory", "gastrointestinal",
                "genitourinary", "musculoskeletal", "neurological", 
                "dermatologic", "psychiatric", "endocrine", "hematologic"
            ],
            SOAPSection.FAMILY_SOCIAL_HISTORY.value: [
                "family_history", "smoking_drinking", "occupation"
            ]
        }
    
    def _initialize_emergency_flags(self) -> List[str]:
        """Initialize emergency red flag symptoms."""
        return [
            "chest pain", "severe shortness of breath", "slurred speech",
            "vision loss", "fainting", "sudden weakness", "confusion",
            "high fever", "severe headache", "difficulty breathing",
            "loss of consciousness", "severe abdominal pain", "heavy bleeding"
        ]
    
    def _initialize_system_questions(self) -> Dict[str, List[str]]:
        """Initialize system-specific follow-up questions."""
        return {
            "chest_pain": [
                "dyspnea", "radiation_to_arm", "nausea", "sweating", "exertion_related"
            ],
            "fever": [
                "chills", "confusion", "rash", "neck_stiffness"
            ],
            "neurologic": [
                "facial_droop", "speech_changes", "limb_weakness", "vision_changes"
            ],
            "headache": [
                "nausea", "light_sensitivity", "neck_stiffness", "vision_changes"
            ]
        }
    
    def evaluate_soap_completeness(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate completeness of SOAP data collection."""
        section_completeness = {}
        total_required = 0
        total_collected = 0
        
        for section, fields in self.required_fields.items():
            collected_in_section = 0
            for field in fields:
                if self._field_has_meaningful_data(collected_data, field):
                    collected_in_section += 1
                    total_collected += 1
                total_required += 1
            
            completion_percentage = (collected_in_section / len(fields)) * 100
            section_completeness[section] = {
                "collected": collected_in_section,
                "total": len(fields),
                "percentage": completion_percentage,
                "complete": completion_percentage >= 80,  # 80% threshold
                "missing_fields": [f for f in fields if not self._field_has_meaningful_data(collected_data, f)]
            }
        
        overall_completion = (total_collected / total_required) * 100
        
        # Determine current section and next priority
        current_section = self._determine_current_section(section_completeness)
        next_priority = self._get_next_priority_field(section_completeness, collected_data)
        
        return {
            "overall_completion_percentage": overall_completion,
            "total_fields_collected": total_collected,
            "total_required_fields": total_required,
            "section_completeness": section_completeness,
            "current_section": current_section,
            "next_priority_field": next_priority,
            "can_complete_session": overall_completion >= 70,
            "meets_minimum_threshold": total_collected >= 15,
            "missing_critical_sections": self._identify_missing_critical_sections(section_completeness),
            "completion_status": self._determine_completion_status(overall_completion)
        }
    
    def _field_has_meaningful_data(self, collected_data: Dict[str, Any], field: str) -> bool:
        """Check if a field contains meaningful data."""
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
            "not mentioned", "skip", "skipped", "not applicable"
        ]
        
        if isinstance(value, str) and value.lower().strip() in meaningless_responses:
            return False
        
        return True
    
    def _determine_current_section(self, section_completeness: Dict[str, Any]) -> str:
        """Determine which SOAP section we're currently working on."""
        # Follow systematic progression through SOAP sections
        section_order = [
            SOAPSection.PATIENT_CONTEXT.value,
            SOAPSection.CHIEF_COMPLAINT.value,
            SOAPSection.HPI_OLDCARTS.value,
            SOAPSection.MEDICAL_HISTORY.value,
            SOAPSection.VITALS.value,
            SOAPSection.INVESTIGATIONS.value,
            SOAPSection.REVIEW_OF_SYSTEMS.value,
            SOAPSection.FAMILY_SOCIAL_HISTORY.value
        ]
        
        for section in section_order:
            if not section_completeness.get(section, {}).get("complete", False):
                return section
        
        return SOAPSection.COMPLETION.value
    
    def _get_next_priority_field(self, section_completeness: Dict[str, Any], collected_data: Dict[str, Any]) -> Optional[str]:
        """Get the next priority field to collect based on OLDCARTS methodology."""
        current_section = self._determine_current_section(section_completeness)
        
        if current_section == SOAPSection.COMPLETION.value:
            return None
        
        # Get missing fields for current section
        section_data = section_completeness.get(current_section, {})
        missing_fields = section_data.get("missing_fields", [])
        
        if not missing_fields:
            return None
        
        # For OLDCARTS, follow systematic order
        if current_section == SOAPSection.HPI_OLDCARTS.value:
            oldcarts_order = [
                "onset", "location", "duration", "character",
                "aggravating_factors", "relieving_factors", "timing",
                "severity", "radiation", "progression", "related_symptoms",
                "treatment_attempted"
            ]
            
            for field in oldcarts_order:
                if field in missing_fields:
                    return field
        
        # For other sections, return first missing field
        return missing_fields[0] if missing_fields else None
    
    def _identify_missing_critical_sections(self, section_completeness: Dict[str, Any]) -> List[str]:
        """Identify critical sections that are missing or incomplete."""
        critical_sections = [
            SOAPSection.CHIEF_COMPLAINT.value,
            SOAPSection.HPI_OLDCARTS.value,
            SOAPSection.MEDICAL_HISTORY.value
        ]
        
        missing_critical = []
        for section in critical_sections:
            if not section_completeness.get(section, {}).get("complete", False):
                missing_critical.append(section)
        
        return missing_critical
    
    def _determine_completion_status(self, completion_percentage: float) -> str:
        """Determine overall completion status."""
        if completion_percentage >= 90:
            return "comprehensive"
        elif completion_percentage >= 70:
            return "adequate"
        elif completion_percentage >= 50:
            return "partial"
        else:
            return "minimal"
    
    def check_emergency_flags(self, user_message: str, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for emergency red flag symptoms."""
        message_lower = user_message.lower()
        detected_flags = []
        
        for flag in self.emergency_flags:
            if flag in message_lower:
                detected_flags.append(flag)
        
        # Check for specific emergency combinations
        emergency_level = "none"
        requires_immediate_action = False
        
        if detected_flags:
            # Determine severity based on detected flags
            critical_flags = ["chest pain", "difficulty breathing", "loss of consciousness", "severe bleeding"]
            high_flags = ["severe shortness of breath", "slurred speech", "vision loss", "fainting"]
            
            if any(flag in detected_flags for flag in critical_flags):
                emergency_level = "critical"
                requires_immediate_action = True
            elif any(flag in detected_flags for flag in high_flags):
                emergency_level = "high"
                requires_immediate_action = True
            else:
                emergency_level = "moderate"
        
        return {
            "emergency_level": emergency_level,
            "detected_flags": detected_flags,
            "requires_immediate_action": requires_immediate_action,
            "emergency_message": self._generate_emergency_message(emergency_level, detected_flags)
        }
    
    def _generate_emergency_message(self, emergency_level: str, detected_flags: List[str]) -> Optional[str]:
        """Generate appropriate emergency message."""
        if emergency_level in ["critical", "high"]:
            return (
                "⚠️ Your symptoms may be serious. Please call emergency services "
                "or go to the ER immediately. If this is a life-threatening emergency, "
                "call 911 now."
            )
        elif emergency_level == "moderate":
            return (
                "🏥 Based on your symptoms, I recommend seeking urgent medical care. "
                "Please contact your healthcare provider immediately or visit an urgent care center."
            )
        return None
    
    def generate_next_question_context(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate context for AI to create the next appropriate question."""
        completeness = self.evaluate_soap_completeness(collected_data)
        current_section = completeness["current_section"]
        next_field = completeness["next_priority_field"]
        
        # Generate specific guidance for the AI based on current section and field
        question_guidance = self._get_question_guidance(current_section, next_field, collected_data)
        
        return {
            "current_soap_section": current_section,
            "next_priority_field": next_field,
            "completion_status": completeness,
            "question_guidance": question_guidance,
            "collected_data_summary": self._summarize_collected_data(collected_data),
            "should_complete": completeness["can_complete_session"] and not next_field
        }
    
    def _get_question_guidance(self, section: str, field: Optional[str], collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get specific guidance for generating questions based on current field."""
        if not field:
            return {"type": "completion", "instruction": "All required data collected, proceed to completion"}
        
        # Field-specific question templates and guidance
        field_guidance = {
            # Patient Context
            "age": {
                "type": "demographic",
                "question_focus": "To help personalize your experience, may I ask your age?",
                "validation": "numeric_age"
            },
            "biological_sex": {
                "type": "demographic", 
                "question_focus": "What is your biological sex assigned at birth? (Male / Female / Other / Prefer not to say)",
                "validation": "categorical"
            },
            
            # Chief Complaint
            "primary_complaint": {
                "type": "open_ended",
                "question_focus": "What brings you in today? What symptom or issue is most important to you right now?",
                "validation": "descriptive"
            },
            "detailed_description": {
                "type": "follow_up",
                "question_focus": "Can you describe this in more detail? Help me understand exactly what you're experiencing.",
                "validation": "descriptive"
            },
            
            # OLDCARTS
            "onset": {
                "type": "temporal",
                "question_focus": "When did this symptom start? Was it sudden or gradual?",
                "validation": "temporal"
            },
            "location": {
                "type": "anatomical",
                "question_focus": "Where exactly do you feel this symptom? Can you point to or describe the specific location?",
                "validation": "anatomical"
            },
            "duration": {
                "type": "temporal",
                "question_focus": "Is this symptom constant or does it come and go? How long does it last when it occurs?",
                "validation": "temporal"
            },
            "character": {
                "type": "descriptive",
                "question_focus": "How would you describe this symptom? (e.g., sharp, dull, burning, throbbing, cramping)",
                "validation": "descriptive"
            },
            "aggravating_factors": {
                "type": "modifying",
                "question_focus": "What makes this symptom worse? Any activities, positions, or situations that trigger it?",
                "validation": "list"
            },
            "relieving_factors": {
                "type": "modifying",
                "question_focus": "What helps relieve this symptom? Anything that makes it better?",
                "validation": "list"
            },
            "timing": {
                "type": "temporal",
                "question_focus": "Is there a particular time of day when this symptom is worse or better?",
                "validation": "temporal"
            },
            "severity": {
                "type": "scale",
                "question_focus": "On a scale of 1 to 10, with 10 being the worst pain imaginable, how would you rate this symptom?",
                "validation": "numeric_scale"
            },
            "radiation": {
                "type": "anatomical",
                "question_focus": "Does this symptom spread or radiate to any other part of your body?",
                "validation": "anatomical"
            },
            "progression": {
                "type": "temporal",
                "question_focus": "Since it started, is this symptom getting better, worse, or staying the same?",
                "validation": "categorical"
            }
        }
        
        return field_guidance.get(field, {
            "type": "general",
            "question_focus": f"Please tell me about your {field.replace('_', ' ')}",
            "validation": "general"
        })
    
    def _summarize_collected_data(self, collected_data: Dict[str, Any]) -> str:
        """Create a summary of collected data for AI context."""
        summary_parts = []
        
        # Patient context
        if collected_data.get("age") and collected_data.get("biological_sex"):
            summary_parts.append(f"Patient: {collected_data['age']} year old {collected_data['biological_sex']}")
        
        # Chief complaint
        if collected_data.get("primary_complaint"):
            summary_parts.append(f"Chief complaint: {collected_data['primary_complaint']}")
        
        # OLDCARTS progress
        oldcarts_collected = []
        for field in ["onset", "location", "duration", "character", "severity"]:
            if self._field_has_meaningful_data(collected_data, field):
                oldcarts_collected.append(field)
        
        if oldcarts_collected:
            summary_parts.append(f"OLDCARTS collected: {', '.join(oldcarts_collected)}")
        
        return " | ".join(summary_parts) if summary_parts else "No data collected yet" 
🏥 SOAP Data Manager for Vi Symptom Agent

Manages structured collection of subjective data following OLDCARTS methodology
for proper EMR documentation and systematic symptom assessment.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import json

class SOAPSection(Enum):
    """SOAP note sections for systematic data collection."""
    PATIENT_CONTEXT = "patient_context"
    CHIEF_COMPLAINT = "chief_complaint"
    HPI_OLDCARTS = "hpi_oldcarts"
    EMERGENCY_SCREENING = "emergency_screening"
    MEDICAL_HISTORY = "medical_history"
    VITALS = "vitals"
    INVESTIGATIONS = "investigations"
    REVIEW_OF_SYSTEMS = "review_of_systems"
    FAMILY_SOCIAL_HISTORY = "family_social_history"
    COMPLETION = "completion"

class OLDCARTSField(Enum):
    """OLDCARTS fields for systematic symptom assessment."""
    ONSET = "onset"
    LOCATION = "location"
    DURATION = "duration"
    CHARACTER = "character"
    AGGRAVATING = "aggravating_factors"
    RELIEVING = "relieving_factors"
    TIMING = "timing"
    SEVERITY = "severity"
    RADIATION = "radiation"
    PROGRESSION = "progression"
    RELATED_SYMPTOMS = "related_symptoms"
    TREATMENT_ATTEMPTED = "treatment_attempted"

class SOAPDataManager:
    """Manages structured SOAP data collection with OLDCARTS methodology."""
    
    def __init__(self):
        self.required_fields = self._initialize_required_fields()
        self.emergency_flags = self._initialize_emergency_flags()
        self.system_specific_questions = self._initialize_system_questions()
    
    def _initialize_required_fields(self) -> Dict[str, List[str]]:
        """Initialize required fields for each SOAP section."""
        return {
            SOAPSection.PATIENT_CONTEXT.value: [
                "age", "biological_sex"
            ],
            SOAPSection.CHIEF_COMPLAINT.value: [
                "primary_complaint", "detailed_description"
            ],
            SOAPSection.HPI_OLDCARTS.value: [
                "onset", "location", "duration", "character",
                "aggravating_factors", "relieving_factors", "timing", 
                "severity", "radiation", "progression", "related_symptoms",
                "treatment_attempted"
            ],
            SOAPSection.MEDICAL_HISTORY.value: [
                "chronic_conditions", "current_medications", "allergies",
                "past_surgeries", "hospitalizations", "similar_episodes"
            ],
            SOAPSection.VITALS.value: [
                "blood_pressure", "temperature", "heart_rate", "height", "weight"
            ],
            SOAPSection.INVESTIGATIONS.value: [
                "recent_tests", "test_results", "specialist_care"
            ],
            SOAPSection.REVIEW_OF_SYSTEMS.value: [
                "general", "cardiovascular", "respiratory", "gastrointestinal",
                "genitourinary", "musculoskeletal", "neurological", 
                "dermatologic", "psychiatric", "endocrine", "hematologic"
            ],
            SOAPSection.FAMILY_SOCIAL_HISTORY.value: [
                "family_history", "smoking_drinking", "occupation"
            ]
        }
    
    def _initialize_emergency_flags(self) -> List[str]:
        """Initialize emergency red flag symptoms."""
        return [
            "chest pain", "severe shortness of breath", "slurred speech",
            "vision loss", "fainting", "sudden weakness", "confusion",
            "high fever", "severe headache", "difficulty breathing",
            "loss of consciousness", "severe abdominal pain", "heavy bleeding"
        ]
    
    def _initialize_system_questions(self) -> Dict[str, List[str]]:
        """Initialize system-specific follow-up questions."""
        return {
            "chest_pain": [
                "dyspnea", "radiation_to_arm", "nausea", "sweating", "exertion_related"
            ],
            "fever": [
                "chills", "confusion", "rash", "neck_stiffness"
            ],
            "neurologic": [
                "facial_droop", "speech_changes", "limb_weakness", "vision_changes"
            ],
            "headache": [
                "nausea", "light_sensitivity", "neck_stiffness", "vision_changes"
            ]
        }
    
    def evaluate_soap_completeness(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate completeness of SOAP data collection."""
        section_completeness = {}
        total_required = 0
        total_collected = 0
        
        for section, fields in self.required_fields.items():
            collected_in_section = 0
            for field in fields:
                if self._field_has_meaningful_data(collected_data, field):
                    collected_in_section += 1
                    total_collected += 1
                total_required += 1
            
            completion_percentage = (collected_in_section / len(fields)) * 100
            section_completeness[section] = {
                "collected": collected_in_section,
                "total": len(fields),
                "percentage": completion_percentage,
                "complete": completion_percentage >= 80,  # 80% threshold
                "missing_fields": [f for f in fields if not self._field_has_meaningful_data(collected_data, f)]
            }
        
        overall_completion = (total_collected / total_required) * 100
        
        # Determine current section and next priority
        current_section = self._determine_current_section(section_completeness)
        next_priority = self._get_next_priority_field(section_completeness, collected_data)
        
        return {
            "overall_completion_percentage": overall_completion,
            "total_fields_collected": total_collected,
            "total_required_fields": total_required,
            "section_completeness": section_completeness,
            "current_section": current_section,
            "next_priority_field": next_priority,
            "can_complete_session": overall_completion >= 70,
            "meets_minimum_threshold": total_collected >= 15,
            "missing_critical_sections": self._identify_missing_critical_sections(section_completeness),
            "completion_status": self._determine_completion_status(overall_completion)
        }
    
    def _field_has_meaningful_data(self, collected_data: Dict[str, Any], field: str) -> bool:
        """Check if a field contains meaningful data."""
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
            "not mentioned", "skip", "skipped", "not applicable"
        ]
        
        if isinstance(value, str) and value.lower().strip() in meaningless_responses:
            return False
        
        return True
    
    def _determine_current_section(self, section_completeness: Dict[str, Any]) -> str:
        """Determine which SOAP section we're currently working on."""
        # Follow systematic progression through SOAP sections
        section_order = [
            SOAPSection.PATIENT_CONTEXT.value,
            SOAPSection.CHIEF_COMPLAINT.value,
            SOAPSection.HPI_OLDCARTS.value,
            SOAPSection.MEDICAL_HISTORY.value,
            SOAPSection.VITALS.value,
            SOAPSection.INVESTIGATIONS.value,
            SOAPSection.REVIEW_OF_SYSTEMS.value,
            SOAPSection.FAMILY_SOCIAL_HISTORY.value
        ]
        
        for section in section_order:
            if not section_completeness.get(section, {}).get("complete", False):
                return section
        
        return SOAPSection.COMPLETION.value
    
    def _get_next_priority_field(self, section_completeness: Dict[str, Any], collected_data: Dict[str, Any]) -> Optional[str]:
        """Get the next priority field to collect based on OLDCARTS methodology."""
        current_section = self._determine_current_section(section_completeness)
        
        if current_section == SOAPSection.COMPLETION.value:
            return None
        
        # Get missing fields for current section
        section_data = section_completeness.get(current_section, {})
        missing_fields = section_data.get("missing_fields", [])
        
        if not missing_fields:
            return None
        
        # For OLDCARTS, follow systematic order
        if current_section == SOAPSection.HPI_OLDCARTS.value:
            oldcarts_order = [
                "onset", "location", "duration", "character",
                "aggravating_factors", "relieving_factors", "timing",
                "severity", "radiation", "progression", "related_symptoms",
                "treatment_attempted"
            ]
            
            for field in oldcarts_order:
                if field in missing_fields:
                    return field
        
        # For other sections, return first missing field
        return missing_fields[0] if missing_fields else None
    
    def _identify_missing_critical_sections(self, section_completeness: Dict[str, Any]) -> List[str]:
        """Identify critical sections that are missing or incomplete."""
        critical_sections = [
            SOAPSection.CHIEF_COMPLAINT.value,
            SOAPSection.HPI_OLDCARTS.value,
            SOAPSection.MEDICAL_HISTORY.value
        ]
        
        missing_critical = []
        for section in critical_sections:
            if not section_completeness.get(section, {}).get("complete", False):
                missing_critical.append(section)
        
        return missing_critical
    
    def _determine_completion_status(self, completion_percentage: float) -> str:
        """Determine overall completion status."""
        if completion_percentage >= 90:
            return "comprehensive"
        elif completion_percentage >= 70:
            return "adequate"
        elif completion_percentage >= 50:
            return "partial"
        else:
            return "minimal"
    
    def check_emergency_flags(self, user_message: str, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for emergency red flag symptoms."""
        message_lower = user_message.lower()
        detected_flags = []
        
        for flag in self.emergency_flags:
            if flag in message_lower:
                detected_flags.append(flag)
        
        # Check for specific emergency combinations
        emergency_level = "none"
        requires_immediate_action = False
        
        if detected_flags:
            # Determine severity based on detected flags
            critical_flags = ["chest pain", "difficulty breathing", "loss of consciousness", "severe bleeding"]
            high_flags = ["severe shortness of breath", "slurred speech", "vision loss", "fainting"]
            
            if any(flag in detected_flags for flag in critical_flags):
                emergency_level = "critical"
                requires_immediate_action = True
            elif any(flag in detected_flags for flag in high_flags):
                emergency_level = "high"
                requires_immediate_action = True
            else:
                emergency_level = "moderate"
        
        return {
            "emergency_level": emergency_level,
            "detected_flags": detected_flags,
            "requires_immediate_action": requires_immediate_action,
            "emergency_message": self._generate_emergency_message(emergency_level, detected_flags)
        }
    
    def _generate_emergency_message(self, emergency_level: str, detected_flags: List[str]) -> Optional[str]:
        """Generate appropriate emergency message."""
        if emergency_level in ["critical", "high"]:
            return (
                "⚠️ Your symptoms may be serious. Please call emergency services "
                "or go to the ER immediately. If this is a life-threatening emergency, "
                "call 911 now."
            )
        elif emergency_level == "moderate":
            return (
                "🏥 Based on your symptoms, I recommend seeking urgent medical care. "
                "Please contact your healthcare provider immediately or visit an urgent care center."
            )
        return None
    
    def generate_next_question_context(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate context for AI to create the next appropriate question."""
        completeness = self.evaluate_soap_completeness(collected_data)
        current_section = completeness["current_section"]
        next_field = completeness["next_priority_field"]
        
        # Generate specific guidance for the AI based on current section and field
        question_guidance = self._get_question_guidance(current_section, next_field, collected_data)
        
        return {
            "current_soap_section": current_section,
            "next_priority_field": next_field,
            "completion_status": completeness,
            "question_guidance": question_guidance,
            "collected_data_summary": self._summarize_collected_data(collected_data),
            "should_complete": completeness["can_complete_session"] and not next_field
        }
    
    def _get_question_guidance(self, section: str, field: Optional[str], collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get specific guidance for generating questions based on current field."""
        if not field:
            return {"type": "completion", "instruction": "All required data collected, proceed to completion"}
        
        # Field-specific question templates and guidance
        field_guidance = {
            # Patient Context
            "age": {
                "type": "demographic",
                "question_focus": "To help personalize your experience, may I ask your age?",
                "validation": "numeric_age"
            },
            "biological_sex": {
                "type": "demographic", 
                "question_focus": "What is your biological sex assigned at birth? (Male / Female / Other / Prefer not to say)",
                "validation": "categorical"
            },
            
            # Chief Complaint
            "primary_complaint": {
                "type": "open_ended",
                "question_focus": "What brings you in today? What symptom or issue is most important to you right now?",
                "validation": "descriptive"
            },
            "detailed_description": {
                "type": "follow_up",
                "question_focus": "Can you describe this in more detail? Help me understand exactly what you're experiencing.",
                "validation": "descriptive"
            },
            
            # OLDCARTS
            "onset": {
                "type": "temporal",
                "question_focus": "When did this symptom start? Was it sudden or gradual?",
                "validation": "temporal"
            },
            "location": {
                "type": "anatomical",
                "question_focus": "Where exactly do you feel this symptom? Can you point to or describe the specific location?",
                "validation": "anatomical"
            },
            "duration": {
                "type": "temporal",
                "question_focus": "Is this symptom constant or does it come and go? How long does it last when it occurs?",
                "validation": "temporal"
            },
            "character": {
                "type": "descriptive",
                "question_focus": "How would you describe this symptom? (e.g., sharp, dull, burning, throbbing, cramping)",
                "validation": "descriptive"
            },
            "aggravating_factors": {
                "type": "modifying",
                "question_focus": "What makes this symptom worse? Any activities, positions, or situations that trigger it?",
                "validation": "list"
            },
            "relieving_factors": {
                "type": "modifying",
                "question_focus": "What helps relieve this symptom? Anything that makes it better?",
                "validation": "list"
            },
            "timing": {
                "type": "temporal",
                "question_focus": "Is there a particular time of day when this symptom is worse or better?",
                "validation": "temporal"
            },
            "severity": {
                "type": "scale",
                "question_focus": "On a scale of 1 to 10, with 10 being the worst pain imaginable, how would you rate this symptom?",
                "validation": "numeric_scale"
            },
            "radiation": {
                "type": "anatomical",
                "question_focus": "Does this symptom spread or radiate to any other part of your body?",
                "validation": "anatomical"
            },
            "progression": {
                "type": "temporal",
                "question_focus": "Since it started, is this symptom getting better, worse, or staying the same?",
                "validation": "categorical"
            }
        }
        
        return field_guidance.get(field, {
            "type": "general",
            "question_focus": f"Please tell me about your {field.replace('_', ' ')}",
            "validation": "general"
        })
    
    def _summarize_collected_data(self, collected_data: Dict[str, Any]) -> str:
        """Create a summary of collected data for AI context."""
        summary_parts = []
        
        # Patient context
        if collected_data.get("age") and collected_data.get("biological_sex"):
            summary_parts.append(f"Patient: {collected_data['age']} year old {collected_data['biological_sex']}")
        
        # Chief complaint
        if collected_data.get("primary_complaint"):
            summary_parts.append(f"Chief complaint: {collected_data['primary_complaint']}")
        
        # OLDCARTS progress
        oldcarts_collected = []
        for field in ["onset", "location", "duration", "character", "severity"]:
            if self._field_has_meaningful_data(collected_data, field):
                oldcarts_collected.append(field)
        
        if oldcarts_collected:
            summary_parts.append(f"OLDCARTS collected: {', '.join(oldcarts_collected)}")
        
        return " | ".join(summary_parts) if summary_parts else "No data collected yet" 