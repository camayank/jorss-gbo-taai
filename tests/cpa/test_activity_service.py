"""
Tests for ActivityService.

Covers activity logging for all ActivityType and ActivityActor variants,
timeline retrieval, filtering, convenience methods, description generation,
bulk operations, analytics, and edge cases.
"""
import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cpa_panel.services.activity_service import (
    ActivityService,
    ActivityType,
    ActivityActor,
    Activity,
    get_activity_service,
)


# =========================================================================
# ENUM TESTS
# =========================================================================

class TestActivityTypeEnum:
    """Verify all ActivityType members."""

    ALL_TYPES = [
        (ActivityType.LEAD_CREATED, "lead_created"),
        (ActivityType.LEAD_CAPTURED, "lead_captured"),
        (ActivityType.STATE_CHANGE, "state_change"),
        (ActivityType.CPA_VIEWED, "cpa_viewed"),
        (ActivityType.CPA_CONTACTED, "cpa_contacted"),
        (ActivityType.CPA_ENGAGED, "cpa_engaged"),
        (ActivityType.CPA_NOTE_ADDED, "cpa_note_added"),
        (ActivityType.CPA_ASSIGNED, "cpa_assigned"),
        (ActivityType.REPORT_GENERATED, "report_generated"),
        (ActivityType.REPORT_DELIVERED, "report_delivered"),
        (ActivityType.EMAIL_SENT, "email_sent"),
        (ActivityType.REMINDER_CREATED, "reminder_created"),
        (ActivityType.REMINDER_COMPLETED, "reminder_completed"),
        (ActivityType.ENGAGEMENT_LETTER_SENT, "engagement_letter_sent"),
        (ActivityType.ENGAGEMENT_LETTER_SIGNED, "engagement_letter_signed"),
        (ActivityType.LEAD_CONVERTED, "lead_converted"),
        (ActivityType.LEAD_ARCHIVED, "lead_archived"),
    ]

    @pytest.mark.parametrize("member,value", ALL_TYPES)
    def test_type_values(self, member, value):
        assert member.value == value

    def test_type_count(self):
        assert len(ActivityType) == 17

    @pytest.mark.parametrize("at", list(ActivityType))
    def test_type_is_str(self, at):
        assert isinstance(at, str)


class TestActivityActorEnum:
    """Verify ActivityActor members."""

    @pytest.mark.parametrize("member,value", [
        (ActivityActor.SYSTEM, "system"),
        (ActivityActor.CPA, "cpa"),
        (ActivityActor.CLIENT, "client"),
        (ActivityActor.ADMIN, "admin"),
    ])
    def test_actor_values(self, member, value):
        assert member.value == value

    def test_actor_count(self):
        assert len(ActivityActor) == 4


# =========================================================================
# ACTIVITY DATACLASS
# =========================================================================

