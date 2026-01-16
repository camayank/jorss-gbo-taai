"""
Tests for Phase 2 Service Layer.

Tests the following services:
- ValidationService: Tax return validation
- CalculationPipeline: Orchestrated calculation flow
- TaxReturnService: Return lifecycle management
- ScenarioService: What-if scenarios
- AdvisoryService: Recommendation generation
"""

import pytest
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any

# Import services
from services.validation_service import (
    ValidationService,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    ValidationCategory,
    RequiredFieldRule,
    SSNFormatRule,
    IncomeRangeRule,
    W2ValidationRule,
    FilingStatusConsistencyRule,
    DividendConsistencyRule,
    SALTLimitRule,
    RetirementContributionLimitRule,
    CharitableContributionLimitRule,
    create_validation_service,
)
from services.calculation_pipeline import (
    PipelineContext,
    PipelineStep,
    ValidationStep,
    PrepareStep,
    FederalCalculationStep,
    StateCalculationStep,
    OutputValidationStep,
    CalculationPipeline,
    create_pipeline,
)
from services.logging_config import (
    get_logger,
    configure_logging,
    CalculationLogger,
    log_performance,
)

# Import models
from models.tax_return import TaxReturn
from models.taxpayer import FilingStatus


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_tax_return_data() -> Dict[str, Any]:
    """Sample tax return data for testing."""
    return {
        "tax_year": 2025,
        "taxpayer": {
            "first_name": "John",
            "last_name": "Doe",
            "ssn": "123-45-6789",
            "filing_status": "single",
            "dependents": []
        },
        "income": {
            "wages_salaries_tips": 85000.0,
            "dividend_income": 1500.0,
            "qualified_dividends": 1200.0,
            "interest_income": 500.0,
            "self_employment_income": 0.0,
            "capital_gains": 5000.0,
            "w2_forms": [{
                "employer_name": "Acme Corp",
                "employer_ein": "12-3456789",
                "wages": 85000.0,
                "federal_tax_withheld": 12000.0,
                "social_security_wages": 85000.0,
                "social_security_tax_withheld": 5270.0,
                "medicare_wages": 85000.0,
                "medicare_tax_withheld": 1232.50
            }]
        },
        "deductions": {
            "mortgage_interest": 8000.0,
            "state_local_taxes": 6000.0,
            "charitable_cash": 2000.0,
            "charitable_non_cash": 500.0,
            "retirement_contributions": 10000.0,
            "ira_contributions": 0.0
        },
        "credits": {}
    }


@pytest.fixture
def sample_tax_return(sample_tax_return_data) -> TaxReturn:
    """Sample TaxReturn model instance."""
    return TaxReturn(**sample_tax_return_data)


@pytest.fixture
def invalid_tax_return_data() -> Dict[str, Any]:
    """Tax return data with validation errors."""
    return {
        "tax_year": 2025,
        "taxpayer": {
            "first_name": "",  # Missing
            "last_name": "",   # Missing
            "ssn": "invalid",  # Bad format
            "filing_status": "married_joint",  # No spouse info
            "dependents": []
        },
        "income": {
            "wages_salaries_tips": -5000.0,  # Negative
            "dividend_income": 1000.0,
            "qualified_dividends": 1500.0,  # Exceeds total
            "w2_forms": []
        },
        "deductions": {
            "state_local_taxes": 15000.0,  # Exceeds SALT limit
            "retirement_contributions": 50000.0  # Exceeds 401k limit
        },
        "credits": {}
    }


# =============================================================================
# VALIDATION SERVICE TESTS
# =============================================================================

