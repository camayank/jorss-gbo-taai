# Auto-Save Integration Guide

## Overview

The auto-save system provides three layers of data protection:

1. **Background Auto-Save**: Runs every 30 seconds on the server (no user action required)
2. **Manual Trigger**: Frontend can trigger immediate save with user feedback
3. **On-Submit Save**: Explicit saves during form submissions

---

## Server-Side (Already Configured)

### Automatic Background Saves

The `AutoSaveManager` runs as a background task and automatically saves pending sessions every 30 seconds.

**Configuration** (`src/web/app.py`):
```python
@app.on_event("startup")
async def startup_auto_save():
    auto_save = get_auto_save_manager()
    asyncio.create_task(auto_save.start())
```

### Marking Sessions for Auto-Save

After modifying a session, mark it for auto-save:

```python
from src.web.auto_save import mark_session_for_auto_save

# After creating/updating session
session = UnifiedFilingSession(...)
persistence.save_unified_session(session)
mark_session_for_auto_save(session)  # Queue for next auto-save cycle
```

**Already integrated in**:
- ✅ Express Lane API (`src/web/express_lane_api.py`)
- 🔲 Smart Tax API (TODO)
- 🔲 AI Chat API (TODO)
- 🔲 Traditional Filing Wizard (TODO)

---

## Frontend Integration

### Option 1: Periodic Auto-Save (Recommended)

Save form data every 30 seconds while user is actively working:

```javascript
// Auto-save manager for filing wizard
class FilingAutoSave {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.isDirty = false;
        this.isSaving = false;
        this.lastSaveTime = null;
        this.intervalId = null;
    }

    start() {
        // Save every 30 seconds
        this.intervalId = setInterval(() => {
            if (this.isDirty && !this.isSaving) {
                this.save();
            }
        }, 30000);

        console.log('Auto-save started (30s interval)');
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    markDirty() {
        this.isDirty = true;
    }

    async save() {
        if (!this.isDirty || this.isSaving) {
            return;
        }

        this.isSaving = true;
        this.showSavingIndicator();

        try {
            const response = await fetch('/api/auto-save/trigger', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });

            const result = await response.json();

            if (result.success) {
                this.isDirty = false;
                this.lastSaveTime = new Date();
                this.showSavedIndicator();
            } else {
                this.showErrorIndicator();
            }
        } catch (error) {
            console.error('Auto-save failed:', error);
            this.showErrorIndicator();
        } finally {
            this.isSaving = false;
        }
    }

    showSavingIndicator() {
        // Update UI to show "Saving..."
        const indicator = document.getElementById('auto-save-status');
        if (indicator) {
            indicator.textContent = '💾 Saving...';
            indicator.style.color = '#718096';
        }
    }

    showSavedIndicator() {
        // Update UI to show "Saved"
        const indicator = document.getElementById('auto-save-status');
        if (indicator) {
            indicator.textContent = '✓ Saved';
            indicator.style.color = '#48bb78';

            // Fade out after 2 seconds
            setTimeout(() => {
                indicator.textContent = '';
            }, 2000);
        }
    }

    showErrorIndicator() {
        // Update UI to show error
        const indicator = document.getElementById('auto-save-status');
        if (indicator) {
            indicator.textContent = '⚠️ Save failed';
            indicator.style.color = '#f56565';
        }
    }
}

// Initialize auto-save when session is created
const autoSave = new FilingAutoSave(state.sessionId);
autoSave.start();

// Mark dirty whenever form data changes
document.querySelectorAll('input, select, textarea').forEach(input => {
    input.addEventListener('change', () => {
        autoSave.markDirty();
    });
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    autoSave.stop();
});
```

### HTML Status Indicator

Add this to your template header:

```html
<div class="auto-save-status" id="auto-save-status"></div>

<style>
.auto-save-status {
    position: fixed;
    top: 16px;
    right: 16px;
    padding: 8px 16px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    font-size: 14px;
    font-weight: 600;
    z-index: 1000;
    transition: opacity 0.3s ease;
}

.auto-save-status:empty {
    opacity: 0;
    pointer-events: none;
}
</style>
```

---

### Option 2: Save on Form Blur

Save immediately when user leaves a form field:

```javascript
document.querySelectorAll('input, select, textarea').forEach(input => {
    let debounceTimer;

    input.addEventListener('blur', () => {
        // Clear any existing timer
        clearTimeout(debounceTimer);

        // Debounce: wait 500ms after user stops typing
        debounceTimer = setTimeout(async () => {
            await fetch('/api/auto-save/trigger', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_id: sessionId})
            });
        }, 500);
    });
});
```

---

### Option 3: Save on Navigation

Save before user navigates to next step:

```javascript
function goToNextStep() {
    // Save current step data first
    await fetch('/api/auto-save/trigger', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: sessionId})
    });

    // Then navigate
    showStep(currentStep + 1);
}
```

---

## API Endpoints

### POST /api/auto-save/trigger

Manually trigger auto-save for a session.