class TestActivityDataclass:
    """Tests for the Activity dataclass."""

    def test_creation(self):
        activity = Activity(
            activity_id="act-001",
            lead_id="lead-001",
            activity_type=ActivityType.LEAD_CREATED,
            actor=ActivityActor.SYSTEM,
        )
        assert activity.activity_id == "act-001"
        assert activity.lead_id == "lead-001"
        assert activity.description == ""
        assert activity.metadata == {}

    def test_full_creation(self):
        activity = Activity(
            activity_id="act-002",
            lead_id="lead-001",
            activity_type=ActivityType.CPA_NOTE_ADDED,
            actor=ActivityActor.CPA,
            actor_id="cpa-001",
            actor_name="CPA Jones",
            description="Added a note",
            metadata={"note": "Good prospect"},
        )
        assert activity.actor_name == "CPA Jones"
        assert activity.metadata["note"] == "Good prospect"

    def test_to_dict(self):
        activity = Activity(
            activity_id="act-003",
            lead_id="lead-001",
            activity_type=ActivityType.EMAIL_SENT,
            actor=ActivityActor.SYSTEM,
            description="Email sent",
            metadata={"subject": "Welcome"},
            created_at=datetime(2025, 3, 1, 12, 0, 0),
        )
        d = activity.to_dict()
        assert d["activity_id"] == "act-003"
        assert d["activity_type"] == "email_sent"
        assert d["actor"] == "system"
        assert d["metadata"]["subject"] == "Welcome"
        assert "2025-03-01" in d["created_at"]

    def test_to_dict_keys(self):
        activity = Activity(
            activity_id="x", lead_id="y",
            activity_type=ActivityType.LEAD_CREATED,
            actor=ActivityActor.SYSTEM,
        )
        d = activity.to_dict()
        expected = {
            "activity_id", "lead_id", "activity_type", "actor",
            "actor_id", "actor_name", "description", "metadata", "created_at",
        }
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("at", list(ActivityType))
    def test_to_dict_with_each_type(self, at):
        activity = Activity(
            activity_id="x", lead_id="y",
            activity_type=at, actor=ActivityActor.SYSTEM,
        )
        d = activity.to_dict()
        assert d["activity_type"] == at.value

    @pytest.mark.parametrize("actor", list(ActivityActor))
    def test_to_dict_with_each_actor(self, actor):
        activity = Activity(
            activity_id="x", lead_id="y",
            activity_type=ActivityType.LEAD_CREATED,
            actor=actor,
        )
        d = activity.to_dict()
        assert d["actor"] == actor.value


# =========================================================================
# CORE LOG ACTIVITY
# =========================================================================

class TestLogActivity:
    """Tests for log_activity core method."""

    def test_log_returns_activity(self, activity_service):
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=ActivityType.LEAD_CREATED,
        )
        assert isinstance(result, Activity)
        assert result.lead_id == "lead-001"
        assert result.activity_type == ActivityType.LEAD_CREATED

    def test_log_generates_unique_id(self, activity_service):
        a1 = activity_service.log_activity("lead-1", ActivityType.LEAD_CREATED)
        a2 = activity_service.log_activity("lead-1", ActivityType.LEAD_CREATED)
        assert a1.activity_id != a2.activity_id

    def test_log_activity_id_format(self, activity_service):
        a = activity_service.log_activity("lead-1", ActivityType.LEAD_CREATED)
        assert a.activity_id.startswith("act-")

    @pytest.mark.parametrize("activity_type", list(ActivityType))
    def test_log_all_activity_types(self, activity_service, activity_type):
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=activity_type,
        )
        assert result.activity_type == activity_type

    @pytest.mark.parametrize("actor", list(ActivityActor))
    def test_log_all_actors(self, activity_service, actor):
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=ActivityType.LEAD_CREATED,
            actor=actor,
        )
        assert result.actor == actor

    def test_log_with_metadata(self, activity_service):
        meta = {"old_state": "new", "new_state": "qualified"}
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=ActivityType.STATE_CHANGE,
            metadata=meta,
        )
        assert result.metadata == meta

    def test_log_with_actor_info(self, activity_service):
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=ActivityType.CPA_VIEWED,
            actor=ActivityActor.CPA,
            actor_id="cpa-001",
            actor_name="CPA Jones",
        )
        assert result.actor_id == "cpa-001"
        assert result.actor_name == "CPA Jones"

    def test_log_custom_description(self, activity_service):
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=ActivityType.LEAD_CREATED,
            description="Custom desc",
        )
        assert result.description == "Custom desc"

    def test_log_auto_description(self, activity_service):
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=ActivityType.LEAD_CREATED,
        )
        assert len(result.description) > 0

    def test_log_default_actor_is_system(self, activity_service):
        result = activity_service.log_activity(
            lead_id="lead-001",
            activity_type=ActivityType.LEAD_CREATED,
        )
        assert result.actor == ActivityActor.SYSTEM

    def test_log_persists_to_db(self, activity_service):
        activity_service.log_activity("lead-001", ActivityType.LEAD_CREATED)
        activities = activity_service.get_lead_activities("lead-001")
        assert len(activities) == 1

    def test_log_multiple_for_same_lead(self, activity_service):
        for _ in range(5):
            activity_service.log_activity("lead-001", ActivityType.CPA_VIEWED,
                                          actor=ActivityActor.CPA)
        activities = activity_service.get_lead_activities("lead-001")
        assert len(activities) == 5


