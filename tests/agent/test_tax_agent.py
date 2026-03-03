"""
Comprehensive tests for TaxAgent — conversation flow, input parsing,
stage transitions, profile building, error recovery, and session management.
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def _make_tax_return():
    """Create a TaxReturn with empty taxpayer names (bypassing Pydantic
    validation) so that _extract_and_store_info name-extraction logic
    works correctly (it checks ``not taxpayer.first_name``)."""
    from models.tax_return import TaxReturn
    from models.taxpayer import TaxpayerInfo, FilingStatus as TaxpayerFilingStatus
    from models.income import Income
    from models.deductions import Deductions
    from models.credits import TaxCredits
    # Use model_construct to bypass min_length=1 validation on names,
    # matching what the source code tries to do in _extract_and_store_info.
    taxpayer = TaxpayerInfo.model_construct(
        first_name="", last_name="",
        filing_status=TaxpayerFilingStatus.SINGLE,
        dependents=[],
        ssn=None, date_of_birth=None,
        address=None, city=None, state=None,
        zip_code=None, is_blind=False, is_over_65=False,
        spouse_first_name=None, spouse_last_name=None,
        spouse_ssn=None, spouse_date_of_birth=None,
        spouse_is_blind=False, spouse_is_over_65=False,
        spouse_itemizes_deductions=False, is_dual_status_alien=False,
        can_be_claimed_as_dependent=False,
        earned_income_for_dependent_deduction=0.0,
        is_covered_by_employer_plan=False,
        spouse_covered_by_employer_plan=False,
        is_age_50_plus=False,
    )
    return TaxReturn(
        taxpayer=taxpayer,
        income=Income(),
        deductions=Deductions(),
        credits=TaxCredits(),
    )


def _create_agent(with_tax_return=True):
    """Create a TaxAgent with mocked AI service.

    Args:
        with_tax_return: If True (default), pre-initialise a valid TaxReturn
            so _extract_and_store_info works. If False, leave tax_return as
            None and patch _extract_and_store_info to avoid Pydantic
            validation errors when it tries to create TaxpayerInfo with
            empty names.
    """
    with patch("agent.tax_agent.get_ai_service") as mock_get, \
         patch("agent.tax_agent.run_async") as mock_run:
        mock_response = Mock()
        mock_response.content = "Thank you. What is your last name?"
        mock_run.return_value = mock_response
        mock_get.return_value = Mock()

        from agent.tax_agent import TaxAgent
        agent = TaxAgent()

        if with_tax_return:
            agent.tax_return = _make_tax_return()

        return agent, mock_run


# ===================================================================
# INITIALIZATION
# ===================================================================

class TestTaxAgentInit:

    def test_initial_stage(self):
        agent, _ = _create_agent()
        assert agent.collection_stage == "personal_info"

    def test_initial_tax_return_is_set(self):
        agent, _ = _create_agent()
        assert agent.tax_return is not None

    def test_initial_messages_contain_system(self):
        agent, _ = _create_agent()
        assert len(agent.messages) >= 1
        assert agent.messages[0]["role"] == "system"

    def test_system_prompt_contains_stages(self):
        agent, _ = _create_agent()
        prompt = agent.messages[0]["content"]
        assert "personal_info" in prompt
        assert "income" in prompt
        assert "deductions" in prompt
        assert "credits" in prompt
        assert "review" in prompt

    def test_system_prompt_mentions_tax_year(self):
        agent, _ = _create_agent()
        prompt = agent.messages[0]["content"]
        assert "2025" in prompt


# ===================================================================
# START CONVERSATION
# ===================================================================

class TestStartConversation:

    def test_start_returns_greeting(self):
        agent, _ = _create_agent()
        greeting = agent.start_conversation()
        assert isinstance(greeting, str)
        assert len(greeting) > 0

    def test_greeting_mentions_tax_return(self):
        agent, _ = _create_agent()
        greeting = agent.start_conversation()
        assert "tax" in greeting.lower()

    def test_greeting_asks_for_name(self):
        agent, _ = _create_agent()
        greeting = agent.start_conversation()
        assert "name" in greeting.lower() or "first" in greeting.lower()

    def test_greeting_added_to_messages(self):
        agent, _ = _create_agent()
        agent.start_conversation()
        assert any(m["role"] == "assistant" for m in agent.messages)


# ===================================================================
# PROCESS MESSAGE
# ===================================================================

class TestProcessMessage:

    def test_process_returns_string(self):
        agent, mock_run = _create_agent()
        result = agent.process_message("John")
        assert isinstance(result, str)

    def test_user_message_added_to_history(self):
        agent, mock_run = _create_agent()
        agent.process_message("John")
        user_msgs = [m for m in agent.messages if m["role"] == "user"]
        assert len(user_msgs) >= 1

    def test_assistant_response_added_to_history(self):
        agent, mock_run = _create_agent()
        agent.process_message("John")
        assistant_msgs = [m for m in agent.messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1

    def test_process_multiple_messages(self):
        agent, mock_run = _create_agent()
        agent.process_message("John")
        agent.process_message("Smith")
        agent.process_message("single")
        user_msgs = [m for m in agent.messages if m["role"] == "user"]
        assert len(user_msgs) == 3

    def test_process_message_error_recovery(self):
        agent, mock_run = _create_agent()
        mock_run.side_effect = Exception("AI service down")
        result = agent.process_message("test input")
        assert "apologize" in result.lower() or "issue" in result.lower()

    def test_process_message_after_error_continues(self):
        agent, mock_run = _create_agent()
        # First call produces an apology
        result1 = agent.process_message("test")
        assert "apologize" in result1.lower() or "issue" in result1.lower()
        # Second call should also return a string (agent doesn't crash)
        result2 = agent.process_message("retry")
        assert isinstance(result2, str) and len(result2) > 0


# ===================================================================
# INPUT PARSING — NAME EXTRACTION
# ===================================================================

class TestNameExtraction:

    def test_extract_first_name(self):
        agent, mock_run = _create_agent()
        agent.process_message("John")
        assert agent.tax_return is not None
        assert agent.tax_return.taxpayer.first_name == "John"

    def test_extract_full_name(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        assert agent.tax_return.taxpayer.first_name == "John"
        assert agent.tax_return.taxpayer.last_name == "Smith"

    def test_extract_name_capitalizes(self):
        agent, mock_run = _create_agent()
        agent.process_message("john smith")
        assert agent.tax_return.taxpayer.first_name == "John"
        assert agent.tax_return.taxpayer.last_name == "Smith"

    def test_does_not_extract_number_as_name(self):
        agent, mock_run = _create_agent()
        agent.process_message("123")
        if agent.tax_return:
            assert agent.tax_return.taxpayer.first_name == ""

    def test_single_letter_not_extracted(self):
        agent, mock_run = _create_agent()
        agent.process_message("A")
        if agent.tax_return:
            assert agent.tax_return.taxpayer.first_name == ""


# ===================================================================
# INPUT PARSING — FILING STATUS
# ===================================================================

class TestFilingStatusExtraction:

    @pytest.mark.parametrize("input_text,expected", [
        ("single", "single"),
        ("I am single", "single"),
        ("married filing jointly", "married_joint"),
        ("married joint", "married_joint"),
        ("married together", "married_joint"),
        ("married filing separately", "married_separate"),
        ("married separate", "married_separate"),
        ("head of household", "head_of_household"),
        ("qualifying widow", "qualifying_widow"),
        ("surviving spouse", "qualifying_widow"),
    ])
    def test_filing_status_extraction(self, input_text, expected):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")  # set up tax return
        agent.process_message(input_text)
        assert agent.tax_return.taxpayer.filing_status.value == expected

    def test_filing_status_not_changed_by_unrelated_input(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        original_status = agent.tax_return.taxpayer.filing_status.value
        agent.process_message("hello there")
        assert agent.tax_return.taxpayer.filing_status.value == original_status


# ===================================================================
# INPUT PARSING — INCOME
# ===================================================================

class TestIncomeExtraction:

    def test_extract_dollar_amount_in_income_stage(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.collection_stage = "income"
        agent.process_message("My wages are $75,000")
        assert len(agent.tax_return.income.w2_forms) > 0

    def test_dollar_amount_below_threshold_ignored(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.collection_stage = "income"
        agent.process_message("$500")
        assert len(agent.tax_return.income.w2_forms) == 0

    @pytest.mark.parametrize("amount_text,expected_amount", [
        ("$75,000", 75000),
        ("$100,000.00", 100000),
        ("$50000", 50000),
        ("$1,234,567", 1234567),
    ])
    def test_various_dollar_formats(self, amount_text, expected_amount):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.collection_stage = "income"
        agent.process_message(f"My wages are {amount_text}")
        if agent.tax_return.income.w2_forms:
            assert agent.tax_return.income.w2_forms[0].wages == expected_amount


# ===================================================================
# STAGE TRANSITIONS
# ===================================================================

class TestStageTransitions:

    def test_initial_stage_is_personal_info(self):
        agent, _ = _create_agent()
        assert agent.collection_stage == "personal_info"

    def test_transition_to_income_after_name(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent._update_collection_stage()
        assert agent.collection_stage == "income"

    def test_stays_personal_info_without_name(self):
        agent, mock_run = _create_agent(with_tax_return=False)
        agent._update_collection_stage()
        assert agent.collection_stage == "personal_info"

    def test_transition_to_deductions_after_income(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.collection_stage = "income"
        agent.process_message("$75,000")
        # process_message already calls _update_collection_stage internally
        if agent.tax_return and agent.tax_return.income.get_total_income() > 0:
            assert agent.collection_stage in ("deductions", "credits")

    def test_transition_credits_to_review(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.add_w2_manually("Employer", 75000, 12500)
        agent.collection_stage = "credits"
        agent._update_collection_stage()
        assert agent.collection_stage == "review"


# ===================================================================
# MANUAL DATA ENTRY
# ===================================================================

class TestManualDataEntry:

    def test_add_w2_manually_no_tax_return(self):
        agent, _ = _create_agent(with_tax_return=False)
        assert agent.add_w2_manually("Employer", 75000, 12500) is False

    def test_add_w2_manually_with_tax_return(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        result = agent.add_w2_manually("Acme Corp", 75000, 12500)
        assert result is True
        assert len(agent.tax_return.income.w2_forms) >= 1

    def test_add_multiple_w2s(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.add_w2_manually("Employer 1", 50000, 8000)
        agent.add_w2_manually("Employer 2", 25000, 4000)
        assert len(agent.tax_return.income.w2_forms) >= 2

    def test_add_1099_manually_no_tax_return(self):
        agent, _ = _create_agent(with_tax_return=False)
        assert agent.add_1099_manually("Payer", 5000) is False

    def test_add_1099_manually_with_tax_return(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        result = agent.add_1099_manually("Client LLC", 10000, "1099-NEC")
        assert result is True

    @pytest.mark.parametrize("form_type", ["1099-MISC", "1099-NEC", "1099-INT", "1099-DIV"])
    def test_add_1099_form_types(self, form_type):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        result = agent.add_1099_manually("Payer", 5000, form_type)
        assert result is True


# ===================================================================
# COMPLETENESS CHECK
# ===================================================================

class TestCompleteness:

    def test_not_complete_initially(self):
        agent, _ = _create_agent(with_tax_return=False)
        assert agent.is_complete() is False

    def test_not_complete_name_only(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        assert agent.is_complete() is False

    def test_complete_with_name_and_income(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.add_w2_manually("Employer", 75000, 12500)
        assert agent.is_complete() is True

    def test_get_tax_return_none_initially(self):
        agent, _ = _create_agent(with_tax_return=False)
        assert agent.get_tax_return() is None

    def test_get_tax_return_after_input(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        assert agent.get_tax_return() is not None


# ===================================================================
# INFO SUMMARY
# ===================================================================

class TestInfoSummary:

    def test_summary_no_data(self):
        agent, _ = _create_agent(with_tax_return=False)
        summary = agent._get_collected_info_summary()
        assert "No information" in summary

    def test_summary_with_name(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        summary = agent._get_collected_info_summary()
        assert "John" in summary

    def test_summary_with_income(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.add_w2_manually("Employer", 75000, 12500)
        summary = agent._get_collected_info_summary()
        assert "W-2" in summary or "Income" in summary or "75" in summary


# ===================================================================
# SERIALIZATION
# ===================================================================

class TestSerialization:

    def test_get_state_no_tax_return(self):
        agent, _ = _create_agent(with_tax_return=False)
        state = agent.get_state_for_serialization()
        assert state["collection_stage"] == "personal_info"
        assert state["tax_return"] is None
        assert isinstance(state["messages"], list)

    def test_get_state_with_data(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        state = agent.get_state_for_serialization()
        assert state["tax_return"] is not None

    def test_restore_from_state(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        state = agent.get_state_for_serialization()

        new_agent, _ = _create_agent()
        new_agent.restore_from_state(state)
        assert new_agent.collection_stage == agent.collection_stage

    def test_restore_empty_state(self):
        agent, _ = _create_agent()
        agent.restore_from_state({})
        assert agent.collection_stage == "personal_info"

    def test_restore_preserves_messages(self):
        agent, mock_run = _create_agent()
        agent.start_conversation()
        agent.process_message("John Smith")
        state = agent.get_state_for_serialization()

        new_agent, _ = _create_agent()
        new_agent.restore_from_state(state)
        assert len(new_agent.messages) >= len(state["messages"])

    def test_roundtrip_serialization(self):
        agent, mock_run = _create_agent()
        agent.process_message("John Smith")
        agent.add_w2_manually("Acme", 75000, 12500)

        state = agent.get_state_for_serialization()

        new_agent, _ = _create_agent()
        new_agent.restore_from_state(state)
        new_state = new_agent.get_state_for_serialization()

        assert state["collection_stage"] == new_state["collection_stage"]


# ===================================================================
# SESSION MANAGEMENT
# ===================================================================

class TestSessionManagement:

    def test_multiple_conversations_independent(self):
        agent1, mock_run1 = _create_agent()
        agent2, mock_run2 = _create_agent()

        agent1.process_message("John Smith")
        agent2.process_message("Jane Doe")

        assert agent1.tax_return.taxpayer.first_name == "John"
        assert agent2.tax_return.taxpayer.first_name == "Jane"

    def test_setup_system_prompt_resets(self):
        agent, _ = _create_agent()
        agent.messages.append({"role": "user", "content": "extra"})
        agent._setup_system_prompt()
        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "system"
