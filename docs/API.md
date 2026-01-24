# Jorss-Gbo API Documentation

## Overview

The Jorss-Gbo CPA Lead Platform provides RESTful APIs for:
- Lead magnet flow (prospect-facing)
- CPA dashboard and lead management
- Notifications and activity tracking
- Engagement letter generation

Base URL: `https://your-domain.com/api`

## Authentication

Most CPA-facing endpoints require authentication via JWT token in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

Prospect-facing endpoints (lead magnet flow) do not require authentication.

---

## Lead Magnet API

### Start Assessment Session

```http
POST /api/cpa/lead-magnet/start
```

Start a new tax assessment session with optional CPA branding.

**Request Body:**
```json
{
  "cpa_slug": "john-smith-cpa",
  "assessment_mode": "quick",
  "referral_source": "google"
}
```

**Response:**
```json
{
  "session_id": "sess-abc123",
  "cpa_profile": {
    "cpa_name": "John Smith, CPA",
    "firm_name": "Smith Tax Advisory",
    "logo_url": "...",
    "primary_color": "#1e40af"
  },
  "assessment_mode": "quick",
  "screens": ["welcome", "profile", "contact", "report"]
}
```

### Submit Tax Profile

```http
POST /api/cpa/lead-magnet/{session_id}/profile
```

Submit answers to the tax profile questionnaire.

**Request Body:**
```json
{
  "filing_status": "married_jointly",
  "dependents_count": 2,
  "has_children_under_17": true,
  "income_range": "100k_150k",
  "income_sources": ["w2", "investments"],
  "is_homeowner": true,
  "retirement_savings": "some",
  "healthcare_type": "employer",
  "life_events": ["baby"],
  "has_student_loans": false,
  "has_business": false,
  "privacy_consent": true
}
```

**Response:**
```json
{
  "session_id": "sess-abc123",
  "complexity": "moderate",
  "income_range_display": "$100,000 - $150,000",
  "insights_preview": 8,
  "next_screen": "contact"
}
```

### Capture Contact Info

```http
POST /api/cpa/lead-magnet/{session_id}/contact
```

Capture prospect contact information (lead gate).

**Request Body:**
```json
{
  "first_name": "John",
  "email": "john@example.com",
  "phone": "(555) 123-4567"
}
```

**Response:**
```json
{
  "session_id": "sess-abc123",
  "lead_id": "lead-xyz789",
  "report_ready": true,
  "redirect_url": "/api/cpa/lead-magnet/sess-abc123/report"
}
```

### Get Tier 1 Report (FREE)

```http
GET /api/cpa/lead-magnet/{session_id}/report
```

Get the free teaser report with limited insights.

**Query Parameters:**
- `format`: `json` (default) or `html`

**Response:**
```json
{
  "session_id": "sess-abc123",
  "lead_id": "lead-xyz789",
  "tier": 1,
  "cpa_name": "John Smith, CPA",
  "cpa_firm": "Smith Tax Advisory",
  "client_name": "John",
  "savings_range": "$2,400 - $4,200",
  "insights": [
    {
      "category": "Retirement",
      "title": "401(k) Contribution Opportunity",
      "teaser_description": "You may be able to increase...",
      "savings_range": "$800 - $1,200"
    }
  ],
  "total_insights": 8,
  "locked_count": 5,
  "cta_text": "Schedule a free consultation",
  "booking_link": "https://calendly.com/john-cpa"
}
```

### Get Tier 2 Report (Full)

```http
GET /api/cpa/lead-magnet/{session_id}/report/full
```

Get the complete report with all insights. Requires:
1. CPA has marked lead as engaged
2. Engagement letter has been acknowledged

**Response (403 if requirements not met):**
```json
{
  "error": "Tier 2 report access denied",
  "reason": "Engagement letter acknowledgment required",
  "requirements": {
    "engaged": "CPA must mark lead as engaged",
    "engagement_letter_acknowledged": "Engagement letter must be acknowledged"
  }
}
```

---

## CPA Lead Management API

### List Leads

```http
GET /api/cpa/lead-magnet/leads
```

**Query Parameters:**
- `cpa_id`: Filter by CPA
- `temperature`: `hot`, `warm`, or `cold`
- `engaged`: `true` or `false`
- `limit`: Max results (default 50, max 100)
- `offset`: Pagination offset

**Response:**
```json
{
  "count": 25,
  "offset": 0,
  "limit": 50,
  "leads": [
    {
      "lead_id": "lead-xyz789",
      "first_name": "John",
      "email": "john@example.com",
      "lead_score": 85,
      "lead_temperature": "hot",
      "savings_range": "$2,400 - $4,200",
      "engaged": false,
      "created_at": "2024-01-24T10:30:00Z"
    }
  ]
}
```

