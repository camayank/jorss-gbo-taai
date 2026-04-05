# Audit-Based Analytics Architecture

## Overview

The audit analytics system provides real-time performance metrics for the CPA dashboard by querying the unified audit log. This architecture enables CPAs to track tax savings delivered, return processing metrics, lead conversion funnels, and recommendation acceptance rates—all derived from actual system events rather than manual input or periodic batch jobs.

## Architecture

### Components

```
┌─────────────────────────────────────────┐
│ CPA Analytics Dashboard Route           │
│ (src/web/cpa_dashboard_pages.py)        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Pipeline Service                        │
│ (cpa_panel/services/pipeline_service)   │
│ - get_tax_savings_metrics()             │
│ - get_return_processing_metrics()       │
│ - get_lead_conversion_funnel_audit()    │
│ - get_recommendation_acceptance_metrics()
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Audit Analytics Helper                  │
│ (cpa_panel/services/audit_analytics_helper)
│ - get_tax_savings_by_client()           │
│ - get_return_processing_metrics()       │
│ - get_lead_conversion_funnel()          │
│ - get_recommendation_acceptance_rate()  │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Audit Service                           │
│ (audit/unified/audit_service.py)        │
│ ._storage.query(event_type, ...)        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Audit Storage / Database                │
│ PostgreSQL audit events table           │
└─────────────────────────────────────────┘
```

### Data Flow

1. **Route Handler** (`cpa_analytics`) calls pipeline service wrapper methods with tenant ID
2. **Pipeline Service** delegates to `AuditAnalyticsHelper` singleton
3. **Helper** queries the audit service storage backend for specific event types
4. **Audit Service** returns filtered/sorted results from the database
5. **Helper** aggregates results into structured metrics (dataclasses or dicts)
6. **Pipeline Service** converts dataclasses to dicts for template rendering
7. **Template** renders metric cards with audit data

## Metrics Provided

### 1. Tax Savings Delivered
**Query:** `TAX_CALC_RUN` events
**Calculation:** Difference between `old_value.outputs.total_tax_liability` and `new_value.outputs.total_tax_liability`
**Aggregation:** By client (from metadata or resource_id)
**Result:**
```python
{
    "total_savings": 50000.0,  # Sum across all clients
    "by_client": [             # List of TaxSavingsMetric objects
        {
            "client_id": "client_123",
            "client_name": "Acme Corp",
            "total_savings": 5000.0,
            "num_returns": 2,
            "avg_savings_per_return": 2500.0,
            "latest_calc_date": "2024-01-15T10:30:00Z"
        }
    ],
    "avg_savings": 5000.0,     # Average per client
    "count": 10                 # Number of clients
}
```

### 2. Return Processing Metrics
**Query:** `TAX_RETURN_SUBMIT` and `TAX_RETURN_ACCEPTED` events
**Calculation:**
- Processing time = days between submit and accept timestamps
- Acceptance rate = (accepted_count / submit_count) * 100
**Aggregation:** Across all returns in period
**Result:**
```python
{
    "total_returns": 15,
    "avg_processing_days": 5.2,
    "submitted_count": 15,
    "accepted_count": 14,
    "acceptance_rate": 93.3,
    "latest_acceptance_date": "2024-01-15T14:00:00Z"
}
```

### 3. Lead Conversion Funnel
**Query:**
- Creation: `TAX_RETURN_CREATE` events with source/lead_type = "magnet"
- Assignment: `CPA_CLIENT_ASSIGN` events
**Calculation:** Conversion rate = (assigned / created) * 100
**Aggregation:** By lead source
**Result:**
```python
{
    "magnet_leads": 100,            # Leads from magnet source
    "assigned_clients": 60,         # Leads converted to clients
    "conversion_rate": 60.0,        # Percentage
    "by_stage": {
        "created_leads": 100,
        "assigned_as_client": 60,
        "pending_assignment": 40
    }
}
```

### 4. Recommendation Acceptance Rate
**Query:**
- Offers: `TAX_DATA_AI_SUGGESTION` events
- Acceptances: `TAX_DATA_FIELD_CHANGE` events with source=AI_CHATBOT or metadata.from_recommendation=True
**Calculation:** Acceptance rate = (accepted / offered) * 100
**Aggregation:** Overall and by field type
**Result:**
```python
{
    "total_recommendations": 40,
    "accepted_count": 32,
    "acceptance_rate": 80.0,
    "by_type": {
        "field_name": {
            "offered": 10,
            "accepted": 8
        }
    }
}
```

## Implementation Details

### AuditAnalyticsHelper Singleton

Located in `src/cpa_panel/services/audit_analytics_helper.py`, this is the core analytics engine:

```python
class AuditAnalyticsHelper:
    """Singleton helper for audit-based analytics."""

    @property
    def audit_service(self) -> AuditService:
        """Get or initialize audit service (lazy)."""

    def get_tax_savings_by_client(
        self,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Calculate tax savings per client from audit logs."""

    def get_return_processing_metrics(
        self,
        tenant_id: str,
        days: int = 30
    ) -> ReturnProcessingMetric:
        """Get return processing time and acceptance metrics."""

    def get_lead_conversion_funnel(
        self,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get lead conversion funnel from audit logs."""

    def get_recommendation_acceptance_rate(
        self,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Calculate recommendation acceptance rate."""
```

**Key Implementation Notes:**
- Uses `self.audit_service._storage.query()` to access the audit database (storage backend, not the service facade)
- All queries are time-windowed (default 30 days, configurable)
- Returns use dataclasses (`TaxSavingsMetric`, `ReturnProcessingMetric`) for type safety
- Graceful error handling with logging for malformed events
- Aggregations use dictionaries for grouping before building result structures

