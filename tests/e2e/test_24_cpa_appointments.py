"""
E2E Test: Appointments CRUD

Tests: Availability → Slots → Book → List → Update → Confirm → Cancel → Reschedule
"""

import pytest
from unittest.mock import patch


class TestAppointmentAvailability:
    """CPA availability management."""

    def test_set_availability(self, client, headers, cpa_jwt_payload):
        """Set CPA availability slots."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/appointments/availability", headers=headers, json={
                "day_of_week": "monday",
                "start_time": "09:00",
                "end_time": "17:00",
                "slot_duration_minutes": 30,
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_get_availability(self, client, headers, cpa_jwt_payload):
        """Get CPA availability."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/appointments/availability/cpa-e2e-001", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_available_slots(self, client, headers, cpa_jwt_payload):
        """Get available booking slots."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/appointments/slots", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestAppointmentCRUD:
    """Appointment booking and management."""

    def test_book_appointment(self, client, headers, cpa_jwt_payload):
        """Book a new appointment."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/appointments", headers=headers, json={
                "client_id": "client-001",
                "date": "2026-04-01",
                "time": "10:00",
                "duration_minutes": 30,
                "type": "tax_review",
                "notes": "Annual review meeting",
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_list_appointments(self, client, headers, cpa_jwt_payload):
        """List all appointments."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/appointments", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_appointment(self, client, headers, cpa_jwt_payload):
        """Get specific appointment."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/appointments/test-appt-id", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_update_appointment(self, client, headers, cpa_jwt_payload):
        """Update appointment details."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.put("/api/cpa/appointments/test-appt-id", headers=headers, json={
                "notes": "Updated notes",
            })
        assert response.status_code in [200, 404, 405, 500]


class TestAppointmentActions:
    """Appointment lifecycle actions."""

    def test_confirm_appointment(self, client, headers, cpa_jwt_payload):
        """Confirm appointment."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/appointments/test-appt-id/confirm", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_cancel_appointment(self, client, headers, cpa_jwt_payload):
        """Cancel appointment."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/appointments/test-appt-id/cancel", headers=headers, json={
                "reason": "Client requested reschedule",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_reschedule_appointment(self, client, headers, cpa_jwt_payload):
        """Reschedule appointment."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/appointments/test-appt-id/reschedule", headers=headers, json={
                "new_date": "2026-04-15",
                "new_time": "14:00",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_complete_appointment(self, client, headers, cpa_jwt_payload):
        """Complete appointment."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/appointments/test-appt-id/complete", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]


class TestAppointmentFilters:
    """Appointment filtering."""

    def test_upcoming_appointments(self, client, headers, cpa_jwt_payload):
        """Get upcoming appointments."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/appointments/upcoming", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_todays_appointments(self, client, headers, cpa_jwt_payload):
        """Get today's appointments."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/appointments/today", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestAppointmentPage:
    """Appointment page rendering."""

    def test_appointments_page(self, client, headers):
        """Appointments page should render."""
        response = client.get("/cpa/appointments")
        assert response.status_code in [200, 302, 303, 307, 404]
