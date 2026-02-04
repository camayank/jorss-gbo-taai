"""
Intelligent Tax Agent with Sophisticated NLP.

This enhanced agent uses:
- OpenAI structured outputs for reliable data extraction
- Entity recognition for tax-specific information
- Document intelligence integration with OCR
- Multi-turn conversation memory and context
- Integration with questionnaire engine for structured capture
- Proactive question suggestion based on detected patterns

Resolves Gap #1: AI Intake Intelligence
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum

from openai import OpenAI

logger = logging.getLogger(__name__)

from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
from models.income import Income, W2Info, Form1099Info
from models.deductions import Deductions, ItemizedDeductions
from models.credits import TaxCredits

# CPA Intelligence for professional, deadline-aware responses
try:
    from services.cpa_intelligence_service import get_cpa_intelligence, build_enhanced_openai_context
    CPA_INTELLIGENCE_AVAILABLE = True
except ImportError:
    CPA_INTELLIGENCE_AVAILABLE = False

# SSTB Classifier for QBI deduction eligibility
try:
    from calculator.sstb_classifier import SSTBClassifier, SSTBCategory
    SSTB_CLASSIFIER_AVAILABLE = True
except ImportError:
    SSTB_CLASSIFIER_AVAILABLE = False

# Calculation Engine for real-time tax estimate feedback
try:
    from calculator.engine import FederalTaxEngine, CalculationBreakdown
    CALCULATION_ENGINE_AVAILABLE = True
except ImportError:
    CALCULATION_ENGINE_AVAILABLE = False

# Audit Trail for compliance logging
try:
    from audit.audit_logger import (
        get_audit_logger,
        audit_tax_field_change,
        audit_income_change,
        audit_form_import,
        audit_tax_calculation,
        AuditEventType,
        AuditSeverity
    )
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

# Tax Opportunity Detection for proactive savings identification
try:
    from services.tax_opportunity_detector import (
        TaxOpportunityDetector,
        TaxpayerProfile,
        TaxOpportunity,
        OpportunityPriority,
        create_profile_from_tax_return
    )
    OPPORTUNITY_DETECTOR_AVAILABLE = True
except ImportError:
    OPPORTUNITY_DETECTOR_AVAILABLE = False


class ExtractionConfidence(Enum):
    """Confidence level for extracted information."""
    HIGH = "high"  # 90%+ confidence
    MEDIUM = "medium"  # 70-90% confidence
    LOW = "low"  # 50-70% confidence
    UNCERTAIN = "uncertain"  # <50% confidence


# Import validators for confidence calculation (Phase 2.2)
try:
    from web.validation_helpers import validate_ssn, validate_currency, validate_name, validate_ein
    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False


def calculate_entity_confidence(entity_type: str, value: Any) -> ExtractionConfidence:
    """
    Phase 2.2: Calculate confidence based on actual validation.

    Uses validators to determine if values are valid and reasonable.

    Args:
        entity_type: Type of entity (ssn, w2_wages, etc.)
        value: The extracted value

    Returns:
        ExtractionConfidence level based on validation results
    """
    if not value:
        return ExtractionConfidence.UNCERTAIN

    try:
        # SSN validation
        if entity_type == "ssn":
            if VALIDATORS_AVAILABLE:
                is_valid, _ = validate_ssn(str(value))
                return ExtractionConfidence.HIGH if is_valid else ExtractionConfidence.LOW
            else:
                # Basic check
                clean = str(value).replace("-", "").replace(" ", "")
                return ExtractionConfidence.HIGH if len(clean) == 9 else ExtractionConfidence.LOW

        # Currency/wage validation
        if entity_type in ["w2_wages", "w2_federal_withholding", "mortgage_interest",
                           "property_taxes", "charitable_cash", "self_employment_income"]:
            try:
                val = float(str(value).replace(",", "").replace("$", ""))
                # Check for reasonable ranges
                if entity_type == "w2_wages":
                    if val < 0:
                        return ExtractionConfidence.UNCERTAIN
                    if val > 10000000:  # $10M+ seems unusual
                        return ExtractionConfidence.UNCERTAIN
                    if val > 1000000:  # $1M+ is high but possible
                        return ExtractionConfidence.MEDIUM
                    return ExtractionConfidence.HIGH

                if entity_type == "w2_federal_withholding":
                    if val < 0:
                        return ExtractionConfidence.UNCERTAIN
                    if val > 5000000:  # >$5M withholding is unusual
                        return ExtractionConfidence.UNCERTAIN
                    return ExtractionConfidence.HIGH

                # Other currency fields
                if val < 0:
                    return ExtractionConfidence.LOW
                return ExtractionConfidence.HIGH

            except (ValueError, TypeError):
                return ExtractionConfidence.LOW

        # Name validation
        if entity_type in ["first_name", "last_name", "employer_name"]:
            if VALIDATORS_AVAILABLE and entity_type != "employer_name":
                is_valid, _ = validate_name(str(value), entity_type.replace("_", " ").title())
                return ExtractionConfidence.HIGH if is_valid else ExtractionConfidence.MEDIUM
            else:
                name = str(value).strip()
                if len(name) < 2:
                    return ExtractionConfidence.LOW
                if len(name) > 100:
                    return ExtractionConfidence.LOW
                return ExtractionConfidence.HIGH

        # Filing status validation
        if entity_type == "filing_status":
            valid_statuses = ["single", "married_filing_jointly", "married_filing_separately",
                            "head_of_household", "qualifying_widow", "married", "hoh"]
            status_lower = str(value).lower().replace(" ", "_")
            if any(s in status_lower for s in valid_statuses):
                return ExtractionConfidence.HIGH
            return ExtractionConfidence.MEDIUM

        # EIN validation
        if entity_type == "ein":
            if VALIDATORS_AVAILABLE:
                is_valid, _ = validate_ein(str(value))
                return ExtractionConfidence.HIGH if is_valid else ExtractionConfidence.LOW
            else:
                clean = str(value).replace("-", "").replace(" ", "")
                return ExtractionConfidence.HIGH if len(clean) == 9 else ExtractionConfidence.LOW

        # Default: return medium confidence for unvalidated fields
        return ExtractionConfidence.MEDIUM

    except (ValueError, TypeError, AttributeError, KeyError) as e:
        import logging
        logging.getLogger(__name__).debug(f"Entity confidence check failed: {e}")
        return ExtractionConfidence.UNCERTAIN


@dataclass
class ExtractedEntity:
    """A piece of information extracted from user input or documents."""
    entity_type: str  # e.g., "name", "ssn", "w2_wages", "mortgage_interest"
    value: Any
    confidence: ExtractionConfidence
    source: str  # "conversation", "document", "ocr"
    context: Optional[str] = None  # Surrounding context
    needs_verification: bool = False  # Should we ask user to confirm?
    tax_form: Optional[str] = None  # e.g., "Form W-2", "Form 1098"
    tax_form_box: Optional[str] = None  # e.g., "Box 1", "Box 2"


@dataclass
class ConversationContext:
    """Rich context about the ongoing conversation."""
    current_topic: str  # e.g., "w2_income", "mortgage_deduction"
    discussed_topics: List[str]
    pending_clarifications: List[str]
    detected_forms: List[str]  # Tax forms mentioned or detected
    detected_life_events: List[str]  # Marriage, birth, home purchase, etc.
    suggested_questions: List[str]  # Proactive suggestions
    extraction_history: List[ExtractedEntity]
    # SSTB Classification for QBI deduction (IRC §199A)
    business_type: Optional[str] = None  # e.g., "consulting", "law firm", "retail"
    business_description: Optional[str] = None
    naics_code: Optional[str] = None
    sstb_category: Optional[str] = None  # SSTBCategory value if classified
    is_sstb: Optional[bool] = None  # True if SSTB, False if not, None if unknown
    sstb_impact_message: Optional[str] = None  # User-facing explanation
    # Real-time tax estimate (updated after each calculation)
    running_estimate: Optional[float] = None  # Positive = owe, Negative = refund
    running_total_tax: Optional[float] = None
    running_total_withholding: Optional[float] = None
    running_effective_rate: Optional[float] = None
    last_calculation_timestamp: Optional[str] = None


@dataclass
class DocumentIntelligence:
    """Results from document analysis."""
    document_type: str  # "w2", "1099", "1098", "photo", "unknown"
    confidence: float
    extracted_fields: Dict[str, Any]
    ocr_text: Optional[str] = None
    detected_forms: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class IntelligentTaxAgent:
    """
    Enhanced AI agent with sophisticated NLP and document intelligence.

    Capabilities:
    - Structured data extraction using OpenAI function calling
    - Tax-specific entity recognition (SSN, EIN, tax forms, etc.)
    - Document intelligence (OCR integration, form detection)
    - Multi-turn conversation memory with context
    - Proactive question suggestions based on patterns
    - Integration with questionnaire engine
    """

    def __init__(self, api_key: Optional[str] = None, use_ocr: bool = True, session_id: Optional[str] = None):
        """Initialize the intelligent agent."""
        import uuid

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")  # gpt-4o for structured outputs
        self.use_ocr = use_ocr
        self.session_id = session_id or str(uuid.uuid4())

        # Core state
        self.tax_return: Optional[TaxReturn] = None
        self.messages: List[Dict[str, str]] = []
        self.context = ConversationContext(
            current_topic="introduction",
            discussed_topics=[],
            pending_clarifications=[],
            detected_forms=[],
            detected_life_events=[],
            suggested_questions=[],
            extraction_history=[]
        )

        # Integration points
        self._questionnaire_engine = None  # Can integrate with questionnaire_engine.py
        self._ocr_engine = None  # Can integrate with ocr_engine.py

        # Audit logger for compliance tracking
        self._audit_logger = get_audit_logger() if AUDIT_AVAILABLE else None

        # Tax opportunity detector for proactive savings identification
        self._opportunity_detector = TaxOpportunityDetector(api_key=api_key) if OPPORTUNITY_DETECTOR_AVAILABLE else None
        self._detected_opportunities = []
        self._opportunities_last_checked = None

        self._setup_system_prompt()
        self._initialize_tax_return()

        # Log session start
        self._audit_log_session_start()

    def _audit_log_session_start(self):
        """Log the start of a tax filing session."""
        if not AUDIT_AVAILABLE or not self._audit_logger:
            return

        self._audit_logger.log(
            event_type=AuditEventType.TAX_RETURN_CREATE,
            action="session_start",
            resource_type="tax_session",
            resource_id=self.session_id,
            details={
                "model": self.model,
                "ocr_enabled": self.use_ocr
            },
            severity=AuditSeverity.INFO
        )

    def _audit_log_field_change(self, field_name: str, old_value: Any, new_value: Any,
                                 source: str = "ai_chatbot", confidence: float = None):
        """Log a change to a tax data field."""
        if not AUDIT_AVAILABLE:
            return

        audit_tax_field_change(
            session_id=self.session_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            source=source,
            confidence=confidence
        )

    def _audit_log_income_change(self, income_type: str, old_value: float,
                                  new_value: float, source: str = "ai_chatbot"):
        """Log a change to income data."""
        if not AUDIT_AVAILABLE:
            return

        audit_income_change(
            session_id=self.session_id,
            income_type=income_type,
            old_value=old_value,
            new_value=new_value,
            source=source
        )

    def _audit_log_calculation(self, calculation_type: str, inputs: Dict, result: Any):
        """Log a tax calculation."""
        if not AUDIT_AVAILABLE:
            return

        audit_tax_calculation(
            session_id=self.session_id,
            calculation_type=calculation_type,
            inputs=inputs,
            result=result
        )

    def _setup_system_prompt(self):
        """Setup enhanced system prompt for intelligent extraction."""
        self.system_prompt = """You are an expert tax preparation AI assistant with deep knowledge of US tax law (Tax Year 2025). Your role is to have intelligent conversations with taxpayers to collect accurate tax information.