### Pipeline Service Integration

The `LeadPipelineService` class provides wrapper methods that delegate to the helper:

```python
def get_tax_savings_metrics(
    self,
    tenant_id: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """Wrapper around audit analytics helper."""
    helper = get_audit_analytics_helper()
    return helper.get_tax_savings_by_client(tenant_id=tenant_id, days=days)

def get_return_processing_metrics(
    self,
    tenant_id: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """Wrapper around audit analytics helper."""
    helper = get_audit_analytics_helper()
    result = helper.get_return_processing_metrics(tenant_id=tenant_id, days=days)
    # Convert dataclass to dict for template
    return asdict(result) if result else {}
```

### Dashboard Integration

The CPA analytics route (`/cpa/analytics`) now queries all metrics:

```python
@cpa_dashboard_router.get("/analytics", response_class=HTMLResponse)
async def cpa_analytics(request, current_user):
    # ... existing code ...

    # Get audit-based analytics with error handling
    try:
        from cpa_panel.services.pipeline_service import get_pipeline_service
        service = get_pipeline_service()
        tenant_id = get_tenant_id_from_user(current_user)

        audit_tax_savings = service.get_tax_savings_metrics(tenant_id)
        audit_return_metrics = service.get_return_processing_metrics(tenant_id)
        audit_lead_funnel = service.get_lead_conversion_funnel_audit(tenant_id)
        audit_recommendations = service.get_recommendation_acceptance_metrics(tenant_id)
    except Exception as e:
        logger.warning(f"Failed to get audit analytics: {e}")
        # Fallback to defaults
        audit_tax_savings = {"total_savings": 0, ...}
        # ... more defaults ...

    # Pass to template
    return templates.TemplateResponse("cpa/analytics.html", {
        "audit_tax_savings": audit_tax_savings,
        "audit_return_metrics": audit_return_metrics,
        "audit_lead_funnel": audit_lead_funnel,
        "audit_recommendations": audit_recommendations,
        # ... other context ...
    })
```

### Template Rendering

Metrics are displayed as cards in `src/web/templates/cpa/analytics.html`:

```html
<!-- Audit-Based Metrics Section -->
<div style="margin-bottom: var(--space-8);">
    <h3>Performance from Audit Data</h3>

    <div class="metrics-grid">
        <!-- Tax Savings Card -->
        <div class="metric-card">
            <div class="metric-header">
                <span class="metric-title">Total Tax Savings</span>
                <div class="metric-icon">💰</div>
            </div>
            <div class="metric-value">${{ '{:,.0f}'.format(audit_tax_savings.total_savings or 0) }}</div>
            <div class="metric-change">
                {{ audit_tax_savings.count or 0 }} clients
            </div>
        </div>
        <!-- ... more cards ... -->
    </div>
</div>
```

## Query Performance & Scalability

### Query Optimization
- All queries use `limit=1000` to prevent memory exhaustion on large event tables
- Time-windowed queries (default 30 days) reduce result set size
- Database indexes on `event_type`, `tenant_id`, `timestamp` are essential

### Caching Strategy
- No application-level caching currently; metrics are always fresh
- Could implement 5-minute cache on metrics without staleness issues
- Consider caching if dashboard becomes heavily used

### Monitoring
- All metric queries are logged at WARNING level if they fail
- Failed metrics gracefully degrade to zero/empty with sensible defaults
- No hard errors propagated to user; dashboard always renders

## Testing

### Unit Tests
- `tests/test_audit_analytics_helper.py`: 11 tests covering all metrics methods
  - Empty result scenarios
  - Populated event scenarios with mock audit entries
  - Proper aggregation and calculations
  - Error handling

- `tests/test_pipeline_service.py`: 2 integration tests
  - Verify wrapper methods exist and are callable
  - Basic integration with helper

- `tests/test_cpa_analytics.py`: 2 route tests
  - Verify audit metrics are passed to template context
  - Verify graceful degradation when service fails

### Test Execution
```bash
# Run all audit analytics tests
python3 -m pytest tests/test_audit_analytics_helper.py tests/test_pipeline_service.py tests/test_cpa_analytics.py -v

# Run with coverage
python3 -m pytest tests/test_audit_analytics_helper.py --cov=cpa_panel.services.audit_analytics_helper
```

## Future Enhancements

1. **Caching Layer**: Add 5-minute Redis cache for metrics to reduce database load
2. **Real-time Updates**: WebSocket push updates for dashboard when metrics change
3. **Historical Trends**: Store daily snapshots of metrics for trend analysis
4. **Alerts**: Trigger notifications when metrics cross thresholds (e.g., "0% acceptance rate")
5. **Export**: Allow CPAs to export metrics as CSV/PDF reports
6. **Customization**: Let CPAs choose time windows and aggregate methods per metric
7. **Role-based Filtering**: CPAs see only their own metrics; partners see firm-wide

## Troubleshooting

### Metrics Showing Zero
- Check that audit events are being captured (verify `audit_service._storage` has events)
- Verify time window includes events (default 30 days)
- Check tenant_id filtering is correct

### Template Errors
- Verify metric dict keys match template `{{ }}` expressions
- Check that defaults are set when service fails
- Inspect console/logs for exceptions during metric retrieval

### Query Performance Issues
- Check database indexes on `event_type`, `tenant_id`, `timestamp`
- Reduce `days` parameter if performance is slow
- Consider pagination or batch loading for large tenants

## References

- Audit Service: `audit/unified/audit_service.py`
- Audit Event Types: `audit/unified/event_types.py`
- CPA Dashboard Routes: `src/web/cpa_dashboard_pages.py`
- CPA Dashboard Template: `src/web/templates/cpa/analytics.html`