### Get Hot Leads

```http
GET /api/cpa/lead-magnet/leads/hot
```

Get high-priority leads (score >= 70, not yet engaged).

### Get Lead Statistics

```http
GET /api/cpa/lead-magnet/leads/stats
```

**Response:**
```json
{
  "total_leads": 150,
  "by_temperature": {
    "hot": 25,
    "warm": 75,
    "cold": 50
  },
  "by_complexity": {
    "simple": 40,
    "moderate": 80,
    "complex": 30
  },
  "engaged_count": 45,
  "converted_count": 12,
  "average_score": 68.5,
  "total_pipeline_value": 125000
}
```

### Engage Lead

```http
POST /api/cpa/lead-magnet/leads/{lead_id}/engage
```

Mark a lead as engaged (step 1 of Tier 2 unlock).

**Request Body:**
```json
{
  "notes": "Called prospect, scheduled follow-up",
  "engagement_letter_acknowledged": false
}
```

**Response:**
```json
{
  "lead_id": "lead-xyz789",
  "engaged": true,
  "engaged_at": "2024-01-24T14:30:00Z",
  "tier_2_unlocked": false,
  "message": "Lead marked as engaged. Engagement letter acknowledgment required for Tier 2 access."
}
```

### Acknowledge Engagement Letter

```http
POST /api/cpa/lead-magnet/leads/{lead_id}/acknowledge-engagement
```

**Request Body:**
```json
{
  "acknowledged": true
}
```

### Convert Lead

```http
POST /api/cpa/lead-magnet/leads/{lead_id}/convert
```

Convert an engaged lead to a client.

**Response:**
```json
{
  "lead_id": "lead-xyz789",
  "converted": true,
  "converted_at": "2024-01-24T16:00:00Z",
  "client_id": "client-abc123",
  "client_token": "client_...",
  "dashboard_url": "/client?token=client_..."
}
```

---

## Notifications API

### List Notifications

```http
GET /api/cpa/notifications
```

**Query Parameters:**
- `unread_only`: `true` to show only unread
- `limit`: Max results (default 50)
- `offset`: Pagination offset

### Mark Notifications Read

```http
POST /api/cpa/notifications/mark-read
```

**Request Body:**
```json
{
  "notification_ids": ["notif-1", "notif-2"]
}
```

### Get Follow-up Reminders

```http
GET /api/cpa/reminders
```

**Query Parameters:**
- `include_completed`: Include completed reminders

---

## Engagement Letters API

### Generate Engagement Letter

```http
POST /api/cpa/engagement/letters/generate
```

**Request Body:**
```json
{
  "session_id": "sess-abc123",
  "letter_type": "tax_preparation",
  "cpa_firm_name": "Smith Tax Advisory",
  "cpa_name": "John Smith",
  "cpa_credentials": "CPA, MST",
  "firm_address": "123 Main St, City, ST 12345",
  "client_name": "Jane Doe",
  "client_email": "jane@example.com",
  "client_address": "456 Oak Ave, City, ST 12345",
  "tax_year": 2024,
  "complexity_tier": "moderate",
  "fee_amount": 1500
}
```

### Download as PDF

```http
GET /api/cpa/engagement/letters/{letter_id}/pdf
```

Returns PDF file download.

---

## Health & Monitoring

### Health Check

```http
GET /health
```

Full health check with all service statuses.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-24T12:00:00Z",
  "uptime": "3:45:22",
  "version": "1.0.0",
  "environment": "production",
  "checks": {
    "database": {"status": "healthy", "latency_ms": 2.5},
    "encryption": {"status": "healthy"},
    "disk": {"status": "healthy", "usage_percent": 45.2}
  }
}
```

### Liveness Probe

```http
GET /health/live
```

Simple liveness check for Kubernetes.

### Readiness Probe

```http
GET /health/ready
```

Readiness check for Kubernetes.

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": true,
  "code": "VALIDATION_ERROR",
  "message": "Technical error message",
  "details": {},
  "user_message": "User-friendly error message"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Invalid request data |
| `MISSING_DATA` | Required data not provided |
| `SESSION_NOT_FOUND` | Session ID not found |
| `RATE_LIMIT` | Too many requests |
| `INTERNAL_ERROR` | Server error |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/api/cpa/lead-magnet/start` | 10/minute per IP |
| `/api/cpa/lead-magnet/{id}/contact` | 5/minute per IP |
| `/api/cpa/*` | 100/minute per CPA |

Exceeded limits return `429 Too Many Requests`.
