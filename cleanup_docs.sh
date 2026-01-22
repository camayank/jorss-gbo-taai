#!/bin/bash

# Documentation Cleanup Script
# Removes redundant analysis, planning, and status documents
# Keeps only essential documentation

echo "🧹 Starting documentation cleanup..."
echo ""

# Create docs/archive directory for backup
mkdir -p docs/archive

# Count files before
BEFORE=$(find . -maxdepth 1 -name "*.md" -type f | wc -l)

echo "📊 Before: $BEFORE markdown files in root"
echo ""

# =====================================================================
# REDUNDANT STATUS/AUDIT FILES - Move to archive
# =====================================================================

echo "📦 Archiving redundant status/audit files..."

# Multiple status files (keep CPA_LAUNCH_CHECKLIST.md only)
mv -f CLIENT_LAUNCH_READY_STATUS.md docs/archive/ 2>/dev/null
mv -f IMPLEMENTATION_STATUS.md docs/archive/ 2>/dev/null
mv -f PLATFORM_STATUS.md docs/archive/ 2>/dev/null
mv -f BUILD_COMPLETE_STATUS.md docs/archive/ 2>/dev/null
mv -f PHASE_0_DAY1_STATUS.md docs/archive/ 2>/dev/null
mv -f DEPLOYMENT_CONFIDENCE_REPORT.md docs/archive/ 2>/dev/null
mv -f READY_TO_TEST_SUMMARY.md docs/archive/ 2>/dev/null

# Multiple audit files
mv -f CHATBOT_COMPREHENSIVE_AUDIT.md docs/archive/ 2>/dev/null
mv -f CAPABILITY_UTILIZATION_GAPS.md docs/archive/ 2>/dev/null
mv -f EDGE_CASES_COMPREHENSIVE.md docs/archive/ 2>/dev/null
mv -f API_SECURITY_VULNERABILITIES_COMPREHENSIVE.md docs/archive/ 2>/dev/null
mv -f SECURITY_FIXES_APPLIED.md docs/archive/ 2>/dev/null
mv -f UI_BACKEND_AUDIT_REPORT.md docs/archive/ 2>/dev/null
mv -f SENIOR_UX_EXPERT_AUDIT.md docs/archive/ 2>/dev/null
mv -f PREMIUM_FEATURES_AUDIT.md docs/archive/ 2>/dev/null

echo "   ✅ Status/audit files archived"

# =====================================================================
# REDUNDANT PLANNING/FIX FILES
# =====================================================================

echo "📦 Archiving redundant planning/fix files..."

mv -f ACTIONABLE_FIX_PLAN.md docs/archive/ 2>/dev/null
mv -f CRITICAL_FIXES_REQUIRED.md docs/archive/ 2>/dev/null
mv -f CRITICAL_UX_FIXES.md docs/archive/ 2>/dev/null
mv -f CSS_ONLY_10X_TRANSFORMATION_PLAN.md docs/archive/ 2>/dev/null
mv -f DESIGN_POLISH_SPRINT_PLAN.md docs/archive/ 2>/dev/null
mv -f CLIENT_UX_FIXES.md docs/archive/ 2>/dev/null
mv -f QUICKSTART_IMPROVEMENTS.md docs/archive/ 2>/dev/null
mv -f VISUAL_IMPROVEMENTS_GUIDE.md docs/archive/ 2>/dev/null
mv -f WHATS_NEXT.md docs/archive/ 2>/dev/null

echo "   ✅ Planning/fix files archived"

# =====================================================================
# REDUNDANT IMPLEMENTATION/INTEGRATION FILES
# =====================================================================

echo "📦 Archiving redundant implementation files..."

mv -f ADVISORY_IMPLEMENTATION_DETAILED_REPORT.md docs/archive/ 2>/dev/null
mv -f ADVISORY_INTEGRATION_QUICK_PATCH.md docs/archive/ 2>/dev/null
mv -f ADVISORY_REPORT_INTEGRATION_GUIDE.md docs/archive/ 2>/dev/null
mv -f ADVISORY_REPORTS_VISUAL_GUIDE.md docs/archive/ 2>/dev/null
mv -f COMPREHENSIVE_ADVISORY_MESSAGING.md docs/archive/ 2>/dev/null
mv -f CPA_ADVISORY_INTELLIGENCE_SYSTEM.md docs/archive/ 2>/dev/null