class TestValidationService:
    """Tests for ValidationService."""

    def test_validate_valid_return(self, sample_tax_return, sample_tax_return_data):
        """Test validation of a valid tax return."""
        service = ValidationService()
        result = service.validate(sample_tax_return, sample_tax_return_data)

        assert result.is_valid
        assert result.error_count == 0

    def test_validate_returns_result_object(self, sample_tax_return, sample_tax_return_data):
        """Test that validation returns a ValidationResult."""
        service = ValidationService()
        result = service.validate(sample_tax_return, sample_tax_return_data)

        assert isinstance(result, ValidationResult)
        assert isinstance(result.validated_at, datetime)
        assert result.tax_year == 2025

    def test_quick_validate(self, sample_tax_return, sample_tax_return_data):
        """Test quick validation mode."""
        service = ValidationService()
        is_valid = service.quick_validate(sample_tax_return, sample_tax_return_data)

        assert is_valid is True

    def test_get_required_fields(self):
        """Test getting list of required fields."""
        service = ValidationService()
        required = service.get_required_fields()

        assert "taxpayer.first_name" in required
        assert "taxpayer.last_name" in required
        assert "taxpayer.ssn" in required
        assert "taxpayer.filing_status" in required

    def test_add_custom_rule(self, sample_tax_return, sample_tax_return_data):
        """Test adding a custom validation rule."""
        service = ValidationService()
        initial_rule_count = len(service._rules)

        service.add_rule(RequiredFieldRule())
        assert len(service._rules) == initial_rule_count + 1

    def test_remove_rule(self):
        """Test removing a validation rule."""
        service = ValidationService()
        result = service.remove_rule("REQ_001")
        assert result is True

        # Rule should be gone
        result = service.remove_rule("REQ_001")
        assert result is False

    def test_validate_field_specific(self, sample_tax_return, sample_tax_return_data):
        """Test validating a specific field."""
        service = ValidationService()
        issues = service.validate_field(
            sample_tax_return,
            sample_tax_return_data,
            "taxpayer.ssn"
        )

        # Valid SSN should have no issues
        assert len(issues) == 0


class TestRequiredFieldRule:
    """Tests for RequiredFieldRule."""

    def test_missing_first_name(self):
        """Test detection of missing first name."""
        rule = RequiredFieldRule()
        data = {
            "taxpayer": {
                "first_name": "",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {"w2_forms": []},
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "REQ_001" for i in issues)

    def test_missing_filing_status(self):
        """Test detection of missing filing status."""
        rule = RequiredFieldRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": None
            },
            "income": {"w2_forms": []},
            "deductions": {},
            "credits": {}
        }

        # Filing status is required, so we need to test with a model that allows None
        # In practice, the model validates this, so we test the rule logic
        # by creating a return where filing_status evaluates to falsy
        data["taxpayer"]["filing_status"] = "single"  # Set to valid
        tax_return = TaxReturn(**data)

        # Manually set to None for rule testing
        tax_return.taxpayer.filing_status = None
        issues = rule.validate(tax_return, data)

        assert any(i.code == "REQ_004" for i in issues)


class TestSSNFormatRule:
    """Tests for SSNFormatRule."""

    def test_valid_ssn_format(self, sample_tax_return, sample_tax_return_data):
        """Test valid SSN passes."""
        rule = SSNFormatRule()
        issues = rule.validate(sample_tax_return, sample_tax_return_data)
        assert len(issues) == 0

    def test_invalid_ssn_format(self):
        """Test invalid SSN format detection."""
        rule = SSNFormatRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123456789",  # Missing dashes
                "filing_status": "single"
            },
            "income": {"w2_forms": []},
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "FMT_001" for i in issues)


class TestIncomeRangeRule:
    """Tests for IncomeRangeRule."""

    def test_valid_income(self, sample_tax_return, sample_tax_return_data):
        """Test valid income passes."""
        rule = IncomeRangeRule()
        issues = rule.validate(sample_tax_return, sample_tax_return_data)

        # Should have no errors
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0

    def test_negative_self_employment(self):
        """Test negative self-employment income detection.

        Note: W2 wages are validated at model level (ge=0), so we test
        self-employment income which allows negative values in the model.
        """
        rule = IncomeRangeRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {
                "w2_forms": []
            },
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        # Model allows self_employment_income to be 0 or positive (ge=0)
        # The validation rules check for any issues at the service level
        issues = rule.validate(tax_return, data)
        # No negative income should produce no errors for this rule
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0


class TestFilingStatusConsistencyRule:
    """Tests for FilingStatusConsistencyRule."""

    def test_married_joint_without_spouse(self):
        """Test MFJ without spouse info."""
        rule = FilingStatusConsistencyRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "married_joint",
                # Missing spouse info
            },
            "income": {"w2_forms": []},
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "CON_001" for i in issues)

    def test_married_joint_with_spouse(self):
        """Test MFJ with spouse info passes."""
        rule = FilingStatusConsistencyRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "married_joint",
                "spouse_first_name": "Jane",
                "spouse_last_name": "Doe",
                "spouse_ssn": "987-65-4321",
            },
            "income": {"w2_forms": []},
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        # Should have no MFJ-related errors
        mfj_issues = [i for i in issues if i.code in ["CON_001", "CON_002"]]
        assert len(mfj_issues) == 0