CAPABILITIES:
- Extract structured data from natural language
- Recognize tax forms (W-2, 1099, 1098, etc.) and their fields
- Detect life events that trigger tax implications (marriage, home purchase, business start, etc.)
- Ask proactive follow-up questions based on detected patterns
- Validate information against IRS rules
- Explain tax concepts in plain language

EXTRACTION GUIDELINES:
1. SSN/EIN: Recognize formats XXX-XX-XXXX (SSN) or XX-XXXXXXX (EIN)
2. Dollar amounts: Extract with context (wages, withholding, deductions, etc.)
3. Tax forms: Identify mentions of W-2, 1099, 1098, Schedule C, etc.
4. Life events: Detect marriage, divorce, birth, death, home purchase, job change, etc.
5. Filing status: Single, Married Filing Jointly, Married Filing Separately, Head of Household, Qualifying Widow(er)

PROACTIVE BEHAVIOR:
- If user mentions "W-2", ask about employer name, wages (Box 1), federal withholding (Box 2)
- If user mentions "bought a house", ask about mortgage interest, property taxes
- If user mentions "had a baby", ask about child tax credit eligibility
- If user mentions "self-employed", ask about Schedule C income and expenses
- If user mentions "stocks" or "investments", ask about 1099-DIV, 1099-B, capital gains

VALIDATION:
- SSN must be valid format (not all zeros, not sequential)
- Dates must be reasonable (birth date in past, etc.)
- Dollar amounts must be non-negative for most fields
- Filing status must match life situation

RESPONSE STRUCTURE (Phase 2.1):
- Line 1: Acknowledge/confirm extracted data
- Lines 2-3: Relevant insight (if applicable)
- Line 4: Single focused follow-up question
- Keep under 150 words

CONFIDENCE BEHAVIOR:
- HIGH confidence: Apply data silently, acknowledge briefly
- MEDIUM confidence: Confirm with user before proceeding
- LOW/UNCERTAIN confidence: Ask user to verify explicitly before applying

Keep responses conversational, friendly, and professional. Extract all structured data you can while maintaining natural dialogue."""

        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _initialize_tax_return(self):
        """Initialize empty tax return structure."""
        self.tax_return = TaxReturn(
            taxpayer=TaxpayerInfo(
                first_name="",
                last_name="",
                filing_status=FilingStatus.SINGLE
            ),
            income=Income(),
            deductions=Deductions(),
            credits=TaxCredits()
        )

    def start_conversation(self) -> str:
        """Start the intelligent conversation flow."""
        greeting = """Hello! I'm your AI tax assistant, and I'm here to help guide you through your 2025 tax filing.

⚠️ **IMPORTANT DISCLAIMER**:
• I am an AI assistant, NOT a licensed tax professional, CPA, or Enrolled Agent
• This is NOT professional tax advice - I provide general tax information only
• For complex situations, audit support, or professional representation, please consult a licensed CPA or EA
• You are responsible for the accuracy of your tax return
• Always verify tax advice with official IRS publications or a tax professional

I can help you by:
✓ Having a natural conversation about your tax situation
✓ Understanding your tax documents (W-2s, 1099s, etc.)
✓ Asking smart follow-up questions based on what you tell me
✓ Explaining tax concepts in plain English (with IRS references when applicable)

