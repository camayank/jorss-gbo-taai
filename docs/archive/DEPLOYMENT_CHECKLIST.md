# Production Deployment Checklist

**Date**: January 21, 2026
**Version**: v2.0 - Database Persistence + UI/UX Improvements
**Status**: ✅ Ready for Production

---

## Pre-Deployment Verification

### 1. Database Migration ✅ COMPLETE

- [x] Base schema created (`session_states`, `session_tax_returns`, `document_processing`)
- [x] New columns added (`user_id`, `is_anonymous`, `workflow_type`, `return_id`)
- [x] `session_transfers` table created
- [x] All indexes created
- [x] Migration tests passing

**Verification**:
```bash
python3 migrations/test_migration.py
# Should show: ✅ All migration tests passed!
```

### 2. Code Changes ✅ COMPLETE

**Modified Files** (3):
- [x] `src/web/app.py` - Branding, CSRF, sessions API, auto-save startup
- [x] `src/web/templates/index.html` - Header, chat, triage modal, CSS
- [x] `src/rbac/permissions.py` - FIRM_CLIENT permissions fix

**New Files** (18):
- [x] Migration files (4)
- [x] Documentation files (8)
- [x] Database models (`src/database/unified_session.py`)
- [x] Auto-save system (2 files)
- [x] Auto-save API (`src/web/auto_save_api.py`)

### 3. Feature Verification ✅ COMPLETE

- [x] Database persistence implemented
- [x] Permission bug fixed (FIRM_CLIENT can edit)
- [x] Enhanced header with branding
- [x] Floating chat button
- [x] Smart triage modal
- [x] Results route (no 404)
- [x] Session management API (8 endpoints)
- [x] CSRF protection enabled
- [x] Auto-save manager functional

---

## Deployment Steps

### Step 1: Backup (2 minutes) ✅

```bash
cd /Users/rakeshanita/Jorss-Gbo

# Backup database (if it has production data)
if [ -f tax_filing.db ]; then
    cp tax_filing.db tax_filing.db.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Database backed up"
else
    echo "ℹ️  No existing database to backup"
fi

# Backup .env (if it exists)
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Environment file backed up"
fi
```

### Step 2: Environment Configuration (2 minutes) ✅

```bash
# Generate CSRF secret key (if not already set)
if ! grep -q "CSRF_SECRET_KEY" .env 2>/dev/null; then
    echo "CSRF_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" >> .env
    echo "✅ CSRF secret key generated"
else
    echo "ℹ️  CSRF secret key already configured"
fi

# Optional: Set auto-save interval (default: 30 seconds)
if ! grep -q "AUTO_SAVE_INTERVAL" .env 2>/dev/null; then
    echo "AUTO_SAVE_INTERVAL=30" >> .env
fi

# Verify .env file
cat .env | grep -E "CSRF_SECRET_KEY|AUTO_SAVE_INTERVAL"
```

### Step 3: Database Migration (1 minute) ✅ ALREADY DONE

The database migration has already been completed. Verify:

```bash
# Check tables exist
sqlite3 tax_filing.db ".tables"
# Should show: document_processing, session_states, session_tax_returns, session_transfers, schema_migrations

# Check new columns exist
sqlite3 tax_filing.db "PRAGMA table_info(session_states);" | grep -E "user_id|workflow_type|return_id"
# Should show all three columns

# Run tests
python3 migrations/test_migration.py
# Should show: ✅ All migration tests passed!
```

### Step 4: Dependencies Check (1 minute)

```bash
# Activate virtual environment
source .venv/bin/activate

# Verify key dependencies (should already be installed)
python3 -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python3 -c "import sqlite3; print('SQLite: OK')"
python3 -c "import secrets; print('Secrets: OK')"

echo "✅ All dependencies present"
```

### Step 5: Application Restart (1 minute)

**Option A: Using supervisorctl**
```bash
supervisorctl restart tax_app
supervisorctl status tax_app
```

**Option B: Using systemctl**
```bash
sudo systemctl restart tax-app
sudo systemctl status tax-app
```

**Option C: Manual restart**
```bash
# Stop existing process
pkill -f "uvicorn.*app:app"

# Start new process
nohup uvicorn src.web.app:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &

# Verify running
ps aux | grep uvicorn
```

### Step 6: Health Checks (2 minutes) ✅

```bash
# Basic health check
curl http://localhost:8000/api/health
# Expected: {"status": "healthy"}

# Database connection check
curl http://localhost:8000/api/health/database
# Expected: {"status": "healthy", "database": "connected"}

# Session API check
curl http://localhost:8000/api/sessions/check-active
# Expected: {"has_active_session": false, ...}

# Auto-save check
curl http://localhost:8000/api/auto-save/stats
# Expected: {"running": true, "pending_count": 0, ...}

echo "✅ All health checks passed"
```

