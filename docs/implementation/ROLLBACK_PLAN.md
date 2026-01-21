# Rollback Plan - Client UX Upgrade

## Safety Strategy

### Git Checkpoints
Before each major change, create a restore point:
```bash
git add .
git commit -m "Pre-fix: Issue #X - RESTORE POINT"
git tag restore-point-issue-X
```

### Rollback Commands
If something breaks:
```bash
# Option 1: Revert specific commit
git revert <commit-hash>

# Option 2: Reset to restore point
git reset --hard restore-point-issue-X

# Option 3: Restore specific file
git checkout <commit-hash> -- path/to/file.py
```

---

## Issue-Specific Rollback Instructions

### Issue #1: Single Entry Point
**Commit**: TBD
**Files Modified**:
- src/web/app.py (route redirects)
- src/web/templates/*.html (navigation links)

**Rollback**:
```bash
git revert [commit-hash-issue-1]
```

**Test After Rollback**:
- [ ] All original entry points work (/smart-tax, /entry-choice)
- [ ] No 404 errors
- [ ] Sessions still functional

**Affected Features**:
- Entry point routing
- URL structure
- Navigation links

---

### Issue #2: White-Label Branding
**Commit**: TBD
**Files Modified**: TBD

**Rollback**: TBD

---

### Issue #3: Trust Signals
**Commit**: TBD
**Files Modified**: TBD

**Rollback**: TBD

---

## Emergency Rollback (Complete Project)

### If Major Issues Arise

**Step 1: Stop all services**
```bash
# Stop the application
supervisorctl stop tax_app
# or
pkill -f "python.*app.py"
```

**Step 2: Rollback to main branch**
```bash
git checkout main
git reset --hard origin/main
```

**Step 3: Restore database backup**
```bash
# Find latest backup
ls -lt tax_filing.db.backup.* | head -1

# Restore (replace TIMESTAMP)
cp tax_filing.db.backup.TIMESTAMP tax_filing.db
```

**Step 4: Restart services**
```bash
supervisorctl restart tax_app
# or
python src/web/app.py
```

**Step 5: Verify**
```bash
curl http://localhost:8000/api/health
```

---

## Database Rollback

### If Migration Issues
```bash
# Restore database from backup
cp tax_filing.db.backup.pre-ux-upgrade tax_filing.db

# Verify restoration
sqlite3 tax_filing.db "SELECT COUNT(*) FROM session_states;"
```

---

## File-Level Rollback

### Restore Single File
```bash
# See file history
git log --oneline -- path/to/file.py

# Restore to specific version
git checkout <commit-hash> -- path/to/file.py

# Test that file
python -m pytest tests/test_specific_feature.py
```

---

## Monitoring After Rollback

### Verify System Health
- [ ] Application starts without errors
- [ ] All routes respond (200 status)
- [ ] Database queries work
- [ ] No JavaScript console errors
- [ ] User can complete filing flow

### Check Data Integrity
- [ ] Session data readable
- [ ] User data intact
- [ ] No data corruption
- [ ] Audit logs present

---

## Communication Plan

### If Rollback Needed

**Step 1: Notify User**
```
⚠️ ROLLBACK INITIATED
Issue: [Description]
Action: Reverted commit [hash]
Status: [Testing/Complete]
Next: [Action plan]
```

**Step 2: Document Issue**
- What broke
- Why it broke
- How to prevent in future
- Revised approach

**Step 3: Re-approach**
- Analyze root cause
- Create better fix
- Test more thoroughly
- Re-implement carefully

---

## Backup Schedule

### Before Starting Each Sprint
```bash
# Backup code
git tag backup-sprint-X

# Backup database
cp tax_filing.db tax_filing.db.backup.sprint-X.$(date +%Y%m%d)

# Backup configuration
tar -czf config-backup-sprint-X.tar.gz .env src/config/
```

### Daily Backups
```bash
# Automated daily backup (add to cron)
0 2 * * * cp tax_filing.db tax_filing.db.backup.daily.$(date +%Y%m%d)
```

---

## Recovery Time Objectives

- **Single file rollback**: 5 minutes
- **Single issue rollback**: 10 minutes
- **Sprint rollback**: 15 minutes
- **Complete project rollback**: 30 minutes
- **Database restoration**: 10 minutes

---

**Rollback Authority**: User approval required
**Testing After Rollback**: Mandatory
**Documentation**: All rollbacks must be logged