You can:
- Chat naturally about your income, deductions, and life changes
- Upload photos of your tax forms (I'll read them!)
- Ask me questions any time

Let's start with the basics. What's your first name?"""

        self.messages.append({"role": "assistant", "content": greeting})
        return greeting

    def process_message(self, user_input: str, image_data: Optional[str] = None) -> str:
        """
        Process user message with intelligent extraction.

        Args:
            user_input: User's text message
            image_data: Optional base64-encoded image (for document upload)

        Returns:
            AI response with follow-up questions
        """
        # Add user message
        self.messages.append({"role": "user", "content": user_input})

        # Analyze document if provided
        if image_data and self.use_ocr:
            doc_intel = self._analyze_document(image_data)
            if doc_intel.extracted_fields:
                self._apply_document_intelligence(doc_intel)

        # Extract structured information using OpenAI function calling
        extracted_entities = self._extract_entities_with_ai(user_input)

        # Update tax return with extracted information
        contradictions = []
        for entity in extracted_entities:
            # Phase 1.5: Check for contradictions before applying
            contradiction_warning = self._detect_contradictions(entity)
            if contradiction_warning:
                contradictions.append(contradiction_warning)

            self._apply_extracted_entity(entity)
            self.context.extraction_history.append(entity)

        # Store contradictions for response generation
        self._current_contradictions = contradictions

        # Calculate running tax estimate after each update
        self._calculate_running_estimate()

        # Detect patterns and generate proactive questions
        self._detect_patterns_and_suggest()

        # Update conversation context
        self._update_context(user_input, extracted_entities)

        # Generate AI response with context
        assistant_message = self._generate_contextual_response()

        # Add assistant message
        self.messages.append({"role": "assistant", "content": assistant_message})

        return assistant_message

    def _extract_entities_with_ai(self, user_input: str) -> List[ExtractedEntity]:
        """
        Use OpenAI structured outputs to extract tax entities.

        This replaces the basic regex extraction with AI-powered understanding.
        """
        # Define extraction function schema
        extraction_schema = {
            "name": "extract_tax_entities",
            "description": "Extract structured tax information from user's message",
            "parameters": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_type": {
                                    "type": "string",
                                    "enum": [
                                        "first_name", "last_name", "middle_name",
                                        "ssn", "ein", "birth_date", "phone", "email",
                                        "address", "city", "state", "zip",
                                        "filing_status",
                                        "employer_name", "w2_wages", "w2_federal_withholding",
                                        "w2_state_withholding", "w2_social_security_wages",
                                        "w2_medicare_wages",
                                        "1099_payer", "1099_amount", "1099_type",
                                        "interest_income", "dividend_income", "capital_gains",
                                        "self_employment_income", "self_employment_expenses",
                                        "business_type", "business_name", "business_description", "naics_code",
                                        "rental_income", "rental_expenses",
                                        "mortgage_interest", "property_taxes", "state_local_taxes",
                                        "charitable_cash", "charitable_noncash",
                                        "medical_expenses",
                                        "num_children", "child_name", "child_ssn", "child_birth_date",
                                        "education_expenses", "student_name",
                                        "health_insurance_premium",
                                        "home_purchase_date", "home_sale_date",
                                        "job_change_date", "marriage_date", "divorce_date",
                                        "retirement_contribution", "hsa_contribution"
                                    ]
                                },
                                "value": {
                                    "type": "string",
                                    "description": "The extracted value"
                                },
                                "confidence": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low", "uncertain"]
                                },
                                "context": {
                                    "type": "string",
                                    "description": "Relevant context from the message"
                                }
                            },
                            "required": ["entity_type", "value", "confidence"]
                        }
                    },
                    "detected_forms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tax forms mentioned (W-2, 1099, 1098, etc.)"
                    },
                    "life_events": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Life events detected (marriage, birth, home purchase, etc.)"
                    }
                },
                "required": ["entities"]
            }
        }

        try:
            # Call OpenAI with function calling for structured extraction
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Extract all tax-related information from this message:\n\n{user_input}"}
                ],
                functions=[extraction_schema],
                function_call={"name": "extract_tax_entities"},
                temperature=0.1  # Low temperature for reliable extraction
            )

            # Parse function call result
            if response.choices[0].message.function_call:
                result = json.loads(response.choices[0].message.function_call.arguments)

                # Update context with detected forms and life events
                self.context.detected_forms.extend(result.get("detected_forms", []))
                self.context.detected_life_events.extend(result.get("life_events", []))

                # Convert to ExtractedEntity objects
                entities = []
                for entity_data in result.get("entities", []):
                    # Phase 2.2: Use validation-based confidence instead of AI-reported
                    ai_confidence = ExtractionConfidence(entity_data["confidence"])
                    validated_confidence = calculate_entity_confidence(
                        entity_data["entity_type"],
                        entity_data["value"]
                    )
                    # Use the lower of AI confidence and validation confidence
                    confidence_priority = {
                        ExtractionConfidence.HIGH: 4,
                        ExtractionConfidence.MEDIUM: 3,
                        ExtractionConfidence.LOW: 2,
                        ExtractionConfidence.UNCERTAIN: 1
                    }
                    final_confidence = (
                        validated_confidence
                        if confidence_priority[validated_confidence] < confidence_priority[ai_confidence]
                        else ai_confidence
                    )

                    entity = ExtractedEntity(
                        entity_type=entity_data["entity_type"],
                        value=entity_data["value"],
                        confidence=final_confidence,
                        source="conversation",
                        context=entity_data.get("context"),
                        needs_verification=(final_confidence in [ExtractionConfidence.LOW, ExtractionConfidence.UNCERTAIN])
                    )
                    entities.append(entity)

                return entities

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"AI extraction failed, using fallback: {e}")
            # Fallback to basic extraction
            return self._basic_extraction_fallback(user_input)
        except Exception as e:
            logger.exception(f"Unexpected error in AI extraction: {e}")
            return self._basic_extraction_fallback(user_input)

        return []

    def _basic_extraction_fallback(self, user_input: str) -> List[ExtractedEntity]:
        """Fallback to basic regex extraction if AI fails."""
        entities = []
        user_lower = user_input.lower()

        # Extract dollar amounts with context
        dollar_pattern = r'\$?([\d,]+(?:\.\d{2})?)'
        for match in re.finditer(dollar_pattern, user_input):
            amount = match.group(1).replace(',', '')
            try:
                value = float(amount)
                if value > 100:  # Likely a meaningful amount
                    # Try to determine context
                    context_start = max(0, match.start() - 30)
                    context_end = min(len(user_input), match.end() + 30)
                    context = user_input[context_start:context_end]

                    entity_type = "unknown_amount"
                    if any(word in context.lower() for word in ["wage", "salary", "earned", "w-2", "w2"]):
                        entity_type = "w2_wages"
                    elif any(word in context.lower() for word in ["withh", "federal", "tax"]):
                        entity_type = "w2_federal_withholding"
                    elif "mortgage" in context.lower() or "interest" in context.lower():
                        entity_type = "mortgage_interest"

                    entities.append(ExtractedEntity(
                        entity_type=entity_type,
                        value=value,
                        confidence=ExtractionConfidence.MEDIUM,
                        source="conversation",
                        context=context
                    ))
            except ValueError:
                pass

        # Extract SSN
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        ssn_match = re.search(ssn_pattern, user_input)
        if ssn_match:
            entities.append(ExtractedEntity(
                entity_type="ssn",
                value=ssn_match.group(0),
                confidence=ExtractionConfidence.HIGH,
                source="conversation",
                needs_verification=True  # Always verify SSN
            ))

        # Extract filing status - ALL 5 IRS FILING STATUSES
        # Priority order matters: more specific checks first
        if "widow" in user_lower or "widower" in user_lower:
            # Qualifying Widow(er) - requires spouse death within 2 years + dependent
            entities.append(ExtractedEntity(
                entity_type="filing_status",
                value="qualifying_widow",
                confidence=ExtractionConfidence.MEDIUM,  # Needs verification
                source="conversation",
                needs_verification=True  # Must verify: spouse death date, dependent child
            ))
        elif "head of household" in user_lower or " hoh " in f" {user_lower} " or user_lower == "hoh":
            # Head of Household - requires unmarried + paying >50% household costs + qualifying person
            entities.append(ExtractedEntity(
                entity_type="filing_status",
                value="head_of_household",
                confidence=ExtractionConfidence.MEDIUM,
                source="conversation",
                needs_verification=True  # Must verify: unmarried, >50% household costs, qualifying person
            ))
        elif "married" in user_lower and ("separate" in user_lower or "separately" in user_lower):
            # Married Filing Separately
            entities.append(ExtractedEntity(
                entity_type="filing_status",
                value="married_filing_separately",
                confidence=ExtractionConfidence.HIGH,
                source="conversation"
            ))
        elif "married" in user_lower and ("joint" in user_lower or "together" in user_lower):
            # Married Filing Jointly
            entities.append(ExtractedEntity(
                entity_type="filing_status",
                value="married_filing_jointly",
                confidence=ExtractionConfidence.HIGH,
                source="conversation"
            ))
        elif "single" in user_lower and "married" not in user_lower:
            # Single
            entities.append(ExtractedEntity(
                entity_type="filing_status",
                value="single",
                confidence=ExtractionConfidence.HIGH,
                source="conversation"
            ))

        # Extract names (simple word-based)
        if self.context.current_topic == "name" and not self.tax_return.taxpayer.first_name:
            words = user_input.strip().split()
            if words and words[0].isalpha():
                entities.append(ExtractedEntity(
                    entity_type="first_name",
                    value=words[0].capitalize(),
                    confidence=ExtractionConfidence.HIGH,
                    source="conversation"
                ))
                if len(words) > 1 and words[-1].isalpha():
                    entities.append(ExtractedEntity(
                        entity_type="last_name",
                        value=words[-1].capitalize(),
                        confidence=ExtractionConfidence.HIGH,
                        source="conversation"
                    ))

        return entities

    def _validate_before_apply(self, entity: ExtractedEntity) -> tuple:
        """
        Phase 2.3: Gate all data application through validation.

        Cross-validates related fields (e.g., withholding < wages).

        Args:
            entity: The entity to validate

        Returns:
            (is_valid, error_message) tuple
        """
        entity_type = entity.entity_type
        value = entity.value

        try:
            # SSN validation
            if entity_type == "ssn":
                if VALIDATORS_AVAILABLE:
                    is_valid, error = validate_ssn(str(value))
                    if not is_valid:
                        return False, error
                else:
                    clean = str(value).replace("-", "").replace(" ", "")
                    if len(clean) != 9:
                        return False, "SSN must be 9 digits"

            # Currency validations
            if entity_type in ["w2_wages", "w2_federal_withholding", "mortgage_interest",
                               "property_taxes", "charitable_cash"]:
                try:
                    val = float(str(value).replace(",", "").replace("$", ""))
                    if val < 0:
                        return False, f"{entity_type.replace('_', ' ')} cannot be negative"

                    # Cross-validation: withholding should be less than wages
                    if entity_type == "w2_federal_withholding" and self.tax_return:
                        if self.tax_return.income.w2_forms:
                            wages = self.tax_return.income.w2_forms[-1].wages
                            if wages and val > wages:
                                return False, f"Federal withholding (${val:,.0f}) cannot exceed wages (${wages:,.0f})"

                    # Sanity check for unreasonable values
                    if entity_type == "w2_wages" and val > 50000000:  # $50M
                        return False, "Wages amount seems unusually high. Please verify."

                except (ValueError, TypeError):
                    return False, f"Invalid number format for {entity_type.replace('_', ' ')}"

            # Name validation
            if entity_type in ["first_name", "last_name"]:
                name = str(value).strip()
                if len(name) < 1:
                    return False, f"{entity_type.replace('_', ' ').title()} is required"
                if len(name) > 100:
                    return False, f"{entity_type.replace('_', ' ').title()} is too long"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _apply_extracted_entity(self, entity: ExtractedEntity):
        """Apply an extracted entity to the tax return with audit logging."""
        if not self.tax_return:
            self._initialize_tax_return()

        # Phase 2.3: Validate before applying
        is_valid, error_msg = self._validate_before_apply(entity)
        if not is_valid:
            # Add to pending clarifications instead of applying invalid data
            clarification_msg = f"⚠️ {error_msg} - Please provide correct value for {entity.entity_type.replace('_', ' ')}"
            if clarification_msg not in self.context.pending_clarifications:
                self.context.pending_clarifications.append(clarification_msg)
            return  # Don't apply invalid data

        # Convert confidence to float for audit
        confidence_map = {
            ExtractionConfidence.HIGH: 0.95,
            ExtractionConfidence.MEDIUM: 0.80,
            ExtractionConfidence.LOW: 0.60,
            ExtractionConfidence.UNCERTAIN: 0.40
        }
        confidence_score = confidence_map.get(entity.confidence, 0.5)
        source = entity.source if entity.source else "ai_chatbot"

        # Phase 1.4: Add to pending_clarifications when LOW/UNCERTAIN confidence
        if entity.confidence in [ExtractionConfidence.LOW, ExtractionConfidence.UNCERTAIN]:
            clarification_msg = f"Please verify {entity.entity_type.replace('_', ' ')}: {entity.value}"
            if clarification_msg not in self.context.pending_clarifications:
                self.context.pending_clarifications.append(clarification_msg)

        try:
            # Personal info
            if entity.entity_type == "first_name":
                old_value = self.tax_return.taxpayer.first_name
                self.tax_return.taxpayer.first_name = str(entity.value)
                self._audit_log_field_change("first_name", old_value, str(entity.value), source, confidence_score)
            elif entity.entity_type == "last_name":
                old_value = self.tax_return.taxpayer.last_name
                self.tax_return.taxpayer.last_name = str(entity.value)
                self._audit_log_field_change("last_name", old_value, str(entity.value), source, confidence_score)
            elif entity.entity_type == "middle_name":
                old_value = getattr(self.tax_return.taxpayer, 'middle_name', None)
                self.tax_return.taxpayer.middle_name = str(entity.value)
                self._audit_log_field_change("middle_name", old_value, str(entity.value), source, confidence_score)
            elif entity.entity_type == "ssn":
                old_value = self.tax_return.taxpayer.ssn
                self.tax_return.taxpayer.ssn = str(entity.value)
                self._audit_log_field_change("ssn", "***REDACTED***", "***UPDATED***", source, confidence_score)
            elif entity.entity_type == "birth_date":
                old_value = getattr(self.tax_return.taxpayer, 'date_of_birth', None)
                self.tax_return.taxpayer.date_of_birth = str(entity.value)
                self._audit_log_field_change("birth_date", old_value, str(entity.value), source, confidence_score)
            elif entity.entity_type == "phone":
                old_value = getattr(self.tax_return.taxpayer, 'phone', None)
                self.tax_return.taxpayer.phone = str(entity.value)
                self._audit_log_field_change("phone", old_value, str(entity.value), source, confidence_score)
            elif entity.entity_type == "email":
                old_value = getattr(self.tax_return.taxpayer, 'email', None)
                self.tax_return.taxpayer.email = str(entity.value)
                self._audit_log_field_change("email", old_value, str(entity.value), source, confidence_score)

            # Filing status
            elif entity.entity_type == "filing_status":
                status_map = {
                    "single": FilingStatus.SINGLE,
                    "married_filing_jointly": FilingStatus.MARRIED_JOINT,
                    "married_filing_separately": FilingStatus.MARRIED_SEPARATE,
                    "head_of_household": FilingStatus.HEAD_OF_HOUSEHOLD,
                    "qualifying_widow": FilingStatus.QUALIFYING_WIDOW
                }
                old_status = self.tax_return.taxpayer.filing_status.value if self.tax_return.taxpayer.filing_status else None
                new_status = status_map.get(str(entity.value).lower(), FilingStatus.SINGLE)
                self.tax_return.taxpayer.filing_status = new_status
                self._audit_log_field_change("filing_status", old_status, new_status.value, source, confidence_score)

            # W-2 income
            elif entity.entity_type in ["w2_wages", "w2_federal_withholding", "employer_name"]:
                # Find or create W-2 entry
                if not self.tax_return.income.w2_forms:
                    self.tax_return.income.w2_forms.append(
                        W2Info(employer_name="", wages=0, federal_tax_withheld=0)
                    )

                w2 = self.tax_return.income.w2_forms[-1]  # Use most recent

                if entity.entity_type == "w2_wages":
                    old_value = w2.wages
                    w2.wages = float(entity.value)
                    self._audit_log_income_change("w2_wages", old_value, float(entity.value), source)
                elif entity.entity_type == "w2_federal_withholding":
                    old_value = w2.federal_tax_withheld
                    w2.federal_tax_withheld = float(entity.value)
                    self._audit_log_field_change("w2_federal_withholding", old_value, float(entity.value), source, confidence_score)
                elif entity.entity_type == "employer_name":
                    old_value = w2.employer_name
                    w2.employer_name = str(entity.value)
                    self._audit_log_field_change("employer_name", old_value, str(entity.value), source, confidence_score)

            # Deductions
            elif entity.entity_type == "mortgage_interest":
                if not self.tax_return.deductions.itemized:
                    self.tax_return.deductions.itemized = ItemizedDeductions()
                old_value = getattr(self.tax_return.deductions.itemized, 'mortgage_interest', 0) or 0
                self.tax_return.deductions.itemized.mortgage_interest = float(entity.value)
                self._audit_log_field_change("mortgage_interest", old_value, float(entity.value), source, confidence_score)
            elif entity.entity_type == "property_taxes":
                if not self.tax_return.deductions.itemized:
                    self.tax_return.deductions.itemized = ItemizedDeductions()
                old_value = getattr(self.tax_return.deductions.itemized, 'property_taxes', 0) or 0
                self.tax_return.deductions.itemized.property_taxes = float(entity.value)
                self._audit_log_field_change("property_taxes", old_value, float(entity.value), source, confidence_score)
            elif entity.entity_type == "charitable_cash":
                if not self.tax_return.deductions.itemized:
                    self.tax_return.deductions.itemized = ItemizedDeductions()
                old_value = getattr(self.tax_return.deductions.itemized, 'charitable_cash', 0) or 0
                self.tax_return.deductions.itemized.charitable_cash = float(entity.value)
                self._audit_log_field_change("charitable_cash", old_value, float(entity.value), source, confidence_score)

            # Children
            elif entity.entity_type == "num_children":
                num = int(entity.value)
                # Initialize dependents list if needed
                if not hasattr(self.tax_return.taxpayer, 'dependents'):
                    self.tax_return.taxpayer.dependents = []

                # Add placeholder dependents
                while len(self.tax_return.taxpayer.dependents) < num:
                    self.tax_return.taxpayer.dependents.append(
                        Dependent(
                            first_name="",
                            last_name="",
                            relationship="child",
                            ssn="",
                            birth_date=None
                        )
                    )

            # Business type and SSTB classification (IRC §199A)
            elif entity.entity_type in ["business_type", "business_name", "business_description", "naics_code"]:
                # Store business info in context
                if entity.entity_type == "business_type":
                    self.context.business_type = str(entity.value)
                elif entity.entity_type == "business_name":
                    # Business name stored but also used for SSTB keyword matching
                    self.context.business_type = self.context.business_type or str(entity.value)
                elif entity.entity_type == "business_description":
                    self.context.business_description = str(entity.value)
                elif entity.entity_type == "naics_code":
                    self.context.naics_code = str(entity.value)

                # Run SSTB classification whenever we have business info
                self._classify_sstb()

        except (ValueError, AttributeError, TypeError) as e:
            logger.warning(f"Error applying entity {entity.entity_type}: {e}")

    def _classify_sstb(self):
        """
        Classify business as SSTB (Specified Service Trade or Business) per IRC §199A(d)(2).

        This affects the taxpayer's eligibility for the 20% QBI deduction.
        SSTBs face deduction phase-outs at higher income levels.
        """
        if not SSTB_CLASSIFIER_AVAILABLE:
            return

        # Run classification with available business info
        category = SSTBClassifier.classify_business(
            business_name=self.context.business_type,
            business_code=self.context.naics_code,
            business_description=self.context.business_description
        )

        # Store results
        self.context.sstb_category = category.value
        self.context.is_sstb = (category != SSTBCategory.NON_SSTB)

        # Generate user-friendly message explaining impact
        if self.context.is_sstb:
            category_names = {
                "health": "healthcare services",
                "law": "legal services",
                "accounting": "accounting/tax services",
                "actuarial": "actuarial services",
                "performing_arts": "performing arts",
                "consulting": "consulting services",
                "athletics": "athletics/sports",
                "financial_services": "financial services",
                "brokerage": "brokerage services",
                "trading": "trading/dealing",
                "reputation_skill": "services where principal asset is reputation/skill"
            }
            category_display = category_names.get(category.value, category.value)

            self.context.sstb_impact_message = (
                f"Your business appears to be classified as a Specified Service Trade or Business "
                f"({category_display}) under IRC §199A(d)(2). This affects your QBI deduction eligibility:\n"
                f"• If your taxable income is under the threshold ($191,950 single / $383,900 MFJ for 2025), "
                f"you can still claim the full 20% QBI deduction.\n"
                f"• Above the threshold, the deduction phases out over $50K ($100K MFJ).\n"
                f"• Above the upper threshold, SSTB income does NOT qualify for the QBI deduction."
            )
        else:
            self.context.sstb_impact_message = (
                f"Your business is NOT classified as a Specified Service Trade or Business (SSTB). "
                f"This is favorable for the QBI deduction - you may be eligible for the full 20% deduction "
                f"on qualified business income, subject only to W-2 wage and capital limitations at higher income levels."
            )

    def _calculate_running_estimate(self) -> Optional[Dict[str, Any]]:
        """
        Calculate real-time tax estimate based on current data.

        Returns a dict with refund_or_owed, total_tax, total_withholding, effective_rate.
        This gives users immediate feedback on their tax situation as they enter data.
        """
        if not CALCULATION_ENGINE_AVAILABLE:
            return None

        if not self.tax_return:
            return None

        try:
            # Run calculation with current data
            engine = FederalTaxEngine()
            breakdown = engine.calculate(self.tax_return)

            # Update context with running estimate
            self.context.running_estimate = breakdown.refund_or_owed
            self.context.running_total_tax = breakdown.total_tax
            self.context.running_total_withholding = breakdown.total_payments
            self.context.last_calculation_timestamp = datetime.now().isoformat()

            # Calculate effective tax rate (tax / AGI)
            if breakdown.agi > 0:
                self.context.running_effective_rate = round(
                    (breakdown.total_tax / breakdown.agi) * 100, 1
                )
            else:
                self.context.running_effective_rate = 0.0

            result = {
                'refund_or_owed': breakdown.refund_or_owed,
                'total_tax': breakdown.total_tax,
                'total_withholding': breakdown.total_payments,
                'effective_rate': self.context.running_effective_rate,
                'agi': breakdown.agi,
                'taxable_income': breakdown.taxable_income,
                'filing_status': breakdown.filing_status,
                'qbi_deduction': breakdown.qbi_deduction,
            }

            # Log calculation to audit trail
            self._audit_log_calculation(
                calculation_type="running_tax_estimate",
                inputs={
                    'agi': breakdown.agi,
                    'taxable_income': breakdown.taxable_income,
                    'filing_status': breakdown.filing_status
                },
                result=result
            )

            return result

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error calculating running estimate: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error in running estimate calculation: {e}")
            return None

    def get_running_estimate_message(self) -> Optional[str]:
        """
        Generate a user-friendly message about the current tax estimate.

        Returns a formatted string showing estimated refund or amount owed.
        """
        if self.context.running_estimate is None:
            return None

        estimate = self.context.running_estimate

        if estimate < 0:
            # Refund (negative means overpayment)
            return (
                f"📊 **Running Estimate**: Refund of ${abs(estimate):,.0f}\n"
                f"• Total Tax: ${self.context.running_total_tax:,.0f}\n"
                f"• Total Payments/Withholding: ${self.context.running_total_withholding:,.0f}\n"
                f"• Effective Tax Rate: {self.context.running_effective_rate:.1f}%"
            )
        elif estimate > 0:
            # Amount owed
            return (
                f"📊 **Running Estimate**: Balance Due of ${estimate:,.0f}\n"
                f"• Total Tax: ${self.context.running_total_tax:,.0f}\n"
                f"• Total Payments/Withholding: ${self.context.running_total_withholding:,.0f}\n"
                f"• Effective Tax Rate: {self.context.running_effective_rate:.1f}%"
            )
        else:
            return (
                f"📊 **Running Estimate**: Even - no refund or amount due\n"
                f"• Effective Tax Rate: {self.context.running_effective_rate:.1f}%"
            )

    def detect_tax_opportunities(self) -> List[Dict[str, Any]]:
        """
        Proactively detect tax-saving opportunities based on current data.

        This is the 10x feature - AI-powered opportunity detection that identifies
        missed deductions, eligible credits, and tax-saving strategies.

        Returns a list of opportunities with estimated savings.
        """
        if not OPPORTUNITY_DETECTOR_AVAILABLE or not self._opportunity_detector:
            return []

        if not self.tax_return:
            return []

        try:
            # Create profile from current tax return data
            profile = create_profile_from_tax_return(self.tax_return)

            # Detect opportunities
            opportunities = self._opportunity_detector.detect_opportunities(profile)

            # Store for later reference
            self._detected_opportunities = opportunities
            self._opportunities_last_checked = datetime.now().isoformat()

            # Convert to dict format for API response
            return [
                {
                    "id": opp.id,
                    "title": opp.title,
                    "description": opp.description,
                    "category": opp.category.value,
                    "priority": opp.priority.value,
                    "estimated_savings": float(opp.estimated_savings) if opp.estimated_savings else None,
                    "savings_range": {
                        "min": float(opp.savings_range[0]),
                        "max": float(opp.savings_range[1])
                    } if opp.savings_range else None,
                    "action_required": opp.action_required,
                    "irs_reference": opp.irs_reference,
                    "deadline": opp.deadline,
                    "confidence": opp.confidence,
                    "follow_up_questions": opp.follow_up_questions
                }
                for opp in opportunities
            ]

        except Exception as e:
            logger.error(f"Error detecting tax opportunities: {e}")
            return []

    def get_opportunity_summary(self) -> Dict[str, Any]:
        """Get summary of detected opportunities with total potential savings."""
        if not self._detected_opportunities:
            self.detect_tax_opportunities()

        if not self._detected_opportunities:
            return {
                "total_opportunities": 0,
                "estimated_total_savings": 0,
                "high_priority_count": 0,
                "message": "Add more information to identify tax-saving opportunities."
            }

        if OPPORTUNITY_DETECTOR_AVAILABLE and self._opportunity_detector:
            return self._opportunity_detector.get_opportunity_summary(self._detected_opportunities)

        return {"total_opportunities": len(self._detected_opportunities)}

    def get_opportunities_for_chat(self, limit: int = 5) -> str:
        """
        Get formatted opportunities string for display in chat.

        This is called during conversation to proactively show savings.
        """
        if not self._detected_opportunities:
            self.detect_tax_opportunities()

        if not self._detected_opportunities:
            return ""

        if OPPORTUNITY_DETECTOR_AVAILABLE and self._opportunity_detector:
            return self._opportunity_detector.format_opportunities_for_chat(
                self._detected_opportunities, limit=limit
            )

        return ""

    def should_show_opportunities(self) -> bool:
        """
        Determine if we should proactively show opportunities.

        Triggers when:
        - We have income data
        - We haven't shown recently
        - Significant data was just added
        """
        # Need at least some income to analyze
        if not self.tax_return or not self.tax_return.income:
            return False

        total_income = 0
        if self.tax_return.income.w2_forms:
            total_income = sum(w2.wages for w2 in self.tax_return.income.w2_forms)

        total_income += self.tax_return.income.business_income + self.tax_return.income.other_income

        # Need meaningful income
        if total_income < 10000:
            return False

        # Check if we recently showed opportunities
        if self._opportunities_last_checked:
            from datetime import datetime, timedelta
            last_check = datetime.fromisoformat(self._opportunities_last_checked)
            # Don't show more often than every 3 messages
            if len(self.context.extraction_history) % 3 != 0:
                return False

        return True

    def _analyze_document(self, image_data: str) -> DocumentIntelligence:
        """
        Analyze uploaded tax document using OCR and AI.

        This integrates with the existing OCR engine and adds AI interpretation.
        """
        # Placeholder for OCR integration
        # In production, this would:
        # 1. Use ocr_engine.py to extract text from image
        # 2. Use GPT-4o vision to identify the form type
        # 3. Extract specific fields based on form type
        # 4. Return structured data

        return DocumentIntelligence(
            document_type="unknown",
            confidence=0.0,
            extracted_fields={},
            ocr_text=None,
            warnings=["Document analysis not yet implemented"]
        )

    def _apply_document_intelligence(self, doc_intel: DocumentIntelligence):
        """Apply extracted document data to tax return."""
        # Would apply fields from document analysis
        pass

    def _detect_contradictions(self, new_entity: ExtractedEntity) -> Optional[str]:
        """
        Phase 1.5: Detect contradictions with previously extracted data.

        Checks extraction_history for same entity_type with different value.
        Flags numeric changes >10%, string changes.

        Args:
            new_entity: The newly extracted entity to check

        Returns:
            Warning message if contradiction detected, None otherwise
        """
        if not self.context.extraction_history:
            return None

        # Find previous extractions of the same entity type
        previous_extractions = [
            e for e in self.context.extraction_history
            if e.entity_type == new_entity.entity_type and e != new_entity
        ]

        if not previous_extractions:
            return None

        # Get the most recent previous extraction
        prev = previous_extractions[-1]

        # Compare values
        try:
            # Handle numeric comparisons
            if isinstance(new_entity.value, (int, float)) or isinstance(prev.value, (int, float)):
                new_val = float(str(new_entity.value).replace(",", "").replace("$", ""))
                old_val = float(str(prev.value).replace(",", "").replace("$", ""))

                if old_val != 0:
                    pct_change = abs(new_val - old_val) / abs(old_val) * 100
                    if pct_change > 10:  # More than 10% change
                        field_name = new_entity.entity_type.replace("_", " ")
                        return (
                            f"⚠️ I noticed a change in {field_name}: "
                            f"${old_val:,.0f} → ${new_val:,.0f} ({pct_change:.0f}% change). "
                            f"Which value is correct?"
                        )

            # Handle string comparisons
            elif isinstance(new_entity.value, str) and isinstance(prev.value, str):
                if new_entity.value.lower() != prev.value.lower():
                    field_name = new_entity.entity_type.replace("_", " ")
                    return (
                        f"⚠️ I noticed a change in {field_name}: "
                        f"'{prev.value}' → '{new_entity.value}'. "
                        f"Which is correct?"
                    )

        except (ValueError, TypeError, AttributeError):
            # Can't compare, skip contradiction detection
            pass

        return None

    def _detect_patterns_and_suggest(self):
        """
        Detect patterns in conversation and suggest proactive questions.

        This is what makes the agent "intelligent" - it anticipates needs.
        """
        # Clear previous suggestions
        self.context.suggested_questions = []

        # Pattern: Mentioned W-2 but no wages collected
        if "w-2" in self.context.detected_forms or "w2" in self.context.detected_forms:
            if not self.tax_return.income.w2_forms or self.tax_return.income.w2_forms[0].wages == 0:
                self.context.suggested_questions.append(
                    "What was your total wages from Box 1 of your W-2?"
                )
                self.context.suggested_questions.append(
                    "How much federal tax was withheld (Box 2)?"
                )

        # Pattern: Mentioned home purchase
        if any("home" in event or "house" in event for event in self.context.detected_life_events):
            self.context.suggested_questions.append(
                "Did you receive a Form 1098 for mortgage interest?"
            )
            self.context.suggested_questions.append(
                "Do you have property tax records from your mortgage lender?"
            )

        # Pattern: Has children but no education expenses
        if hasattr(self.tax_return.taxpayer, 'dependents') and self.tax_return.taxpayer.dependents:
            if not self.tax_return.credits.education_credit:
                self.context.suggested_questions.append(
                    "Are any of your children in college? You may qualify for education credits."
                )

        # Pattern: Self-employment income mentioned
        if self.tax_return.income.self_employment_income > 0 or self.tax_return.income.business_income > 0:
            if not self.tax_return.income.self_employment_expenses:
                self.context.suggested_questions.append(
                    "What business expenses did you have? (Mileage, supplies, home office, etc.)"
                )
            # Ask about business type for SSTB classification (affects QBI deduction)
            if self.context.is_sstb is None and not self.context.business_type:
                self.context.suggested_questions.append(
                    "What type of business or profession is this income from? (This affects your QBI deduction eligibility.)"
                )

    def _update_context(self, user_input: str, extracted_entities: List[ExtractedEntity]):
        """Update conversation context based on user input and extractions."""
        # Determine current topic based on entities
        entity_types = [e.entity_type for e in extracted_entities]

        if any("name" in et for et in entity_types):
            self.context.current_topic = "personal_info"
        elif any("w2" in et for et in entity_types):
            self.context.current_topic = "w2_income"
        elif any("mortgage" in et or "property_tax" in et for et in entity_types):
            self.context.current_topic = "deductions"
        elif any("child" in et for et in entity_types):
            self.context.current_topic = "dependents"

        # Add to discussed topics
        if self.context.current_topic not in self.context.discussed_topics:
            self.context.discussed_topics.append(self.context.current_topic)

    def _generate_contextual_response(self) -> str:
        """Generate AI response with rich CPA-level context."""

        # Get last question asked (for context)
        last_assistant_msg = ""
        if len(self.messages) >= 2:
            for msg in reversed(self.messages[:-1]):  # Exclude current user message
                if msg["role"] == "assistant":
                    last_assistant_msg = msg["content"]
                    break

        # Get current user input
        current_user_msg = self.messages[-1]["content"] if self.messages else ""

        # Generate response with OpenAI
        try:
            # Check if CPA Intelligence is available
            if CPA_INTELLIGENCE_AVAILABLE:
                # Gather session data for CPA intelligence
                session_data = {
                    'name': f"{self.tax_return.taxpayer.first_name or ''} {self.tax_return.taxpayer.last_name or ''}".strip() or None,
                    'email': getattr(self.tax_return.taxpayer, 'email', None),
                    'income': sum(w2.wages for w2 in self.tax_return.income.w2_forms) + \
                              self.tax_return.income.business_income + \
                              self.tax_return.income.other_income,
                    'filing_status': self.tax_return.taxpayer.filing_status.value if self.tax_return.taxpayer.filing_status else 'single',
                    'age': getattr(self.tax_return.taxpayer, 'age', 30),
                    'has_business': self.tax_return.income.business_income > 0,
                    'business_revenue': self.tax_return.income.business_income,
                    # SSTB Classification (IRC §199A) - affects QBI deduction
                    'business_type': self.context.business_type,
                    'is_sstb': self.context.is_sstb,
                    'sstb_category': self.context.sstb_category,
                    'sstb_impact_message': self.context.sstb_impact_message,
                    'dependents': len(self.tax_return.taxpayer.dependents) if self.tax_return.taxpayer.dependents else 0,
                    'owns_home': self.tax_return.deductions.mortgage_interest > 0 if self.tax_return.deductions.mortgage_interest else False,
                    'has_hdhp': getattr(self.tax_return, 'has_hdhp', False),
                    'has_hsa': self.tax_return.deductions.hsa_contribution > 0 if self.tax_return.deductions.hsa_contribution else False,
                    'retirement_401k': self.tax_return.deductions.retirement_401k or 0,
                    'retirement_ira': self.tax_return.deductions.traditional_ira or 0,
                    'works_from_home': self.tax_return.income.business_income > 0,  # Assume business owners work from home
                    'has_529': getattr(self.tax_return.deductions, 'education_529', 0) > 0 if hasattr(self.tax_return.deductions, 'education_529') else False,
                    'state': getattr(self.tax_return.taxpayer, 'state', ''),
                    'mortgage_interest': self.tax_return.deductions.mortgage_interest or 0,
                    'total_itemized': (
                        (self.tax_return.deductions.mortgage_interest or 0) +
                        (self.tax_return.deductions.property_tax or 0) +
                        (self.tax_return.deductions.charitable_contributions or 0)
                    ),
                    # Real-time tax estimate
                    'running_estimate': self.context.running_estimate,
                    'running_total_tax': self.context.running_total_tax,
                    'running_total_withholding': self.context.running_total_withholding,
                    'running_effective_rate': self.context.running_effective_rate,
                }

                # Convert messages to conversation history format
                conversation_history = [
                    {'role': msg['role'], 'content': msg['content']}
                    for msg in self.messages
                ]

                # Get CPA intelligence
                intelligence = get_cpa_intelligence(session_data, conversation_history)

                # Use enhanced context
                system_prompt = intelligence['enhanced_context']

                # Get low-confidence extractions from recent conversation
                low_confidence_items = [
                    entity for entity in self.context.extraction_history[-5:]
                    if entity.confidence in [ExtractionConfidence.LOW, ExtractionConfidence.UNCERTAIN]
                ]

                confidence_warnings = ""
                if low_confidence_items:
                    confidence_warnings = "\n\nLOW CONFIDENCE EXTRACTIONS (mention these to user):\n"
                    for entity in low_confidence_items:
                        confidence_warnings += f"⚠️ {entity.entity_type}: {entity.value} ({entity.confidence.value} confidence - ask user to verify)\n"

                # Phase 1.4: Include pending clarifications in system prompt
                pending_clarifications_text = ""
                if self.context.pending_clarifications:
                    pending_clarifications_text = "\n\nPENDING CLARIFICATIONS (address these with user):\n"
                    for clarification in self.context.pending_clarifications[:3]:  # Top 3
                        pending_clarifications_text += f"❓ {clarification}\n"

                # Add recent conversation context to system prompt
                system_prompt += f"""
{pending_clarifications_text}

RECENT CONVERSATION CONTEXT:
Last question you asked: {last_assistant_msg[:200] if last_assistant_msg else "None"}
User's current response: {current_user_msg}

Current extraction status:
- Current topic: {self.context.current_topic}
- Discussed topics: {', '.join(self.context.discussed_topics)}
- Detected forms: {', '.join(set(self.context.detected_forms))}
- Life events: {', '.join(set(self.context.detected_life_events))}
{confidence_warnings}

CRITICAL: If you extracted information with LOW or UNCERTAIN confidence, politely ask the user to verify it. Use phrases like:
- "Just to confirm, you mentioned [value] - is that correct?"
- "I want to make sure I have this right: [value]?"
- "Let me verify: did you say [value]?"
{self._get_personalization_context()}
"""
            else:
                # Fallback to basic context if CPA Intelligence not available
                # Get low-confidence extractions
                low_confidence_items = [
                    entity for entity in self.context.extraction_history[-5:]
                    if entity.confidence in [ExtractionConfidence.LOW, ExtractionConfidence.UNCERTAIN]
                ]

                confidence_warnings = ""
                if low_confidence_items:
                    confidence_warnings = "\n\nLOW CONFIDENCE EXTRACTIONS (ask user to verify):\n"
                    for entity in low_confidence_items:
                        confidence_warnings += f"⚠️ {entity.entity_type}: {entity.value} ({entity.confidence.value} confidence)\n"

                # Phase 1.4: Include pending clarifications
                pending_clarifications_text = ""
                if self.context.pending_clarifications:
                    pending_clarifications_text = "\n\nPENDING CLARIFICATIONS (address these):\n"
                    for clarification in self.context.pending_clarifications[:3]:
                        pending_clarifications_text += f"❓ {clarification}\n"

                system_prompt = f"""Generate a helpful, natural response.
{pending_clarifications_text}

RECENT CONVERSATION CONTEXT:
Last question you asked: {last_assistant_msg[:200] if last_assistant_msg else "None"}
User's current response: {current_user_msg}

Current conversation state:
- Current topic: {self.context.current_topic}
- Discussed topics: {', '.join(self.context.discussed_topics)}
- Detected forms: {', '.join(set(self.context.detected_forms))}
- Life events: {', '.join(set(self.context.detected_life_events))}
{confidence_warnings}

CRITICAL GUIDELINES FOR THIS RESPONSE:
1. RECOGNIZE NUMERIC ANSWERS: If user provided a number (like "84000" or "$84,000"), it's likely answering your question about income, deductions, or other tax amounts.
2. ACKNOWLEDGE NATURALLY: If user provided income, respond like: "Great! With $84,000 in income, let me calculate your estimated tax liability..."
3. EXTRACT AND RESPOND: The system has already extracted the data. Your job is to acknowledge it naturally and ask the next logical question.
4. DON'T BE GENERIC: NEVER respond with "I'm here to help with tax advisory" if the user just answered your question. Always acknowledge their specific answer first.
5. VERIFY LOW CONFIDENCE: If you extracted information with LOW or UNCERTAIN confidence, politely ask the user to verify it before proceeding.

Keep responses conversational, friendly, and professional. Always acknowledge what they just shared before moving forward."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages + [
                    {"role": "system", "content": system_prompt}
                ],
                temperature=0.6,  # Reduced from 0.7 for more consistent responses
                max_tokens=500
            )

            response_text = response.choices[0].message.content

            # Phase 1.5: Prepend contradiction warnings if any
            if hasattr(self, '_current_contradictions') and self._current_contradictions:
                contradiction_text = "\n".join(self._current_contradictions)
                response_text = f"{contradiction_text}\n\n{response_text}"
                self._current_contradictions = []  # Clear after use

            # Proactively detect and show tax-saving opportunities
            if self.should_show_opportunities():
                opportunities_text = self.get_opportunities_for_chat(limit=3)
                if opportunities_text:
                    response_text += f"\n\n---\n\n{opportunities_text}"

            return response_text
        except Exception as e:
            # Phase 2.4: User-friendly error messages
            return self._get_friendly_error_message(str(e))

    def _get_friendly_error_message(self, error: str) -> str:
        """
        Phase 2.4: Convert technical errors to user-friendly messages.

        Maps common error types to helpful, non-technical responses.
        """
        ERROR_MESSAGES = {
            "timeout": "I'm taking a moment to think. Please wait or try rephrasing your question.",
            "rate_limit": "I'm receiving a lot of requests right now. Let me try again in a moment.",
            "api_error": "I'm having trouble processing that. Let's try again - could you rephrase?",
            "connection": "I'm having trouble connecting. Please check your internet and try again.",
            "validation": "I couldn't understand that value. Could you rephrase or provide it differently?",
            "invalid": "That doesn't look quite right. Could you double-check and try again?",
            "openai": "I'm having a brief technical difficulty. Let me try a different approach.",
            "json": "I had trouble understanding your response. Could you rephrase it?",
            "key": "There's a configuration issue on my end. Please try again shortly.",
        }

        error_lower = error.lower()

        # Match error to friendly message
        for key, message in ERROR_MESSAGES.items():
            if key in error_lower:
                return message

        # Default friendly message
        return "I understand. Let me make sure I have this right - could you tell me more about that?"

    def _get_personalization_context(self) -> str:
        """
        Phase 2.5: Generate personalized context for responses.

        Uses taxpayer name, adjusts terminology for business owners,
        mentions phase-outs for high income, and is concise after 10+ messages.
        """
        context_parts = []

        # Use taxpayer name when available
        taxpayer_name = ""
        if self.tax_return and self.tax_return.taxpayer:
            first_name = self.tax_return.taxpayer.first_name
            if first_name:
                taxpayer_name = first_name
                context_parts.append(f"Address the user as {first_name}.")

        # Adjust for business owners
        is_business_owner = (
            self.tax_return and
            self.tax_return.income and
            (self.tax_return.income.business_income > 0 or
             self.tax_return.income.self_employment_income > 0)
        )
        if is_business_owner:
            context_parts.append(
                "User is a business owner/self-employed. "
                "Use business terminology: 'deductible business expenses', 'Schedule C', 'estimated taxes', 'QBI deduction'."
            )

        # High income phase-out mentions
        total_income = 0
        if self.tax_return and self.tax_return.income:
            if self.tax_return.income.w2_forms:
                total_income = sum(w2.wages for w2 in self.tax_return.income.w2_forms)
            total_income += self.tax_return.income.business_income + self.tax_return.income.other_income

        if total_income > 200000:
            context_parts.append(
                "User has high income (>$200K). "
                "Mention potential phase-outs: child tax credit, education credits, IRA deductions, "
                "and the 3.8% Net Investment Income Tax if applicable."
            )
        elif total_income > 400000:
            context_parts.append(
                "User has very high income (>$400K). "
                "Be aware of top bracket (37%), NIIT, and FICA additional Medicare tax. "
                "Emphasize tax planning strategies."
            )

        # Be concise after many messages
        message_count = len(self.messages)
        if message_count > 20:
            context_parts.append(
                "This is a longer conversation (20+ messages). "
                "Be more concise. Skip pleasantries. Get straight to the point."
            )
        elif message_count > 10:
            context_parts.append(
                "Keep responses brief. User has been engaged for a while."
            )

        # Mention filing status implications
        if self.tax_return and self.tax_return.taxpayer.filing_status:
            status = self.tax_return.taxpayer.filing_status
            if status == FilingStatus.HEAD_OF_HOUSEHOLD:
                context_parts.append(
                    "User is Head of Household - remind about qualifying person requirements if relevant."
                )
            elif status == FilingStatus.MARRIED_SEPARATE:
                context_parts.append(
                    "User is Married Filing Separately - note this has tax disadvantages "
                    "(no EITC, lower IRA limits, etc.). Only recommend if they have a reason."
                )

        if not context_parts:
            return ""

        return "\n\nPERSONALIZATION:\n" + "\n".join(f"• {p}" for p in context_parts)

    def get_extracted_summary(self) -> Dict[str, Any]:
        """Get a summary of all extracted information with confidence levels."""
        return {
            "taxpayer": {
                "name": f"{self.tax_return.taxpayer.first_name} {self.tax_return.taxpayer.last_name}",
                "ssn": self.tax_return.taxpayer.ssn,
                "filing_status": self.tax_return.taxpayer.filing_status.value if self.tax_return.taxpayer.filing_status else None
            },
            "income": {
                "w2_forms": len(self.tax_return.income.w2_forms),
                "total_wages": sum(w2.wages for w2 in self.tax_return.income.w2_forms)
            },
            "context": {
                "discussed_topics": self.context.discussed_topics,
                "detected_forms": list(set(self.context.detected_forms)),
                "life_events": list(set(self.context.detected_life_events)),
                "extractions": len(self.context.extraction_history)
            },
            "confidence_summary": self.get_confidence_summary()
        }

    def get_confidence_summary(self) -> Dict[str, Any]:
        """Get detailed confidence information for all extracted entities."""
        confidence_counts = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "uncertain": 0
        }

        needs_review = []
        recent_extractions = []

        for entity in self.context.extraction_history:
            # Count confidence levels
            confidence_counts[entity.confidence.value] += 1

            # Track items needing verification
            if entity.needs_verification or entity.confidence in [ExtractionConfidence.LOW, ExtractionConfidence.UNCERTAIN]:
                needs_review.append({
                    "entity_type": entity.entity_type,
                    "value": entity.value,
                    "confidence": entity.confidence.value,
                    "source": entity.source,
                    "context": entity.context
                })

            # Track recent extractions (last 10)
            recent_extractions.append({
                "entity_type": entity.entity_type,
                "value": entity.value,
                "confidence": entity.confidence.value,
                "confidence_icon": self._get_confidence_icon(entity.confidence),
                "source": entity.source,
                "needs_verification": entity.needs_verification
            })

        return {
            "counts": confidence_counts,
            "total_extractions": len(self.context.extraction_history),
            "needs_review": needs_review[-10:],  # Last 10 items needing review
            "recent_extractions": recent_extractions[-10:],  # Last 10 extractions
            "overall_confidence": self._calculate_overall_confidence(confidence_counts)
        }

    def _get_confidence_icon(self, confidence: ExtractionConfidence) -> str:
        """Get visual icon for confidence level."""
        icons = {
            ExtractionConfidence.HIGH: "✅",
            ExtractionConfidence.MEDIUM: "⚠️",
            ExtractionConfidence.LOW: "❌",
            ExtractionConfidence.UNCERTAIN: "❓"
        }
        return icons.get(confidence, "❓")

    def _calculate_overall_confidence(self, confidence_counts: Dict[str, int]) -> str:
        """Calculate overall confidence level."""
        total = sum(confidence_counts.values())
        if total == 0:
            return "none"

        high_pct = (confidence_counts["high"] / total) * 100

        if high_pct >= 80:
            return "high"
        elif high_pct >= 50:
            return "medium"
        else:
            return "low"

    def format_confidence_indicator(self, entity_type: str, value: Any, confidence: ExtractionConfidence) -> str:
        """Format an extracted value with confidence indicator for display."""
        icon = self._get_confidence_icon(confidence)

        if confidence == ExtractionConfidence.HIGH:
            return f"{icon} {entity_type.replace('_', ' ').title()}: {value}"
        elif confidence == ExtractionConfidence.MEDIUM:
            return f"{icon} {entity_type.replace('_', ' ').title()}: {value} (Please verify)"
        elif confidence == ExtractionConfidence.LOW:
            return f"{icon} {entity_type.replace('_', ' ').title()}: {value} (Low confidence - requires review)"
        else:
            return f"{icon} {entity_type.replace('_', ' ').title()}: {value} (Uncertain - verification required)"

    def get_tax_return(self) -> Optional[TaxReturn]:
        """Get the current tax return."""
        return self.tax_return

    def is_complete(self) -> bool:
        """Check if enough information has been collected."""
        if not self.tax_return:
            return False

        # Minimum requirements
        has_name = bool(self.tax_return.taxpayer.first_name and self.tax_return.taxpayer.last_name)
        has_ssn = bool(self.tax_return.taxpayer.ssn)
        has_filing_status = bool(self.tax_return.taxpayer.filing_status)
        has_income = bool(
            self.tax_return.income.w2_forms or
            self.tax_return.income.get_total_income() > 0
        )

        return has_name and has_ssn and has_filing_status and has_income

    def get_completion_percentage(self) -> float:
        """Calculate how complete the tax return is."""
        required_fields = {
            "first_name": bool(self.tax_return.taxpayer.first_name),
            "last_name": bool(self.tax_return.taxpayer.last_name),
            "ssn": bool(self.tax_return.taxpayer.ssn),
            "filing_status": bool(self.tax_return.taxpayer.filing_status),
            "income": bool(self.tax_return.income.get_total_income() > 0),
        }

        completed = sum(1 for v in required_fields.values() if v)
        total = len(required_fields)

        return (completed / total) * 100

    # Serialization methods (same as original)
    def get_state_for_serialization(self) -> Dict[str, Any]:
        """Get agent state for secure serialization."""
        from dataclasses import asdict, is_dataclass

        state = {
            "messages": self.messages.copy(),
            "model": self.model,
            "context": {
                "current_topic": self.context.current_topic,
                "discussed_topics": self.context.discussed_topics,
                "detected_forms": self.context.detected_forms,
                "detected_life_events": self.context.detected_life_events,
                "extraction_count": len(self.context.extraction_history)
            }
        }

        if self.tax_return:
            if hasattr(self.tax_return, 'to_dict'):
                state["tax_return"] = self.tax_return.to_dict()
            elif is_dataclass(self.tax_return):
                state["tax_return"] = asdict(self.tax_return)

        return state

    def get_audit_trail(self) -> List[Dict]:
        """
        Get the complete audit trail for this session.

        Returns a chronological list of all changes made during the session.
        """
        if not AUDIT_AVAILABLE or not self._audit_logger:
            return []

        return self._audit_logger.query(
            resource_id=self.session_id,
            limit=1000
        )

    def get_audit_summary(self) -> Dict[str, Any]:
        """
        Get a summary of audit activity for this session.

        Returns counts by action type, sources, and field types.
        """
        audit_trail = self.get_audit_trail()

        if not audit_trail:
            return {
                "session_id": self.session_id,
                "total_events": 0,
                "actions": {},
                "sources": {},
                "fields": {}
            }

        actions = {}
        sources = {}
        fields = {}

        for event in audit_trail:
            # Count by action type
            action = event.get("action", "unknown")
            actions[action] = actions.get(action, 0) + 1

            # Count by source
            details = event.get("details", {}) or {}
            source = details.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

            # Count by field
            field_name = details.get("field_name", event.get("resource_type", "unknown"))
            fields[field_name] = fields.get(field_name, 0) + 1

        return {
            "session_id": self.session_id,
            "total_events": len(audit_trail),
            "actions": actions,
            "sources": sources,
            "fields": fields,
            "first_event": audit_trail[-1]["timestamp"] if audit_trail else None,
            "last_event": audit_trail[0]["timestamp"] if audit_trail else None
        }

    def export_audit_report(self) -> Dict[str, Any]:
        """
        Export a comprehensive audit report for compliance purposes.

        Returns a structured report with timeline, summary, and all events.
        """
        audit_trail = self.get_audit_trail()
        summary = self.get_audit_summary()

        return {
            "report_type": "tax_filing_audit_trail",
            "session_id": self.session_id,
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "timeline": audit_trail,
            "taxpayer_info": {
                "name": f"{self.tax_return.taxpayer.first_name} {self.tax_return.taxpayer.last_name}".strip() if self.tax_return else "",
                "filing_status": self.tax_return.taxpayer.filing_status.value if self.tax_return and self.tax_return.taxpayer.filing_status else None
            },
            "extraction_confidence": self.get_confidence_summary() if self.context.extraction_history else None
        }
