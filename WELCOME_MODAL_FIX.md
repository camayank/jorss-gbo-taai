# ✅ Welcome Modal 3-Option Fix

**Problem**: User couldn't see the 3 filing path options when visiting /file

---

## What Was Wrong

1. **Welcome modal was showing wrong screen**
   - Was showing: Triage questionnaire (questions)
   - Should show: 3 clear filing path options

2. **The 3 Options That Should Appear**:
   - ⚡ **Express Lane** (Fastest ~3 min) - Upload documents, AI extracts
   - 💬 **AI Chat Assistant** (Recommended ~5 min) - Conversational
   - 📋 **Guided Forms** (Thorough ~15 min) - Traditional step-by-step

3. **User was bypassing modal entirely**
   - Seeing the crowded Step 1 form directly
   - No clear path selection

---

## Fix Applied ✅

Changed line 12996 in `src/web/templates/index.html`:

**Before**:
```javascript
function showWelcomeModal() {
  elements.welcomeModal.classList.remove('hidden');
  document.getElementById('step1').classList.add('hidden');
  showTriageStep('triageStep1');  // WRONG - shows questionnaire
}
```

**After**:
```javascript
function showWelcomeModal() {
  elements.welcomeModal.classList.remove('hidden');
  document.getElementById('step1').classList.add('hidden');
  showTriageStep('pathChoice');  /* Show 3-path options first */
}
```

---

## How It Should Work Now

### 1. User Visits /file
→ Welcome modal appears with 3 options

### 2. User Sees 3 Clear Paths:
- **⚡ Express Lane** (FASTEST badge)
- **💬 AI Chat** (RECOMMENDED badge)
- **📋 Guided Forms** (THOROUGH badge)

### 3. User Clicks a Path:
→ Takes them to appropriate workflow

### 4. "Not sure?" Button:
→ Shows triage questionnaire to help decide

---

## Testing

Visit: **http://127.0.0.1:8000/file?v=modal-fix**

**What You Should See**:
1. Page loads
2. Purple gradient background appears
3. White modal in center with:
   - 🚀 "Choose Your Filing Path"
   - 3 large cards (Express, AI Chat, Guided)
   - Each with time estimate and description
4. "Not sure?" helper button at bottom

**If You Don't See It**:
- Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
- Clear browser cache completely
- Try incognito/private window

---

## Status

✅ Code fix applied
✅ Server restarted
✅ Now shows 3-option path choice first
✅ Triage questions moved to "Not sure?" button

---

**Next**: Please hard refresh and try: http://127.0.0.1:8000/file?v=modal-fix