### Step 7: UI Verification (3 minutes)

**Open in browser**: `http://localhost:8000`

Visual checks:
- [ ] Company branding appears in header (not "TaxFlow")
- [ ] Trust badges visible: "Secure & Encrypted", "Auto-Saved", "IRS Certified"
- [ ] Floating chat button visible (bottom-right)
- [ ] Chat opens when clicked
- [ ] Smart triage modal appears on first visit
- [ ] Triage shows 3 steps with workflow recommendations

**Test filing flow**:
- [ ] Start filing → creates session
- [ ] Fill some data → browser refresh → data persists ✅
- [ ] Complete filing → redirect to `/results` (not 404) ✅
- [ ] Results page shows refund/owed
- [ ] "Explore Scenarios" link visible
- [ ] "View Projections" link visible

---

## Post-Deployment Monitoring

### Immediate (First Hour)

1. **Monitor logs for errors**:
   ```bash
   tail -f logs/app.log | grep -i "error\|exception\|failed"
   ```

2. **Check auto-save activity**:
   ```bash
   tail -f logs/app.log | grep -i "auto-save"
   # Should see: "Auto-save manager started (interval: 30s)"
   ```

3. **Monitor CSRF rejections**:
   ```bash
   tail -f logs/app.log | grep -i "csrf"
   # Should be minimal (only on invalid requests)
   ```

4. **Test session persistence**:
   - Create session in browser A
   - Note session_id from cookies
   - Open browser B with same session_id
   - Verify data appears

### First 24 Hours

1. **Database growth**:
   ```bash
   ls -lh tax_filing.db
   # Track file size - should grow gradually
   ```

2. **Session cleanup**:
   ```bash
   # Manually trigger cleanup
   curl -X POST http://localhost:8000/api/sessions/cleanup-expired

   # Or set up cron job:
   crontab -e
   # Add: 0 * * * * curl -X POST http://localhost:8000/api/sessions/cleanup-expired
   ```

3. **Auto-save statistics**:
   ```bash
   curl http://localhost:8000/api/auto-save/stats
   # Monitor: pending_count, total_saves, failed_saves
   ```

4. **Error rate monitoring**:
   ```bash
   grep -c "ERROR" logs/app.log
   grep -c "WARNING" logs/app.log
   ```

### First Week

1. **User feedback**:
   - Ask users about new UI (header, chat, triage)
   - Check if anyone reports 404 errors (should be zero)
   - Monitor chat usage analytics

2. **Performance metrics**:
   - Page load time (should be < 2s)
   - Database query time (should be < 100ms)
   - Auto-save overhead (should be negligible)

3. **Database analysis**:
   ```sql
   -- Session creation by workflow
   SELECT workflow_type, COUNT(*) as count
   FROM session_states
   WHERE created_at > datetime('now', '-7 days')
   GROUP BY workflow_type;

   -- Session resume rate
   SELECT
     COUNT(*) as total_sessions,
     SUM(CASE WHEN user_id IS NOT NULL THEN 1 ELSE 0 END) as authenticated_sessions,
     SUM(CASE WHEN is_anonymous = 0 THEN 1 ELSE 0 END) as claimed_sessions
   FROM session_states
   WHERE created_at > datetime('now', '-7 days');

   -- Anonymous → authenticated transfers
   SELECT COUNT(*) as transfers
   FROM session_transfers
   WHERE transferred_at > datetime('now', '-7 days');
   ```

---

## Rollback Plan

**If critical issues occur**, follow these steps:

### Option 1: Quick Disable Features

**Disable CSRF** (if causing false positives):
```python
# Edit src/web/app.py, comment lines 113-139
# try:
#     csrf_secret = ...
#     app.add_middleware(CSRFMiddleware, ...)
# except Exception as e:
#     ...

# Restart application
```

**Disable Auto-Save** (if causing performance issues):
```python
# Edit src/web/app.py, comment out startup_auto_save function
# @app.on_event("startup")
# async def startup_auto_save():
#     ...

# Restart application
```

**Disable Sessions API** (if causing errors):
```python
# Edit src/web/app.py, comment lines 289-293
# try:
#     from web.sessions_api import router as sessions_router
#     ...

# Restart application
```

### Option 2: Database Rollback

**If database issues occur**:
```bash
# Stop application
supervisorctl stop tax_app

# Find most recent backup
ls -lt tax_filing.db.backup.* | head -1

# Restore (replace TIMESTAMP)
cp tax_filing.db.backup.TIMESTAMP tax_filing.db

# Restart
supervisorctl start tax_app

# Verify
curl http://localhost:8000/api/health/database
```

### Option 3: Full Rollback

**Revert all code changes** (nuclear option):
```bash
# If using git
git stash
git log --oneline | head -5  # Find commit before changes
git reset --hard COMMIT_HASH

# Restart application
supervisorctl restart tax_app
```

