# ADR-002: Decimal Arithmetic for Tax Calculations

## Status
Accepted

## Context
Tax calculations require precise arithmetic. Floating-point errors (e.g., 0.1 + 0.2 = 0.30000000000000004) are unacceptable for financial calculations that must match IRS forms exactly.

## Decision
All tax amounts use Python's `Decimal` type or integer cents representation. Database columns use `NUMERIC`/`DECIMAL` types.

## Rationale
- IRS forms require exact dollar-and-cent values
- Accumulated rounding errors across many line items could cause mismatches
- Python's Decimal module provides arbitrary precision

## Consequences
- All financial inputs must be converted to Decimal before computation
- JSON serialization requires custom handlers (Decimal → string)
- Database ORM mappings must preserve Decimal types
- NumPy operations on financial data use appropriate precision settings