echo "   ✅ Implementation files archived"

# =====================================================================
# REDUNDANT ANALYSIS/DEEP DIVE FILES
# =====================================================================

echo "📦 Archiving redundant analysis files..."

mv -f CRITICAL_FIRST_IMPRESSION_DEEP_DIVE.md docs/archive/ 2>/dev/null
mv -f CURRENT_ARCHITECTURE_DEEP_DIVE.md docs/archive/ 2>/dev/null
mv -f SYSTEM_ARCHITECTURE_REVIEW.md docs/archive/ 2>/dev/null
mv -f IDEAL_CLIENT_FLOW_ANALYSIS.md docs/archive/ 2>/dev/null
mv -f CPA_BUSINESS_VALUE.md docs/archive/ 2>/dev/null

echo "   ✅ Analysis files archived"

# =====================================================================
# REDUNDANT COMPLETION/SUMMARY FILES
# =====================================================================

echo "📦 Archiving redundant completion files..."

mv -f CORE_IMPROVEMENTS_COMPLETE.md docs/archive/ 2>/dev/null
mv -f DEPLOYMENT_SUCCESS.md docs/archive/ 2>/dev/null
mv -f SEE_THE_CHANGES.md docs/archive/ 2>/dev/null
mv -f FINAL_SECURITY_REPORT.md docs/archive/ 2>/dev/null

echo "   ✅ Completion files archived"

# =====================================================================
# REDUNDANT TESTING FILES (keep main testing docs)
# =====================================================================

echo "📦 Archiving redundant testing files..."

mv -f END_TO_END_TESTING_CHECKLIST.md docs/archive/ 2>/dev/null
mv -f TEST_BRANDING.md docs/archive/ 2>/dev/null
mv -f CLEAR_BROWSER_CACHE_INSTRUCTIONS.md docs/archive/ 2>/dev/null
mv -f DAY_1_VISUAL_COMPARISON.md docs/archive/ 2>/dev/null

echo "   ✅ Testing files archived"

# =====================================================================
# REDUNDANT DEPLOYMENT FILES (keep DEPLOYMENT_GUIDE.md)
# =====================================================================

echo "📦 Archiving redundant deployment files..."

mv -f DEPLOYMENT_CHECKLIST.md docs/archive/ 2>/dev/null
# Keep DEPLOYMENT_GUIDE.md as primary deployment doc

echo "   ✅ Deployment files archived"

# =====================================================================
# REDUNDANT README/DOCUMENTATION FILES
# =====================================================================

echo "📦 Archiving redundant readme files..."

mv -f README_PLATFORM_COMPLETE.md docs/archive/ 2>/dev/null
mv -f QUICKSTART.md docs/archive/ 2>/dev/null
mv -f SERVER_RUNNING.md docs/archive/ 2>/dev/null

echo "   ✅ Readme files archived"

# =====================================================================
# OLD IMPLEMENTATION LOGS
# =====================================================================

echo "📦 Archiving old implementation logs..."

mv -f CLEANUP_REDUNDANT_FILES.md docs/archive/ 2>/dev/null
mv -f PENDING_SPRINTS_AND_PHASES.md docs/archive/ 2>/dev/null

echo "   ✅ Implementation logs archived"

# Count files after
AFTER=$(find . -maxdepth 1 -name "*.md" -type f | wc -l)
ARCHIVED=$((BEFORE - AFTER))

echo ""
echo "✨ Documentation cleanup complete!"
echo ""
echo "📊 Summary:"
echo "   Before: $BEFORE markdown files"
echo "   After:  $AFTER markdown files"
echo "   Archived: $ARCHIVED files"
echo ""
echo "📂 Archived files saved in: docs/archive/"
echo ""
echo "✅ Essential docs kept:"
echo "   • README.md (main project readme)"
echo "   • DEPLOYMENT_GUIDE.md (deployment instructions)"
echo "   • SECURITY.md (security documentation)"
echo "   • CPA_LAUNCH_CHECKLIST.md (launch checklist)"
echo "   • IMPLEMENTATION_PROGRESS_LOG.md (current progress)"
echo "   • MASTER_VULNERABILITY_AUDIT_COMPLETE.md (security audit)"
echo "   • PERFORMANCE_BOTTLENECKS_COMPREHENSIVE.md (performance guide)"
echo ""