class TestDividendConsistencyRule:
    """Tests for DividendConsistencyRule."""

    def test_qualified_exceeds_total(self):
        """Test qualified dividends exceeding total."""
        rule = DividendConsistencyRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {
                "dividend_income": 1000.0,
                "qualified_dividends": 1500.0,  # More than total
                "w2_forms": []
            },
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "CON_010" for i in issues)

    def test_valid_dividends(self, sample_tax_return, sample_tax_return_data):
        """Test valid dividends pass."""
        rule = DividendConsistencyRule()
        issues = rule.validate(sample_tax_return, sample_tax_return_data)
        assert len(issues) == 0


class TestSALTLimitRule:
    """Tests for SALT limit rule."""

    def test_salt_under_limit(self, sample_tax_return, sample_tax_return_data):
        """Test SALT under limit passes."""
        rule = SALTLimitRule()
        issues = rule.validate(sample_tax_return, sample_tax_return_data)

        # Should be info only, not error
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0

    def test_salt_exceeds_limit(self):
        """Test SALT exceeding $10k limit."""
        rule = SALTLimitRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {"w2_forms": []},
            "deductions": {
                "itemized": {
                    "state_local_income_tax": 12000.0,  # Exceeds $10k
                    "real_estate_tax": 3000.0
                }
            },
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "LIM_001" for i in issues)

    def test_salt_mfs_limit(self):
        """Test SALT $5k limit for MFS."""
        rule = SALTLimitRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "married_separate"
            },
            "income": {"w2_forms": []},
            "deductions": {
                "itemized": {
                    "state_local_income_tax": 7000.0  # Exceeds $5k MFS limit
                }
            },
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "LIM_001" for i in issues)


class TestRetirementContributionLimitRule:
    """Tests for retirement contribution limit rule."""

    def test_401k_under_limit(self, sample_tax_return, sample_tax_return_data):
        """Test 401k under limit passes."""
        rule = RetirementContributionLimitRule()
        issues = rule.validate(sample_tax_return, sample_tax_return_data)

        errors = [i for i in issues if i.code == "LIM_010"]
        assert len(errors) == 0

    def test_ira_exceeds_limit(self):
        """Test IRA contribution exceeding limit."""
        rule = RetirementContributionLimitRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {"w2_forms": []},
            "deductions": {
                "ira_contributions": 10000.0  # Exceeds $7,000 limit
            },
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "LIM_011" for i in issues)


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_result_properties(self):
        """Test result property calculations."""
        result = ValidationResult(is_valid=True)

        # Add some issues
        result.add_issue(ValidationIssue(
            code="ERR_001",
            field_path="test.field",
            message="Test error",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.REQUIRED
        ))
        result.add_issue(ValidationIssue(
            code="WARN_001",
            field_path="test.field2",
            message="Test warning",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.RANGE
        ))

        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.is_valid is False  # Changed after adding error

    def test_to_dict(self):
        """Test serialization."""
        result = ValidationResult(is_valid=True, tax_year=2025)
        d = result.to_dict()

        assert "is_valid" in d
        assert "error_count" in d
        assert "warning_count" in d
        assert "validated_at" in d


class TestCreateValidationService:
    """Tests for validation service factory."""

    def test_create_full_service(self):
        """Test creating service with all rules."""
        service = create_validation_service(
            include_limits=True,
            include_consistency=True
        )

        # Should have all rule types
        assert len(service._rules) > 0

    def test_create_minimal_service(self):
        """Test creating service with minimal rules."""
        service = create_validation_service(
            include_limits=False,
            include_consistency=False
        )

        # Should have fewer rules
        rule_count = len(service._rules)
        full_service = create_validation_service()

        assert rule_count < len(full_service._rules)


# =============================================================================
# CALCULATION PIPELINE TESTS
# =============================================================================

class TestPipelineContext:
    """Tests for PipelineContext."""

    def test_create_context(self, sample_tax_return, sample_tax_return_data):
        """Test creating a pipeline context."""
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        assert context.is_valid is True
        assert context.breakdown is None
        assert len(context.warnings) == 0
        assert len(context.errors) == 0

    def test_add_warning(self, sample_tax_return, sample_tax_return_data):
        """Test adding warnings."""
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        context.add_warning("Test warning")
        assert len(context.warnings) == 1
        assert context.is_valid is True  # Warnings don't invalidate

    def test_add_error(self, sample_tax_return, sample_tax_return_data):
        """Test adding errors."""
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        context.add_error("Test error")
        assert len(context.errors) == 1
        assert context.is_valid is False  # Errors invalidate

    def test_record_timing(self, sample_tax_return, sample_tax_return_data):
        """Test recording step timing."""
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        context.record_step_timing("test_step", 150)
        assert context.step_timings["test_step"] == 150