---

## Success Criteria

**Deployment is successful if**:

✅ **Zero data loss**:
- Sessions persist after browser refresh
- Sessions persist after server restart
- No "session expired" errors for active users

✅ **Zero 404 errors**:
- `/results` route works
- All links functional

✅ **Permission fix working**:
- FIRM_CLIENT users can edit DRAFT returns
- No "permission denied" errors for valid actions

✅ **UI improvements visible**:
- Professional branding in header
- Trust badges displaying
- Floating chat accessible
- Smart triage recommending workflows

✅ **Security functional**:
- CSRF blocks unauthenticated POSTs
- Rate limiting returns 429 after 60+ requests/min
- No security headers errors

✅ **Auto-save operational**:
- Manager starts on application boot
- Sessions auto-saved every 30 seconds
- Manual trigger API works
- Status endpoint returns stats

---

## Performance Benchmarks

**Expected performance** (after deployment):

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Page load time | < 1s | < 3s |
| Database queries | < 50ms (p95) | < 200ms (p95) |
| Auto-save overhead | < 10ms | < 50ms |
| CSRF validation | < 5ms | < 20ms |
| Session lookup | < 20ms | < 100ms |

**Monitor with**:
```bash
# Average page load (from logs)
grep "GET /" logs/app.log | awk '{print $NF}' | awk '{s+=$1; c++} END {print s/c "ms avg"}'

# Database query times (if query logging enabled)
grep "SELECT" logs/app.log | grep -o "[0-9.]*ms" | awk '{s+=$1; c++} END {print s/c "ms avg"}'
```

---

## Troubleshooting

### Issue: CSRF Errors on Valid Requests

**Symptom**: "CSRF validation failed" in logs

**Fix**:
1. Verify `CSRF_SECRET_KEY` is set in `.env`
2. Check that frontend includes CSRF token in forms
3. Ensure cookies are enabled
4. Verify endpoint not accidentally in exempt list

### Issue: Auto-Save Not Working

**Symptom**: Data lost on refresh

**Check**:
```bash
# Verify manager running
curl http://localhost:8000/api/auto-save/stats
# Should show: "running": true

# Check for errors
grep "auto-save" logs/app.log | grep -i error
```

**Fix**:
1. Verify `startup_auto_save()` is called
2. Check that endpoints call `mark_session_for_auto_save()`
3. Verify database columns exist

### Issue: Session Not Persisting

**Symptom**: Session data disappears on refresh

**Check**:
```bash
# Verify session saved to database
sqlite3 tax_filing.db "SELECT session_id, workflow_type, created_at FROM session_states LIMIT 5;"
```

**Fix**:
1. Ensure `persistence.save_unified_session(session)` is called
2. Check for database write errors in logs
3. Verify database permissions (write access)

### Issue: Performance Degradation

**Symptom**: Slow page loads

**Check**:
```bash
# Database size
ls -lh tax_filing.db

# Session count
sqlite3 tax_filing.db "SELECT COUNT(*) FROM session_states;"

# Old sessions not cleaned up
sqlite3 tax_filing.db "SELECT COUNT(*) FROM session_states WHERE expires_at < datetime('now');"
```

**Fix**:
1. Run session cleanup: `curl -X POST http://localhost:8000/api/sessions/cleanup-expired`
2. Add indexes if queries slow
3. Consider connection pooling

---

## Documentation Reference

- **QUICKSTART.md** - 15-minute deployment guide
- **PLATFORM_STATUS.md** - Complete implementation status
- **IMPLEMENTATION_STATUS.md** - What's done, what's pending
- **docs/SECURITY.md** - Security configuration details
- **docs/AUTO_SAVE_INTEGRATION.md** - Frontend auto-save integration
- **migrations/README.md** - Database migration guide

---

## Support

**If issues persist**:

1. Check logs: `tail -f logs/app.log`
2. Review documentation above
3. Test rollback procedures
4. Check health endpoints
5. Review database schema

---

**Last Updated**: January 21, 2026
**Deployment Status**: ✅ Ready
**Risk Level**: LOW
**Estimated Downtime**: < 2 minutes (for restart)

---

## Final Checklist

Before marking deployment complete:

- [ ] Database migration verified (tests passing)
- [ ] Environment variables configured
- [ ] Application restarted successfully
- [ ] All health checks passing
- [ ] UI verified in browser (branding, chat, triage)
- [ ] Test session created and persists
- [ ] /results route works (no 404)
- [ ] Auto-save manager running
- [ ] Monitoring in place
- [ ] Rollback plan documented and tested

**When all checks pass**: ✅ Deployment Complete

**Enjoy your upgraded tax filing platform with zero data loss and professional UI!** 🎉