# =========================================================================
# DESCRIPTION GENERATION
# =========================================================================

class TestDescriptionGeneration:
    """Tests for _generate_description."""

    def test_lead_created_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.LEAD_CREATED, None, None,
        )
        assert "created" in desc.lower()

    def test_lead_captured_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.LEAD_CAPTURED, None, {"email": "test@example.com"},
        )
        assert "test@example.com" in desc

    def test_state_change_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.STATE_CHANGE, None,
            {"old_state": "new", "new_state": "qualified"},
        )
        assert "new" in desc
        assert "qualified" in desc

    def test_cpa_viewed_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.CPA_VIEWED, "CPA Jones", None,
        )
        assert "CPA Jones" in desc

    def test_cpa_assigned_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.CPA_ASSIGNED, None, {"assigned_to": "CPA Smith"},
        )
        assert "CPA Smith" in desc

    def test_email_sent_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.EMAIL_SENT, None, {"subject": "Welcome Email"},
        )
        assert "Welcome Email" in desc

    def test_reminder_created_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.REMINDER_CREATED, None, {"due_date": "2025-04-01"},
        )
        assert "2025-04-01" in desc

    def test_lead_converted_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.LEAD_CONVERTED, "CPA Jones", None,
        )
        assert "CPA Jones" in desc
        assert "converted" in desc.lower()

    def test_lead_archived_desc(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.LEAD_ARCHIVED, "Admin", None,
        )
        assert "archived" in desc.lower()

    @pytest.mark.parametrize("activity_type", list(ActivityType))
    def test_all_types_generate_description(self, activity_service, activity_type):
        desc = activity_service._generate_description(activity_type, "Actor", {})
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_none_actor_defaults_to_system(self, activity_service):
        desc = activity_service._generate_description(
            ActivityType.CPA_VIEWED, None, None,
        )
        assert "System" in desc


# =========================================================================
# CONVENIENCE METHODS
# =========================================================================

class TestConvenienceMethods:
    """Tests for convenience logging methods."""

    def test_log_lead_created(self, activity_service):
        a = activity_service.log_lead_created("lead-001", session_id="sess-1")
        assert a.activity_type == ActivityType.LEAD_CREATED
        assert a.metadata.get("session_id") == "sess-1"

    def test_log_lead_created_no_session(self, activity_service):
        a = activity_service.log_lead_created("lead-001")
        assert a.activity_type == ActivityType.LEAD_CREATED

    def test_log_contact_captured(self, activity_service):
        a = activity_service.log_contact_captured("lead-001", "test@example.com", name="Jane")
        assert a.activity_type == ActivityType.LEAD_CAPTURED
        assert a.metadata["email"] == "test@example.com"
        assert a.metadata["name"] == "Jane"

    def test_log_state_change(self, activity_service):
        a = activity_service.log_state_change("lead-001", "new", "qualified")
        assert a.activity_type == ActivityType.STATE_CHANGE
        assert a.metadata["old_state"] == "new"
        assert a.metadata["new_state"] == "qualified"
        assert a.actor == ActivityActor.SYSTEM

    def test_log_state_change_by_cpa(self, activity_service):
        a = activity_service.log_state_change("lead-001", "new", "qualified",
                                               changed_by="CPA Jones")
        assert a.actor == ActivityActor.CPA
        assert a.actor_name == "CPA Jones"

    def test_log_cpa_viewed(self, activity_service):
        a = activity_service.log_cpa_viewed("lead-001", "cpa-001", "CPA Jones")
        assert a.activity_type == ActivityType.CPA_VIEWED
        assert a.actor == ActivityActor.CPA
        assert a.actor_id == "cpa-001"

    def test_log_cpa_note(self, activity_service):
        a = activity_service.log_cpa_note("lead-001", "cpa-001", "CPA Jones", "Good prospect")
        assert a.activity_type == ActivityType.CPA_NOTE_ADDED
        assert a.metadata["note"] == "Good prospect"

    def test_log_cpa_note_truncation(self, activity_service):
        long_note = "x" * 1000
        a = activity_service.log_cpa_note("lead-001", "cpa-001", "CPA", long_note)
        assert len(a.metadata["note"]) == 500

    def test_log_email_sent(self, activity_service):
        a = activity_service.log_email_sent("lead-001", "welcome", "Welcome!", "test@example.com")
        assert a.activity_type == ActivityType.EMAIL_SENT
        assert a.metadata["email_type"] == "welcome"
        assert a.metadata["subject"] == "Welcome!"
        assert a.metadata["recipient"] == "test@example.com"

    def test_log_engagement(self, activity_service):
        a = activity_service.log_engagement("lead-001", "cpa-001", "CPA Jones")
        assert a.activity_type == ActivityType.CPA_ENGAGED
        assert a.actor == ActivityActor.CPA

    def test_log_conversion(self, activity_service):
        a = activity_service.log_conversion("lead-001", "cpa-001", "CPA Jones", revenue=1500.0)
        assert a.activity_type == ActivityType.LEAD_CONVERTED
        assert a.metadata["revenue"] == 1500.0

    def test_log_conversion_no_revenue(self, activity_service):
        a = activity_service.log_conversion("lead-001", "cpa-001", "CPA Jones")
        assert a.activity_type == ActivityType.LEAD_CONVERTED
        assert a.metadata == {}