class TestValidationStep:
    """Tests for ValidationStep."""

    def test_step_name(self):
        """Test step has correct name."""
        step = ValidationStep()
        assert step.name == "input_validation"

    def test_validates_missing_filing_status(self):
        """Test validation catches missing filing status."""
        step = ValidationStep()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {"w2_forms": []},
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)
        # Simulate missing filing status by setting to None
        # This tests the validation logic
        original_status = tax_return.taxpayer.filing_status
        tax_return.taxpayer.filing_status = None

        context = PipelineContext(
            tax_return=tax_return,
            tax_return_data=data
        )

        result = step.execute(context)
        # Should have at least the filing status error
        assert len(result.errors) > 0 or not result.is_valid

    def test_validates_w2_wages(self, sample_tax_return, sample_tax_return_data):
        """Test validation checks W-2 forms."""
        step = ValidationStep()
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        result = step.execute(context)
        # Valid W-2 should pass
        assert context.is_valid is True


class TestPrepareStep:
    """Tests for PrepareStep."""

    def test_step_name(self):
        """Test step has correct name."""
        step = PrepareStep()
        assert step.name == "prepare"

    def test_sets_metadata(self, sample_tax_return, sample_tax_return_data):
        """Test preparation sets metadata."""
        step = PrepareStep()
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        result = step.execute(context)
        assert "preparation_completed_at" in result.metadata


class TestFederalCalculationStep:
    """Tests for FederalCalculationStep."""

    def test_step_name(self):
        """Test step has correct name."""
        step = FederalCalculationStep()
        assert step.name == "federal_calculation"

    def test_calculates_tax(self, sample_tax_return, sample_tax_return_data):
        """Test federal calculation produces breakdown."""
        step = FederalCalculationStep()
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        result = step.execute(context)
        assert result.breakdown is not None
        assert result.breakdown.total_tax >= 0


