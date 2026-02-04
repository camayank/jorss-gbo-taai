# Quick Fix Guide - Advisory Reports

## Critical Issue: Missing reportlab

**Problem**: Advisory API won't load because reportlab is not installed.

**Solution** (2 minutes):

```bash
# 1. Install reportlab
pip install reportlab

# 2. Verify installation
python -c "import reportlab; print('✅ reportlab installed:', reportlab.__version__)"

# 3. Restart server
python run.py
```

**Verify Fix**:
```bash
# Should see this in logs:
# INFO: Advisory Reports API enabled at /api/v1/advisory-reports

# Visit http://localhost:8000/docs
# You should see advisory-reports endpoints
```

---

## Optional: Install All PDF Dependencies

```bash
# Full set of dependencies for PDF generation
pip install reportlab Pillow

# Or update requirements.txt
echo "reportlab>=3.6.0" >> requirements.txt
echo "Pillow>=9.0.0" >> requirements.txt
pip install -r requirements.txt
```

---

## Test After Fix

```bash
# Run automated tests
pytest tests/test_advisory_frontend_integration.py -v

# Expected: 14/15 tests pass (93%)

# Manual test:
# 1. Visit http://localhost:8000/file
# 2. Complete tax return
# 3. Click "Generate Professional Report" on Step 6
# 4. Report should open in new tab
# 5. PDF should be downloadable
```

---

## If Still Having Issues

### Check 1: Verify Import Works
```bash
python << EOF
from web.advisory_api import router
print("✅ Advisory API imports successfully")
EOF
```

### Check 2: Verify App Logs
```bash
# Start server and check logs for:
# INFO: Advisory Reports API enabled at /api/v1/advisory-reports

# Should NOT see:
# WARNING: Advisory Reports API not available: No module named 'reportlab'
```

### Check 3: Test API Directly
```bash
curl -X POST http://localhost:8000/api/v1/advisory-reports/test/generate-sample

# Expected: {"report_id": "...", "status": "completed", ...}
```

---

## Common Issues

### Issue: "No module named 'PIL'"
**Fix**: `pip install Pillow`

### Issue: "No module named 'sqlalchemy'"
**Fix**: `pip install sqlalchemy`

### Issue: CSRF token errors
**Fix**: This is expected for POST requests without CSRF tokens. Use browser, not curl.

### Issue: 404 on /advisory-report-preview
**Fix**: Check that you added the route to app.py (should already be there)

---

## Rollback Plan (if needed)

If something breaks, rollback is easy:

```bash
# 1. Remove advisory buttons from index.html
# Comment out lines 10818-10828

# 2. Remove advisory route from app.py
# Comment out lines 924-927

# 3. Restart server
python run.py

# System will work as before, just without advisory reports
```

---

## Success Checklist

- [ ] reportlab installed
- [ ] Server starts without warnings
- [ ] /docs shows advisory endpoints
- [ ] Can generate test report
- [ ] Can view report preview
- [ ] Can download PDF
- [ ] Can view report history

---

**Estimated Fix Time**: 2-5 minutes
**Difficulty**: Easy
**Risk**: Very Low
