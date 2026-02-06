# UX v2 Rollout Plan

**Created**: 2026-02-06
**Status**: Ready for Execution
**Goal**: Safely roll out v2 templates to production with gradual traffic shifting

---

## Executive Summary

This document outlines the systematic rollout of UX v2 templates using feature flags for controlled deployment. The rollout follows a 4-stage process: Internal Testing → 10% → 50% → 100%.

---

## Pre-Rollout Checklist

### 1. Code Verification
- [ ] All v2 templates pass Jinja2 syntax validation
- [ ] CSS modules load without 404 errors
- [ ] Feature flag system tested locally
- [ ] No console errors on v2 pages

### 2. Templates Ready for v2
| Template | Path | Status |
|----------|------|--------|
| Base | `v2/base.html` | Ready |
| Results | `v2/results.html` | Ready |
| Guided Filing | `v2/guided_filing.html` | Ready |
| Dashboard | `v2/dashboard.html` | Ready |
| Lead Magnet Landing | `v2/lead_magnet/landing.html` | Ready |

### 3. Feature Flag Configuration
```python
# Environment Variables
UX_V2_ENABLED=true       # Master switch
UX_V2_PERCENTAGE=0       # Start at 0%, increase gradually

# Override for testing
# Add ?ux_v2=1 to any URL for immediate v2 access
```

---

## Rollout Stages

### Stage 0: Internal Testing (Current)
**Duration**: Before production deployment
**Traffic**: 0% (manual override only)

**Actions**:
1. Deploy code to staging/production with flags OFF
2. Test all v2 pages using `?ux_v2=1` query parameter
3. Verify on multiple devices (desktop, tablet, mobile)
4. Check analytics events fire correctly

**Verification Checklist**:
- [ ] `/?ux_v2=1` - Homepage renders
- [ ] `/file/guided?ux_v2=1` - Guided filing works
- [ ] `/file/results?ux_v2=1` - Results page displays
- [ ] `/dashboard?ux_v2=1` - CPA dashboard loads
- [ ] `/lead-magnet/landing?ux_v2=1` - Lead magnet page works
- [ ] Mobile viewport tested (375px)
- [ ] Tablet viewport tested (768px)
- [ ] No JavaScript console errors
- [ ] Forms submit correctly
- [ ] Navigation works

**Exit Criteria**: All checklist items pass

---

### Stage 1: Canary Release (10%)
**Duration**: 24-48 hours
**Traffic**: 10% of users

**Configuration**:
```bash
UX_V2_ENABLED=true
UX_V2_PERCENTAGE=10
```

**Monitoring**:
- Error rate < 0.1%
- No spike in support tickets
- Bounce rate within ±5% of baseline
- Page load time within ±10% of baseline

**Rollback Trigger**:
- Error rate > 1%
- Critical bug reported
- Significant conversion drop (>10%)

**Rollback Command**:
```bash
UX_V2_PERCENTAGE=0
```

**Exit Criteria**: 24 hours with stable metrics

---

### Stage 2: Partial Rollout (50%)
**Duration**: 24-48 hours
**Traffic**: 50% of users

**Configuration**:
```bash
UX_V2_ENABLED=true
UX_V2_PERCENTAGE=50
```

**Monitoring**:
- Same metrics as Stage 1
- A/B comparison: v1 vs v2 completion rates
- User feedback collection

**Exit Criteria**: Metrics stable, no critical issues

---

### Stage 3: Full Rollout (100%)
**Duration**: Permanent
**Traffic**: 100% of users

**Configuration**:
```bash
UX_V2_ENABLED=true
UX_V2_PERCENTAGE=100
```

**Post-Rollout Actions**:
1. Monitor for 1 week
2. Collect user feedback
3. Plan deprecation of v1 templates
4. Schedule cleanup of feature flag code

---

## Monitoring Dashboard

### Key Metrics to Track

| Metric | Source | Baseline | Alert Threshold |
|--------|--------|----------|-----------------|
| Error Rate | Sentry | <0.1% | >1% |
| Page Load Time | Analytics | <2.5s | >4s |
| Bounce Rate | Analytics | Baseline | +10% |
| Form Completion | Analytics | Baseline | -15% |
| Support Tickets | Helpdesk | Normal | 2x spike |

### Analytics Events
```javascript
// Track UX version in all events
gtag('event', 'page_view', {
  'ux_version': 'v2',
  'page_template': 'guided_filing'
});
```

---

## Rollback Procedure

### Immediate Rollback (< 1 minute)
```bash
# Set percentage to 0 - users get v1 immediately
export UX_V2_PERCENTAGE=0
# Or disable entirely
export UX_V2_ENABLED=false
```

### Full Rollback (if needed)
1. Revert to previous deployment
2. Notify team via Slack/email
3. Document incident
4. Plan fix before retry

---

## Communication Plan

| Stage | Audience | Channel | Message |
|-------|----------|---------|---------|
| Pre-rollout | Dev Team | Slack | "Starting UX v2 rollout" |
| 10% Live | Dev Team | Slack | "10% rollout active, monitoring" |
| 50% Live | All Staff | Email | "New UX rolling out to users" |
| 100% Live | Users | In-app | Optional announcement |

---

## Success Criteria

The rollout is considered successful when:

1. **Stability**: 7 days at 100% with error rate < 0.1%
2. **Performance**: Page load times equal or better than v1
3. **User Experience**: No increase in support tickets
4. **Metrics**: Conversion rates equal or better than v1

---

## Timeline

| Day | Action |
|-----|--------|
| Day 0 | Internal testing with `?ux_v2=1` |
| Day 1 | Enable 10% rollout |
| Day 2-3 | Monitor 10% rollout |
| Day 3 | Scale to 50% if stable |
| Day 4-5 | Monitor 50% rollout |
| Day 5 | Scale to 100% if stable |
| Day 5-12 | Monitor full rollout |
| Day 12+ | Deprecate v1 templates |

---

## Appendix: Feature Flag Code Reference

**Location**: `src/web/feature_flags.py`

```python
# Check if user should see v2
from web.feature_flags import should_use_ux_v2, get_template_path

# In route handler
if should_use_ux_v2(request):
    template = "v2/dashboard.html"
else:
    template = "dashboard.html"

# Or use resolver
template = get_template_path(request, "dashboard.html")
```

---

*Plan created: 2026-02-06*