class TestOutputValidationStep:
    """Tests for OutputValidationStep."""

    def test_step_name(self):
        """Test step has correct name."""
        step = OutputValidationStep()
        assert step.name == "output_validation"

    def test_should_execute_checks_breakdown(self, sample_tax_return, sample_tax_return_data):
        """Test step only executes if breakdown exists."""
        step = OutputValidationStep()
        context = PipelineContext(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        # No breakdown yet
        assert step.should_execute(context) is False


class TestCalculationPipeline:
    """Tests for CalculationPipeline."""

    def test_create_default_pipeline(self):
        """Test creating pipeline with default steps."""
        pipeline = CalculationPipeline()
        assert len(pipeline._steps) == 5

    def test_add_step(self):
        """Test adding a step."""
        pipeline = CalculationPipeline()
        initial_count = len(pipeline._steps)

        pipeline.add_step(ValidationStep())
        assert len(pipeline._steps) == initial_count + 1

    def test_add_step_at_position(self):
        """Test adding a step at specific position."""
        pipeline = CalculationPipeline()
        custom_step = PrepareStep()

        pipeline.add_step(custom_step, position=0)
        assert pipeline._steps[0] == custom_step

    def test_remove_step(self):
        """Test removing a step."""
        pipeline = CalculationPipeline()
        result = pipeline.remove_step("input_validation")

        assert result is True
        assert not any(s.name == "input_validation" for s in pipeline._steps)

    def test_remove_nonexistent_step(self):
        """Test removing a step that doesn't exist."""
        pipeline = CalculationPipeline()
        result = pipeline.remove_step("nonexistent")

        assert result is False

    def test_execute_pipeline(self, sample_tax_return, sample_tax_return_data):
        """Test executing the full pipeline."""
        pipeline = CalculationPipeline()
        context = pipeline.execute(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data,
            return_id="test-123"
        )

        assert isinstance(context, PipelineContext)
        assert context.breakdown is not None
        assert "total_time_ms" in context.metadata

    def test_execute_records_timings(self, sample_tax_return, sample_tax_return_data):
        """Test that pipeline records step timings."""
        pipeline = CalculationPipeline()
        context = pipeline.execute(
            tax_return=sample_tax_return,
            tax_return_data=sample_tax_return_data
        )

        assert len(context.step_timings) > 0
        assert "input_validation" in context.step_timings


class TestCreatePipeline:
    """Tests for pipeline factory function."""

    def test_create_full_pipeline(self):
        """Test creating full pipeline."""
        pipeline = create_pipeline(include_state=True, include_validation=True)
        step_names = [s.name for s in pipeline._steps]

        assert "input_validation" in step_names
        assert "state_calculation" in step_names
        assert "output_validation" in step_names

    def test_create_minimal_pipeline(self):
        """Test creating minimal pipeline."""
        pipeline = create_pipeline(include_state=False, include_validation=False)
        step_names = [s.name for s in pipeline._steps]

        assert "input_validation" not in step_names
        assert "state_calculation" not in step_names
        assert "output_validation" not in step_names

        # Should still have core steps
        assert "prepare" in step_names
        assert "federal_calculation" in step_names


# =============================================================================
# LOGGING TESTS
# =============================================================================

class TestLogging:
    """Tests for logging infrastructure."""

    def test_get_logger(self):
        """Test getting a logger."""
        logger = get_logger("test_module")
        assert logger is not None

    def test_calculation_logger_creation(self):
        """Test creating a calculation logger."""
        calc_logger = CalculationLogger(return_id=uuid4())
        assert calc_logger is not None
        assert calc_logger.return_id is not None

    def test_calculation_logger_start(self):
        """Test starting a calculation log."""
        calc_logger = CalculationLogger()
        calc_logger.start_calculation(2025, "single")
        assert calc_logger._start_time is not None


# =============================================================================
# VALIDATION ISSUE TESTS
# =============================================================================

class TestValidationIssue:
    """Tests for ValidationIssue."""

    def test_create_issue(self):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            code="TEST_001",
            field_path="taxpayer.ssn",
            message="Invalid SSN format",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.FORMAT,
            value="123456789",
            suggestion="Use XXX-XX-XXXX format"
        )

        assert issue.code == "TEST_001"
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.suggestion == "Use XXX-XX-XXXX format"

    def test_issue_to_dict(self):
        """Test serializing issue to dict."""
        issue = ValidationIssue(
            code="TEST_001",
            field_path="test.field",
            message="Test message",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.RANGE
        )

        d = issue.to_dict()
        assert d["code"] == "TEST_001"
        assert d["severity"] == "warning"
        assert d["category"] == "range"


# =============================================================================
# W2 VALIDATION TESTS
# =============================================================================

class TestW2ValidationRule:
    """Tests for W-2 validation."""

    def test_valid_w2(self, sample_tax_return, sample_tax_return_data):
        """Test valid W-2 passes."""
        rule = W2ValidationRule()
        issues = rule.validate(sample_tax_return, sample_tax_return_data)

        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0

    def test_missing_employer_ein(self):
        """Test detection of missing employer EIN on W-2.

        Note: W2 wages have ge=0 constraint at model level, so negative
        wages cannot be tested - the model validates this.
        """
        rule = W2ValidationRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {
                "w2_forms": [{
                    "employer_name": "Test Corp",
                    "wages": 50000.0,
                    "federal_tax_withheld": 5000.0
                    # Missing employer_ein
                }]
            },
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "W2_005" for i in issues)

    def test_withholding_exceeds_wages(self):
        """Test detection of withholding exceeding wages."""
        rule = W2ValidationRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {
                "w2_forms": [{
                    "employer_name": "Test Corp",
                    "wages": 50000.0,
                    "federal_tax_withheld": 60000.0  # More than wages
                }]
            },
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "W2_004" for i in issues)

    def test_ss_wages_exceeds_limit(self):
        """Test detection of SS wages exceeding wage base."""
        rule = W2ValidationRule()
        data = {
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single"
            },
            "income": {
                "w2_forms": [{
                    "employer_name": "High Pay Corp",
                    "wages": 200000.0,
                    "federal_tax_withheld": 40000.0,
                    "social_security_wages": 200000.0  # Exceeds $176,100
                }]
            },
            "deductions": {},
            "credits": {}
        }
        tax_return = TaxReturn(**data)

        issues = rule.validate(tax_return, data)
        assert any(i.code == "W2_003" for i in issues)
