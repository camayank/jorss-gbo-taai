"""Questionnaire Engine.

Core engine for managing the guided questionnaire flow with smart
question routing, validation, and conditional logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
import re
from datetime import date


class QuestionType(Enum):
    """Types of questions."""
    TEXT = "text"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    BOOLEAN = "boolean"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    SSN = "ssn"
    EIN = "ein"
    PHONE = "phone"
    EMAIL = "email"
    ADDRESS = "address"
    PERCENTAGE = "percentage"


class ValidationRule(Enum):
    """Common validation rules."""
    REQUIRED = "required"
    POSITIVE = "positive"
    NON_NEGATIVE = "non_negative"
    PERCENTAGE_RANGE = "percentage_range"
    VALID_SSN = "valid_ssn"
    VALID_EIN = "valid_ein"
    VALID_EMAIL = "valid_email"
    VALID_PHONE = "valid_phone"
    VALID_DATE = "valid_date"
    FUTURE_DATE = "future_date"
    PAST_DATE = "past_date"
    MAX_LENGTH = "max_length"
    MIN_LENGTH = "min_length"


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class Choice:
    """A choice option for single/multi choice questions."""
    value: str
    label: str
    description: Optional[str] = None
    help_text: Optional[str] = None
    triggers_followup: Optional[str] = None  # Question ID to show if selected
    exclusive: bool = False  # For multi-choice: selecting this deselects others


@dataclass
class Question:
    """A single question in the questionnaire."""
    id: str
    text: str
    question_type: QuestionType
    group_id: Optional[str] = None

    # Display properties
    help_text: Optional[str] = None
    placeholder: Optional[str] = None
    prefix: Optional[str] = None  # e.g., "$" for currency
    suffix: Optional[str] = None  # e.g., "%" for percentage

    # Choice options (for single/multi choice)
    choices: List[Choice] = field(default_factory=list)

    # Validation
    required: bool = True
    validation_rules: List[ValidationRule] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    regex_pattern: Optional[str] = None

    # Conditional display
    show_if: Optional[Dict[str, Any]] = None  # Condition to show this question
    hide_if: Optional[Dict[str, Any]] = None  # Condition to hide this question

    # Data mapping
    data_path: Optional[str] = None  # Path in tax return model (e.g., "income.wages")
    transform: Optional[Callable] = None  # Transform function for the answer

    # Default value
    default_value: Optional[Any] = None

    # IRS reference
    irs_form: Optional[str] = None
    irs_line: Optional[str] = None

    def validate(self, answer: Any) -> ValidationResult:
        """Validate an answer against this question's rules."""
        errors = []
        warnings = []

        # Check required
        if self.required and (answer is None or answer == "" or answer == []):
            return ValidationResult(False, "This field is required")

        # Skip further validation if empty and not required
        if answer is None or answer == "" or answer == []:
            return ValidationResult(True)

        # Type-specific validation
        if self.question_type == QuestionType.NUMBER:
            try:
                num = float(answer)
                if self.min_value is not None and num < self.min_value:
                    errors.append(f"Value must be at least {self.min_value}")
                if self.max_value is not None and num > self.max_value:
                    errors.append(f"Value must be at most {self.max_value}")
            except (ValueError, TypeError):
                errors.append("Please enter a valid number")

        elif self.question_type == QuestionType.CURRENCY:
            try:
                # Remove currency symbols and commas
                cleaned = str(answer).replace("$", "").replace(",", "")
                num = float(cleaned)
                if num < 0 and ValidationRule.NON_NEGATIVE in self.validation_rules:
                    errors.append("Value cannot be negative")
            except (ValueError, TypeError):
                errors.append("Please enter a valid dollar amount")

        elif self.question_type == QuestionType.SSN:
            if not self._validate_ssn(str(answer)):
                errors.append("Please enter a valid SSN (XXX-XX-XXXX)")

        elif self.question_type == QuestionType.EIN:
            if not self._validate_ein(str(answer)):
                errors.append("Please enter a valid EIN (XX-XXXXXXX)")

        elif self.question_type == QuestionType.EMAIL:
            if not self._validate_email(str(answer)):
                errors.append("Please enter a valid email address")

        elif self.question_type == QuestionType.PHONE:
            if not self._validate_phone(str(answer)):
                errors.append("Please enter a valid phone number")

        elif self.question_type == QuestionType.DATE:
            date_obj = self._parse_date(answer)
            if date_obj is None:
                errors.append("Please enter a valid date (MM/DD/YYYY)")
            else:
                today = date.today()
                if ValidationRule.PAST_DATE in self.validation_rules and date_obj > today:
                    errors.append("Date must be in the past")
                if ValidationRule.FUTURE_DATE in self.validation_rules and date_obj < today:
                    errors.append("Date must be in the future")

        elif self.question_type == QuestionType.PERCENTAGE:
            try:
                pct = float(str(answer).replace("%", ""))
                if pct < 0 or pct > 100:
                    errors.append("Percentage must be between 0 and 100")
            except (ValueError, TypeError):
                errors.append("Please enter a valid percentage")

        elif self.question_type == QuestionType.SINGLE_CHOICE:
            valid_values = [c.value for c in self.choices]
            if answer not in valid_values:
                errors.append("Please select a valid option")

        elif self.question_type == QuestionType.MULTI_CHOICE:
            valid_values = [c.value for c in self.choices]
            if isinstance(answer, list):
                for a in answer:
                    if a not in valid_values:
                        errors.append(f"Invalid option: {a}")

        # Custom regex pattern
        if self.regex_pattern and not re.match(self.regex_pattern, str(answer)):
            errors.append("Please enter a valid value")

        # Length validation for text
        if self.question_type == QuestionType.TEXT:
            if self.min_length and len(str(answer)) < self.min_length:
                errors.append(f"Must be at least {self.min_length} characters")
            if self.max_length and len(str(answer)) > self.max_length:
                errors.append(f"Must be at most {self.max_length} characters")

        if errors:
            return ValidationResult(False, errors[0], warnings)
        return ValidationResult(True, None, warnings)

    def _validate_ssn(self, ssn: str) -> bool:
        """Validate SSN format."""
        pattern = r"^\d{3}-?\d{2}-?\d{4}$"
        return bool(re.match(pattern, ssn))

    def _validate_ein(self, ein: str) -> bool:
        """Validate EIN format."""
        pattern = r"^\d{2}-?\d{7}$"
        return bool(re.match(pattern, ein))

    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _validate_phone(self, phone: str) -> bool:
        """Validate phone format."""
        # Remove common formatting characters
        cleaned = re.sub(r"[\s\-\(\)\.]", "", phone)
        return len(cleaned) >= 10 and cleaned.isdigit()

    def _parse_date(self, date_value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if isinstance(date_value, date):
            return date_value

        date_str = str(date_value)
        formats = ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"]

        for fmt in formats:
            try:
                return date.fromisoformat(date_str) if "-" in date_str else None
            except ValueError:
                pass

            try:
                from datetime import datetime
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None


@dataclass
class QuestionGroup:
    """A group of related questions."""
    id: str
    title: str
    description: Optional[str] = None
    icon: Optional[str] = None  # Icon name for UI
    questions: List[Question] = field(default_factory=list)

    # Display
    order: int = 0
    estimated_time: Optional[str] = None  # e.g., "2-3 minutes"

    # Conditional display
    show_if: Optional[Dict[str, Any]] = None
    hide_if: Optional[Dict[str, Any]] = None

    # Progress tracking
    is_required: bool = True
    completion_percentage: float = 0.0


@dataclass
class QuestionnaireState:
    """Current state of the questionnaire."""
    current_group_index: int = 0
    current_question_index: int = 0
    answers: Dict[str, Any] = field(default_factory=dict)
    completed_groups: List[str] = field(default_factory=list)
    skipped_questions: List[str] = field(default_factory=list)
    validation_errors: Dict[str, str] = field(default_factory=dict)
    started_at: Optional[str] = None
    last_updated: Optional[str] = None


class QuestionnaireEngine:
    """
    Engine for managing questionnaire flow.

    Handles question routing, validation, conditional logic,
    and state management for the tax interview process.
    """

    def __init__(self):
        """Initialize the questionnaire engine."""
        self._groups: List[QuestionGroup] = []
        self._questions: Dict[str, Question] = {}
        self._state = QuestionnaireState()

    def add_group(self, group: QuestionGroup) -> None:
        """Add a question group."""
        self._groups.append(group)
        self._groups.sort(key=lambda g: g.order)

        for question in group.questions:
            question.group_id = group.id
            self._questions[question.id] = question

    def add_question(self, group_id: str, question: Question) -> None:
        """Add a question to a specific group."""
        for group in self._groups:
            if group.id == group_id:
                question.group_id = group_id
                group.questions.append(question)
                self._questions[question.id] = question
                return
        raise ValueError(f"Group {group_id} not found")

    def get_current_group(self) -> Optional[QuestionGroup]:
        """Get the current question group."""
        visible_groups = self._get_visible_groups()
        if self._state.current_group_index < len(visible_groups):
            return visible_groups[self._state.current_group_index]
        return None

    def get_current_question(self) -> Optional[Question]:
        """Get the current question."""
        group = self.get_current_group()
        if not group:
            return None

        visible_questions = self._get_visible_questions(group)
        if self._state.current_question_index < len(visible_questions):
            return visible_questions[self._state.current_question_index]
        return None

    def get_all_questions_for_group(self, group_id: str) -> List[Question]:
        """Get all visible questions for a group."""
        for group in self._groups:
            if group.id == group_id:
                return self._get_visible_questions(group)
        return []

    def answer_question(self, question_id: str, answer: Any) -> ValidationResult:
        """Submit an answer to a question."""
        if question_id not in self._questions:
            return ValidationResult(False, "Question not found")

        question = self._questions[question_id]
        result = question.validate(answer)

        if result.is_valid:
            self._state.answers[question_id] = answer
            if question_id in self._state.validation_errors:
                del self._state.validation_errors[question_id]
        else:
            self._state.validation_errors[question_id] = result.error_message or ""

        return result

    def get_answer(self, question_id: str) -> Optional[Any]:
        """Get the answer to a question."""
        return self._state.answers.get(question_id)

    def next_question(self) -> Optional[Question]:
        """Move to the next question."""
        group = self.get_current_group()
        if not group:
            return None

        visible_questions = self._get_visible_questions(group)

        # Try next question in current group
        self._state.current_question_index += 1
        if self._state.current_question_index < len(visible_questions):
            return visible_questions[self._state.current_question_index]

        # Move to next group
        return self.next_group()

    def previous_question(self) -> Optional[Question]:
        """Move to the previous question."""
        # Try previous question in current group
        if self._state.current_question_index > 0:
            self._state.current_question_index -= 1
            return self.get_current_question()

        # Move to previous group
        return self.previous_group()

    def next_group(self) -> Optional[Question]:
        """Move to the next question group."""
        visible_groups = self._get_visible_groups()

        # Mark current group as completed
        current_group = self.get_current_group()
        if current_group and current_group.id not in self._state.completed_groups:
            self._state.completed_groups.append(current_group.id)

        self._state.current_group_index += 1
        self._state.current_question_index = 0

        if self._state.current_group_index < len(visible_groups):
            return self.get_current_question()

        return None  # Questionnaire complete

    def previous_group(self) -> Optional[Question]:
        """Move to the previous question group."""
        if self._state.current_group_index > 0:
            self._state.current_group_index -= 1
            group = self.get_current_group()
            if group:
                visible_questions = self._get_visible_questions(group)
                self._state.current_question_index = len(visible_questions) - 1
            return self.get_current_question()
        return None

    def skip_question(self, question_id: str) -> bool:
        """Skip a question (if not required)."""
        if question_id not in self._questions:
            return False

        question = self._questions[question_id]
        if question.required:
            return False

        self._state.skipped_questions.append(question_id)
        return True

    def get_progress(self) -> Dict[str, Any]:
        """Get questionnaire progress."""
        visible_groups = self._get_visible_groups()
        total_groups = len(visible_groups)
        completed_groups = len(self._state.completed_groups)

        # Count questions
        total_questions = 0
        answered_questions = 0
        for group in visible_groups:
            visible_questions = self._get_visible_questions(group)
            total_questions += len(visible_questions)
            for q in visible_questions:
                if q.id in self._state.answers:
                    answered_questions += 1

        return {
            "total_groups": total_groups,
            "completed_groups": completed_groups,
            "current_group_index": self._state.current_group_index,
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "percentage_complete": (
                (answered_questions / total_questions * 100) if total_questions > 0 else 0
            ),
            "groups_progress": [
                {
                    "id": g.id,
                    "title": g.title,
                    "is_complete": g.id in self._state.completed_groups,
                    "is_current": i == self._state.current_group_index,
                    "questions_answered": sum(
                        1 for q in self._get_visible_questions(g)
                        if q.id in self._state.answers
                    ),
                    "questions_total": len(self._get_visible_questions(g)),
                }
                for i, g in enumerate(visible_groups)
            ],
        }

    def get_all_answers(self) -> Dict[str, Any]:
        """Get all answers."""
        return self._state.answers.copy()

    def set_answers(self, answers: Dict[str, Any]) -> Dict[str, ValidationResult]:
        """Set multiple answers at once, returning validation results."""
        results = {}
        for question_id, answer in answers.items():
            results[question_id] = self.answer_question(question_id, answer)
        return results

    def is_complete(self) -> bool:
        """Check if questionnaire is complete."""
        visible_groups = self._get_visible_groups()

        for group in visible_groups:
            if not group.is_required:
                continue

            visible_questions = self._get_visible_questions(group)
            for question in visible_questions:
                if question.required and question.id not in self._state.answers:
                    return False

        return True

    def get_incomplete_required_questions(self) -> List[Question]:
        """Get list of required questions that haven't been answered."""
        incomplete = []
        visible_groups = self._get_visible_groups()

        for group in visible_groups:
            visible_questions = self._get_visible_questions(group)
            for question in visible_questions:
                if question.required and question.id not in self._state.answers:
                    incomplete.append(question)

        return incomplete

    def reset(self) -> None:
        """Reset the questionnaire state."""
        self._state = QuestionnaireState()

    def _get_visible_groups(self) -> List[QuestionGroup]:
        """Get groups that should be visible based on conditions."""
        visible = []
        for group in self._groups:
            if self._evaluate_condition(group.show_if, default=True) and \
               not self._evaluate_condition(group.hide_if, default=False):
                visible.append(group)
        return visible

    def _get_visible_questions(self, group: QuestionGroup) -> List[Question]:
        """Get questions that should be visible based on conditions."""
        visible = []
        for question in group.questions:
            if self._evaluate_condition(question.show_if, default=True) and \
               not self._evaluate_condition(question.hide_if, default=False):
                visible.append(question)
        return visible

    def _evaluate_condition(
        self, condition: Optional[Dict[str, Any]], default: bool = True
    ) -> bool:
        """Evaluate a condition against current answers."""
        if condition is None:
            return default

        # Handle different condition types
        if "question_id" in condition:
            # Simple equality check
            q_id = condition["question_id"]
            expected = condition.get("equals")
            actual = self._state.answers.get(q_id)

            if expected is not None:
                return actual == expected

            # Check for not equals
            not_equals = condition.get("not_equals")
            if not_equals is not None:
                return actual != not_equals

            # Check for in list
            in_list = condition.get("in")
            if in_list is not None:
                return actual in in_list

            # Check for contains (for multi-choice)
            contains = condition.get("contains")
            if contains is not None:
                if isinstance(actual, list):
                    return contains in actual
                return False

            # Check for answered (any value)
            if condition.get("answered"):
                return actual is not None and actual != ""

        # Handle AND conditions
        if "and" in condition:
            return all(
                self._evaluate_condition(c, default=True)
                for c in condition["and"]
            )

        # Handle OR conditions
        if "or" in condition:
            return any(
                self._evaluate_condition(c, default=False)
                for c in condition["or"]
            )

        # Handle NOT condition
        if "not" in condition:
            return not self._evaluate_condition(condition["not"], default=True)

        return default

    def export_state(self) -> Dict[str, Any]:
        """Export questionnaire state for persistence."""
        return {
            "current_group_index": self._state.current_group_index,
            "current_question_index": self._state.current_question_index,
            "answers": self._state.answers,
            "completed_groups": self._state.completed_groups,
            "skipped_questions": self._state.skipped_questions,
            "validation_errors": self._state.validation_errors,
        }

    def import_state(self, state: Dict[str, Any]) -> None:
        """Import questionnaire state from persistence."""
        self._state.current_group_index = state.get("current_group_index", 0)
        self._state.current_question_index = state.get("current_question_index", 0)
        self._state.answers = state.get("answers", {})
        self._state.completed_groups = state.get("completed_groups", [])
        self._state.skipped_questions = state.get("skipped_questions", [])
        self._state.validation_errors = state.get("validation_errors", {})