**Request**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Session 550e8400... saved successfully",
  "last_save_time": "2026-01-21T14:30:00"
}
```

### GET /api/auto-save/stats

Get auto-save manager statistics (for monitoring/debugging).

**Response**:
```json
{
  "running": true,
  "pending_count": 3,
  "total_saves": 1247,
  "failed_saves": 2,
  "save_interval_seconds": 30
}
```

### POST /api/auto-save/flush

Force immediate flush of all pending saves (admin endpoint).

**Response**:
```json
{
  "success": true,
  "message": "Flushed 5 pending saves",
  "saved_count": 5
}
```

---

## Testing Auto-Save

### Manual Test

1. Start the application
2. Create a new filing session
3. Fill out some form data
4. Wait 30 seconds
5. Check server logs for "Auto-saved N sessions"
6. Refresh the page - data should still be there

### Check Status

```bash
# Check auto-save stats
curl http://localhost:8000/api/auto-save/stats

# Manually trigger save
curl -X POST http://localhost:8000/api/auto-save/trigger \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your-session-id"}'

# Force flush all pending
curl -X POST http://localhost:8000/api/auto-save/flush
```

### Monitor Logs

```bash
# Watch for auto-save activity
tail -f logs/app.log | grep -i "auto-save"

# Expected output:
# [INFO] Auto-save manager started (interval: 30s)
# [DEBUG] Session abc123 marked for auto-save (1 pending)
# [INFO] Auto-saved 1 sessions (0 still pending)
```

---

## Configuration

### Change Auto-Save Interval

In `src/web/app.py`:

```python
@app.on_event("startup")
async def startup_auto_save():
    from src.web.auto_save import initialize_auto_save

    # Custom configuration
    auto_save = initialize_auto_save(
        save_interval_seconds=60,  # Save every 60 seconds
        max_retry_attempts=5,      # Retry up to 5 times
        batch_size=20              # Save up to 20 sessions per batch
    )

    asyncio.create_task(auto_save.start())
```

### Environment Variables

Add to `.env`:

```bash
# Auto-save configuration
AUTO_SAVE_INTERVAL=30          # Seconds between auto-saves
AUTO_SAVE_MAX_RETRIES=3        # Max retry attempts
AUTO_SAVE_BATCH_SIZE=10        # Sessions per batch
AUTO_SAVE_ENABLED=true         # Enable/disable auto-save
```

---

## Troubleshooting

### Auto-Save Not Working

**Check if manager is running**:
```bash
curl http://localhost:8000/api/auto-save/stats
```

Should return `"running": true`.

**Check server logs**:
```bash
grep "auto-save" logs/app.log
```

Should see:
- "Auto-save manager started"
- "Auto-saved N sessions" (every 30 seconds if there are pending saves)

### Data Not Persisting

1. **Verify session is marked for auto-save**:
   - Check that `mark_session_for_auto_save(session)` is called after session updates

2. **Check for database errors**:
   ```bash
   grep "Failed to save session" logs/app.log
   ```

3. **Verify database columns exist**:
   ```bash
   sqlite3 tax_filing.db "PRAGMA table_info(session_states);"
   ```

   Should include: `user_id`, `workflow_type`, `return_id`, `is_anonymous`

---

## Performance Considerations

### Database Load

- Auto-save uses **batched writes** (max 10 sessions per cycle)
- **Optimistic locking** prevents conflicts from concurrent edits
- Failed saves are retried up to 3 times

### Frontend Impact

- Manual triggers are **debounced** (500ms)
- Status indicator uses **minimal DOM updates**
- No blocking - saves happen asynchronously

### Network Traffic

- Each auto-save trigger: ~200 bytes request + response
- Background saves: No network traffic (server-side only)
- Recommended: Use background saves, manual trigger only for important milestones

---

## Best Practices

1. **Start auto-save on session creation**
   ```javascript
   const autoSave = new FilingAutoSave(sessionId);
   autoSave.start();
   ```

2. **Mark dirty on any data change**
   ```javascript
   input.addEventListener('change', () => autoSave.markDirty());
   ```

3. **Stop on page unload**
   ```javascript
   window.addEventListener('beforeunload', () => autoSave.stop());
   ```

4. **Show visual feedback**
   - "💾 Saving..." during save
   - "✓ Saved" on success
   - "⚠️ Save failed" on error

5. **Don't block user flow**
   - Auto-save runs asynchronously
   - User can continue working while save happens
   - Only block on critical actions (final submission)

---

## Migration Checklist

To add auto-save to an existing workflow:

- [ ] Server-side:
  - [ ] Import `mark_session_for_auto_save`
  - [ ] Call after `persistence.save_unified_session(session)`
  - [ ] Test that sessions appear in pending queue

- [ ] Frontend:
  - [ ] Add `FilingAutoSave` class to page JavaScript
  - [ ] Initialize on session creation
  - [ ] Mark dirty on form changes
  - [ ] Add status indicator to UI
  - [ ] Test that visual feedback appears

- [ ] Testing:
  - [ ] Verify auto-save triggers every 30s
  - [ ] Test browser refresh preserves data
  - [ ] Test server restart preserves data
  - [ ] Test concurrent edits (optimistic locking)

---

**Status**: ✅ Auto-save infrastructure complete and ready for integration.

**Already integrated in**: Express Lane API
**Next**: Integrate into Smart Tax, AI Chat, and Traditional Wizard
