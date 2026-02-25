# Tax Year Inconsistency Fix Design Document

**Date:** 2026-02-25
**Status:** Implemented
**Approach:** Direct Fix (Approach A)

## Overview

Fix tax year default inconsistencies where 7 files default to 2024 while the rest of the codebase correctly uses 2025. This causes calculations to use the wrong year's rules when tax_year isn't explicitly passed.

## Problem

The SWOT analysis identified "Tax Year Hardcoded Inconsistently" as a Risk 8/10 issue:
- `orchestrator.py` line 57: `tax_year: int = 2024`
- Calculator engine uses 2025 rules
- State modules and other services use 2025

This mismatch means new sessions created without explicit tax_year will calculate using 2024 rules instead of 2025.

## Design

### Files to Update

| File | Line | Current | New |
|------|------|---------|-----|
| `src/smart_tax/orchestrator.py` | 57 | `tax_year: int = 2024` | `tax_year: int = 2025` |
| `src/smart_tax/orchestrator.py` | 159 | `tax_year: int = 2024` | `tax_year: int = 2025` |
| `src/smart_tax/document_processor.py` | 214 | `tax_year: int = 2024` | `tax_year: int = 2025` |
| `src/core/api/scenarios_routes.py` | 123 | `tax_year: int = 2024` | `tax_year: int = 2025` |
| `src/core/api/scenarios_routes.py` | 245 | `.get("tax_year", 2024)` | `.get("tax_year", 2025)` |
| `src/core/api/scenarios_routes.py` | 440 | `.get("tax_year", 2024)` | `.get("tax_year", 2025)` |
| `src/core/services/test_data_init.py` | 534 | `"tax_year": 2024` | `"tax_year": 2025` |

### Intentionally Unchanged

The following 2024 references are correct and should NOT be changed:
- `src/services/tax_return_service.py:555` - Prior year data for carryforward
- `src/services/async_tax_return_service.py:463` - Prior year data for carryforward
- `src/smart_tax/question_generator.py:310` - Question about 2024 CTC advance payments (prior year)

## Testing Strategy

1. Run existing test suite to verify no regressions
2. Verify orchestrator creates sessions with tax_year=2025 by default
3. Verify scenario API uses 2025 defaults

## Files Changed

| File | Action | Lines Changed |
|------|--------|---------------|
| `src/smart_tax/orchestrator.py` | Modify | 2 |
| `src/smart_tax/document_processor.py` | Modify | 1 |
| `src/core/api/scenarios_routes.py` | Modify | 3 |
| `src/core/services/test_data_init.py` | Modify | 1 |

**Total: 7 line changes across 4 files**

## Out of Scope

- Centralized `DEFAULT_TAX_YEAR` constant (unnecessary complexity)
- Modifying prior year references (intentionally 2024)
- Adding tax year validation logic

## Approval

- [x] Design approved

Ready for implementation planning.
