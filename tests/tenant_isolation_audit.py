#!/usr/bin/env python3
"""
Tenant Isolation Audit

Critical security audit for CPA multi-tenancy.
Ensures no data leakage between firms.
"""

import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class TenantIsolationAudit:
    def __init__(self):
        self.critical_findings = []
        self.warnings = []
        self.safe_queries = []

    def audit_file(self, filepath: Path, table_names: list):
        """Audit a Python file for tenant isolation"""
        if not filepath.exists():
            return

        content = filepath.read_text()
        lines = content.split('\n')

        # Find all SELECT/UPDATE/DELETE queries
        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            # Find queries
            for table in table_names:
                patterns = [
                    f"SELECT.*FROM {table}",
                    f"UPDATE {table} SET",
                    f"DELETE FROM {table}",
                ]

                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Check if this query filters by tenant_id
                        # Look ahead up to 10 lines for WHERE clause
                        query_block = '\n'.join(lines[i-1:min(i+10, len(lines))])

                        if 'tenant_id' in query_block:
                            self.safe_queries.append({
                                'file': filepath.name,
                                'line': i,
                                'query': line.strip()[:80],
                                'table': table
                            })
                        elif table in ['schema_migrations', 'sqlite_sequence']:
                            # System tables don't need tenant_id
                            continue
                        else:
                            # Check if it's in a function that receives tenant_id
                            func_start = max(0, i - 50)
                            func_block = '\n'.join(lines[func_start:i])

                            if 'tenant_id: str' in func_block or 'tenant_id=' in func_block:
                                # Function has tenant_id parameter (likely safe)
                                self.warnings.append({
                                    'file': filepath.name,
                                    'line': i,
                                    'query': line.strip()[:80],
                                    'table': table,
                                    'note': 'Has tenant_id param but not in WHERE'
                                })
                            else:
                                self.critical_findings.append({
                                    'file': filepath.name,
                                    'line': i,
                                    'query': line.strip()[:80],
                                    'table': table,
                                    'note': 'No tenant_id filter - CROSS-TENANT ACCESS POSSIBLE'
                                })

    def run(self):
        print(f"\n{BLUE}{'='*70}{RESET}")
        print(f"{BLUE}TENANT ISOLATION AUDIT{RESET}")
        print(f"{BLUE}Critical Security Check for CPA Multi-Tenancy{RESET}")
        print(f"{BLUE}{'='*70}{RESET}\n")

        # Tables that MUST be tenant-isolated
        tenant_tables = [
            'session_states',
            'session_tax_returns',
            'document_processing',
            'return_status',
            'audit_trails',
            'session_transfers',
        ]

        # Files to audit
        files_to_audit = [
            project_root / 'src/database/session_persistence.py',
            project_root / 'src/database/models.py',
            project_root / 'src/web/app.py',
            project_root / 'src/cpa_panel' / 'api' / 'returns.py',
        ]

        for filepath in files_to_audit:
            if filepath.exists():
                print(f"Auditing: {filepath.name}...")
                self.audit_file(filepath, tenant_tables)

        # Print results
        print(f"\n{BLUE}{'='*70}{RESET}")
        print(f"{BLUE}AUDIT RESULTS{RESET}")
        print(f"{BLUE}{'='*70}{RESET}\n")

        print(f"{GREEN}✅ SAFE QUERIES: {len(self.safe_queries)}{RESET}")
        print(f"{YELLOW}⚠️  WARNINGS: {len(self.warnings)}{RESET}")
        print(f"{RED}❌ CRITICAL: {len(self.critical_findings)}{RESET}\n")

        if self.critical_findings:
            print(f"{RED}CRITICAL FINDINGS (DATA LEAKAGE RISK):{RESET}\n")
            for finding in self.critical_findings:
                print(f"{RED}❌ {finding['file']}:{finding['line']}{RESET}")
                print(f"   Table: {finding['table']}")
                print(f"   Query: {finding['query']}")
                print(f"   Risk: {finding['note']}\n")

        if self.warnings:
            print(f"{YELLOW}WARNINGS (VERIFY MANUALLY):{RESET}\n")
            for warning in self.warnings:
                print(f"{YELLOW}⚠️  {warning['file']}:{warning['line']}{RESET}")
                print(f"   Table: {warning['table']}")
                print(f"   Query: {warning['query']}")
                print(f"   Note: {warning['note']}\n")

        # Recommendations
        print(f"{BLUE}{'='*70}{RESET}")
        print(f"{BLUE}RECOMMENDATIONS{RESET}")
        print(f"{BLUE}{'='*70}{RESET}\n")

        if self.critical_findings:
            print(f"{RED}⛔ BLOCKER: Critical findings must be fixed before CPA launch{RESET}\n")
            print("Fix pattern:")
            print("```python")
            print("# BEFORE (unsafe)")
            print("cursor.execute('SELECT * FROM session_states WHERE user_id = ?', (user_id,))")
            print()
            print("# AFTER (safe)")
            print("cursor.execute('''")
            print("    SELECT * FROM session_states")
            print("    WHERE user_id = ? AND tenant_id = ?")
            print("''', (user_id, tenant_id))")
            print("```\n")

        if self.warnings:
            print(f"{YELLOW}Review warnings manually:{RESET}")
            print("- Verify function has tenant_id parameter")
            print("- Ensure parameter is actually used in query")
            print("- Add tenant_id to WHERE clause if missing\n")

        print(f"{GREEN}Safe queries:{RESET}")
        print(f"These {len(self.safe_queries)} queries properly filter by tenant_id ✅\n")

        # Final verdict
        print(f"{BLUE}{'='*70}{RESET}")
        if self.critical_findings:
            print(f"{RED}❌ FAILED - NOT SAFE FOR CPA MULTI-TENANCY{RESET}")
            print(f"{RED}Fix {len(self.critical_findings)} critical issues before launch{RESET}")
            return False
        elif self.warnings:
            print(f"{YELLOW}⚠️  CONDITIONAL PASS - Manual review required{RESET}")
            print(f"{YELLOW}Review {len(self.warnings)} warnings{RESET}")
            return True
        else:
            print(f"{GREEN}✅ PASSED - Tenant isolation looks good!{RESET}")
            return True


if __name__ == "__main__":
    audit = TenantIsolationAudit()
    passed = audit.run()
    sys.exit(0 if passed else 1)