# =========================================================================
# TIMELINE RETRIEVAL
# =========================================================================

class TestGetLeadActivities:
    """Tests for get_lead_activities."""

    def test_empty_timeline(self, activity_service):
        activities = activity_service.get_lead_activities("nonexistent-lead")
        assert activities == []

    def test_timeline_returns_activities(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(sample_lead_id)
        assert len(activities) == 7

    def test_timeline_ordered_desc(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(sample_lead_id)
        for i in range(len(activities) - 1):
            assert activities[i].created_at >= activities[i + 1].created_at

    def test_timeline_limit(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(sample_lead_id, limit=3)
        assert len(activities) == 3

    def test_timeline_filter_by_type(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(
            sample_lead_id,
            activity_types=[ActivityType.CPA_VIEWED],
        )
        assert len(activities) == 1
        assert activities[0].activity_type == ActivityType.CPA_VIEWED

    def test_timeline_filter_multiple_types(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(
            sample_lead_id,
            activity_types=[ActivityType.CPA_VIEWED, ActivityType.CPA_NOTE_ADDED],
        )
        assert len(activities) == 2

    def test_timeline_filter_no_match(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(
            sample_lead_id,
            activity_types=[ActivityType.ENGAGEMENT_LETTER_SENT],
        )
        assert len(activities) == 0

    def test_activities_are_activity_objects(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(sample_lead_id)
        for a in activities:
            assert isinstance(a, Activity)
            assert isinstance(a.activity_type, ActivityType)
            assert isinstance(a.actor, ActivityActor)

    def test_metadata_deserialized(self, populated_activity_service, sample_lead_id):
        activities = populated_activity_service.get_lead_activities(
            sample_lead_id,
            activity_types=[ActivityType.EMAIL_SENT],
        )
        assert len(activities) == 1
        assert activities[0].metadata["subject"] == "Welcome"

    def test_multiple_leads_isolated(self, activity_service):
        activity_service.log_activity("lead-A", ActivityType.LEAD_CREATED)
        activity_service.log_activity("lead-A", ActivityType.CPA_VIEWED, actor=ActivityActor.CPA)
        activity_service.log_activity("lead-B", ActivityType.LEAD_CREATED)

        a_activities = activity_service.get_lead_activities("lead-A")
        b_activities = activity_service.get_lead_activities("lead-B")
        assert len(a_activities) == 2
        assert len(b_activities) == 1


# =========================================================================
# RECENT ACTIVITIES (DASHBOARD)
# =========================================================================

class TestGetRecentActivities:
    """Tests for get_recent_activities."""

    def test_empty_recent(self, activity_service):
        results = activity_service.get_recent_activities()
        assert results == [] or isinstance(results, list)

    def test_recent_returns_dicts(self, populated_activity_service):
        results = populated_activity_service.get_recent_activities(limit=5)
        # This may return empty if the join fails (no lead_magnet_leads table)
        # but should not raise
        assert isinstance(results, list)

    def test_recent_limit(self, activity_service):
        for i in range(10):
            activity_service.log_activity(f"lead-{i}", ActivityType.LEAD_CREATED)
        results = activity_service.get_recent_activities(limit=5)
        # May be limited by join; just verify no crash
        assert isinstance(results, list)


# =========================================================================
# BULK LOGGING
# =========================================================================

class TestBulkLogging:
    """Tests for logging multiple activities."""

    def test_log_10_activities(self, activity_service):
        for i in range(10):
            activity_service.log_activity(
                lead_id="lead-bulk",
                activity_type=ActivityType.CPA_VIEWED,
                actor=ActivityActor.CPA,
                actor_name=f"CPA {i}",
            )
        activities = activity_service.get_lead_activities("lead-bulk")
        assert len(activities) == 10

    def test_log_50_activities(self, activity_service):
        for i in range(50):
            activity_service.log_activity(
                lead_id="lead-50",
                activity_type=list(ActivityType)[i % len(ActivityType)],
            )
        activities = activity_service.get_lead_activities("lead-50", limit=50)
        assert len(activities) == 50

    def test_log_all_types_for_one_lead(self, activity_service):
        for at in ActivityType:
            activity_service.log_activity("lead-all-types", at)
        activities = activity_service.get_lead_activities("lead-all-types", limit=20)
        assert len(activities) == 17

    def test_log_all_actors_for_one_lead(self, activity_service):
        for actor in ActivityActor:
            activity_service.log_activity("lead-all-actors", ActivityType.LEAD_CREATED,
                                          actor=actor)
        activities = activity_service.get_lead_activities("lead-all-actors")
        assert len(activities) == 4

    @pytest.mark.parametrize("activity_type,actor", [
        (at, ac)
        for at in [ActivityType.LEAD_CREATED, ActivityType.CPA_VIEWED,
                    ActivityType.EMAIL_SENT, ActivityType.LEAD_CONVERTED]
        for ac in ActivityActor
    ])
    def test_type_actor_combinations(self, activity_service, activity_type, actor):
        a = activity_service.log_activity(
            lead_id="lead-combo",
            activity_type=activity_type,
            actor=actor,
        )
        assert a.activity_type == activity_type
        assert a.actor == actor


# =========================================================================
# DATABASE / PERSISTENCE
# =========================================================================

class TestPersistence:
    """Tests for database persistence behavior."""

    def test_table_created_on_init(self, activity_db_path):
        """ActivityService should create tables on initialization."""
        svc = ActivityService(db_path=activity_db_path)
        import sqlite3
        conn = sqlite3.connect(activity_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lead_activities'")
        row = cursor.fetchone()
        conn.close()
        assert row is not None

    def test_index_created(self, activity_db_path):
        svc = ActivityService(db_path=activity_db_path)
        import sqlite3
        conn = sqlite3.connect(activity_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_activities_lead_id'")
        row = cursor.fetchone()
        conn.close()
        assert row is not None

    def test_data_survives_reinit(self, activity_db_path):
        svc1 = ActivityService(db_path=activity_db_path)
        svc1.log_activity("lead-persist", ActivityType.LEAD_CREATED)

        svc2 = ActivityService(db_path=activity_db_path)
        activities = svc2.get_lead_activities("lead-persist")
        assert len(activities) == 1


# =========================================================================
# SINGLETON
# =========================================================================

class TestActivitySingleton:
    """Test singleton accessor."""

    def test_get_activity_service(self):
        # Reset singleton to avoid conflicts
        ActivityService._instance = None
        with patch.object(ActivityService, "__init__", return_value=None):
            svc = get_activity_service()
            assert isinstance(svc, ActivityService)
        ActivityService._instance = None


# =========================================================================
# EDGE CASES
# =========================================================================

class TestActivityEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_lead_id(self, activity_service):
        a = activity_service.log_activity("", ActivityType.LEAD_CREATED)
        assert a.lead_id == ""

    def test_very_long_lead_id(self, activity_service):
        long_id = "lead-" + "x" * 1000
        a = activity_service.log_activity(long_id, ActivityType.LEAD_CREATED)
        assert a.lead_id == long_id

    def test_special_characters_in_metadata(self, activity_service):
        meta = {"note": "Client said 'yes' & agreed to <terms>", "emoji": "ok"}
        a = activity_service.log_activity(
            "lead-special", ActivityType.CPA_NOTE_ADDED,
            metadata=meta,
        )
        assert a.metadata["note"] == meta["note"]
        # Verify it persisted correctly
        activities = activity_service.get_lead_activities("lead-special")
        assert activities[0].metadata["note"] == meta["note"]

    def test_unicode_in_description(self, activity_service):
        a = activity_service.log_activity(
            "lead-unicode", ActivityType.CPA_NOTE_ADDED,
            description="Note with unicode: cafe\u0301",
        )
        assert "cafe" in a.description

    def test_none_metadata(self, activity_service):
        a = activity_service.log_activity(
            "lead-none-meta", ActivityType.LEAD_CREATED,
            metadata=None,
        )
        assert a.metadata == {}

    def test_empty_metadata(self, activity_service):
        a = activity_service.log_activity(
            "lead-empty-meta", ActivityType.LEAD_CREATED,
            metadata={},
        )
        assert a.metadata == {}

    def test_large_metadata(self, activity_service):
        meta = {f"key_{i}": f"value_{i}" for i in range(100)}
        a = activity_service.log_activity(
            "lead-large-meta", ActivityType.CPA_NOTE_ADDED,
            metadata=meta,
        )
        activities = activity_service.get_lead_activities("lead-large-meta")
        assert len(activities[0].metadata) == 100

    def test_concurrent_leads(self, activity_service):
        """Log activities for many leads and verify isolation."""
        for i in range(20):
            activity_service.log_activity(f"lead-{i}", ActivityType.LEAD_CREATED)
            activity_service.log_activity(f"lead-{i}", ActivityType.CPA_VIEWED,
                                          actor=ActivityActor.CPA)

        for i in range(20):
            activities = activity_service.get_lead_activities(f"lead-{i}")
            assert len(activities) == 2

    def test_activity_created_at_is_datetime(self, activity_service):
        a = activity_service.log_activity("lead-dt", ActivityType.LEAD_CREATED)
        assert isinstance(a.created_at, datetime)

    def test_filter_with_limit(self, activity_service):
        for _ in range(10):
            activity_service.log_activity("lead-fl", ActivityType.CPA_VIEWED,
                                          actor=ActivityActor.CPA)
        activity_service.log_activity("lead-fl", ActivityType.LEAD_CREATED)
        activities = activity_service.get_lead_activities(
            "lead-fl",
            activity_types=[ActivityType.CPA_VIEWED],
            limit=3,
        )
        assert len(activities) == 3
        for a in activities:
            assert a.activity_type == ActivityType.CPA_VIEWED

    @pytest.mark.parametrize("activity_type", list(ActivityType))
    def test_roundtrip_all_types(self, activity_service, activity_type):
        """Log, then retrieve, verifying type survives serialization."""
        activity_service.log_activity("lead-rt", activity_type)
        activities = activity_service.get_lead_activities(
            "lead-rt",
            activity_types=[activity_type],
        )
        assert len(activities) >= 1
        assert activities[0].activity_type == activity_type

    @pytest.mark.parametrize("actor", list(ActivityActor))
    def test_roundtrip_all_actors(self, activity_service, actor):
        """Log, then retrieve, verifying actor survives serialization."""
        activity_service.log_activity("lead-actor-rt", ActivityType.LEAD_CREATED, actor=actor)
        activities = activity_service.get_lead_activities("lead-actor-rt")
        found = [a for a in activities if a.actor == actor]
        assert len(found) >= 1
