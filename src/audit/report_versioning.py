"""
Report Versioning and Audit Trail System.

Prompt 6: Report Artifacts - Storage, versioning, linkage.

Provides:
1. Version control for all generated reports
2. Complete audit trail of changes
3. Immutable version history
4. Comparison between versions
5. Linkage between reports and calculation snapshots

Design Principles:
- Every report version is immutable once created
- All changes create new versions (never modify existing)
- Full audit trail with user, timestamp, and reason
- Cryptographic hashes for integrity verification
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from uuid import uuid4
from enum import Enum

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


class ReportType(str, Enum):
    """Types of reports that can be versioned."""
    TAX_RETURN = "tax_return"
    RECOMMENDATION_REPORT = "recommendation_report"
    CALCULATION_BREAKDOWN = "calculation_breakdown"
    COMPARISON_REPORT = "comparison_report"
    AUDIT_REPORT = "audit_report"
    SUMMARY_REPORT = "summary_report"
    DOCUMENT_RECEIPT = "document_receipt"


class ChangeType(str, Enum):
    """Types of changes to reports."""
    CREATED = "created"
    UPDATED = "updated"
    RECALCULATED = "recalculated"
    CORRECTED = "corrected"
    AMENDED = "amended"
    FINALIZED = "finalized"
    EXPORTED = "exported"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class ReportVersion:
    """An immutable version of a report."""
    version_id: str
    report_id: str
    version_number: int
    report_type: str
    tenant_id: str

    # Content
    content_json: str
    content_hash: str

    # Metadata
    created_at: str
    created_by: str
    change_type: str
    change_reason: str

    # Linkage
    snapshot_id: Optional[str]  # Link to calculation snapshot
    previous_version_id: Optional[str]  # Link to previous version

    # Integrity
    integrity_hash: str

    @property
    def content(self) -> Dict[str, Any]:
        """Get content as dictionary."""
        return json.loads(self.content_json) if self.content_json else {}

    def verify_integrity(self) -> bool:
        """Verify the version hasn't been tampered with."""
        computed_hash = compute_version_hash(
            version_id=self.version_id,
            report_id=self.report_id,
            version_number=self.version_number,
            content_hash=self.content_hash,
            created_at=self.created_at
        )
        return computed_hash == self.integrity_hash

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version_id": self.version_id,
            "report_id": self.report_id,
            "version_number": self.version_number,
            "report_type": self.report_type,
            "tenant_id": self.tenant_id,
            "content": self.content,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "change_type": self.change_type,
            "change_reason": self.change_reason,
            "snapshot_id": self.snapshot_id,
            "previous_version_id": self.previous_version_id,
            "integrity_hash": self.integrity_hash,
        }


@dataclass
class AuditEntry:
    """An entry in the audit trail."""
    audit_id: str
    report_id: str
    version_id: str
    tenant_id: str
    timestamp: str
    action: str
    user_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "report_id": self.report_id,
            "version_id": self.version_id,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
        }


def compute_content_hash(content: Dict[str, Any]) -> str:
    """Compute deterministic hash of report content."""
    normalized = json.dumps(content, sort_keys=True, default=str, separators=(',', ':'))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def compute_version_hash(
    version_id: str,
    report_id: str,
    version_number: int,
    content_hash: str,
    created_at: str
) -> str:
    """Compute integrity hash for version."""
    content = f"{version_id}:{report_id}:{version_number}:{content_hash}:{created_at}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


class ReportVersionStore:
    """
    Persistent store for report versions and audit trail.

    Features:
    - Immutable version storage
    - Complete audit trail
    - Version comparison
    - Tenant isolation
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        """Create required tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                -- Report versions table
                CREATE TABLE IF NOT EXISTS report_versions (
                    version_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    report_type TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    content_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT 'system',
                    change_type TEXT NOT NULL,
                    change_reason TEXT DEFAULT '',
                    snapshot_id TEXT,
                    previous_version_id TEXT,
                    integrity_hash TEXT NOT NULL,
                    UNIQUE(report_id, version_number, tenant_id)
                );

                CREATE INDEX IF NOT EXISTS idx_report_versions_report
                    ON report_versions(report_id, version_number);
                CREATE INDEX IF NOT EXISTS idx_report_versions_tenant
                    ON report_versions(tenant_id, report_id);
                CREATE INDEX IF NOT EXISTS idx_report_versions_snapshot
                    ON report_versions(snapshot_id);

                -- Audit trail table
                CREATE TABLE IF NOT EXISTS report_audit_trail (
                    audit_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT 'system',
                    ip_address TEXT,
                    user_agent TEXT,
                    details_json TEXT DEFAULT '{}',
                    FOREIGN KEY (version_id) REFERENCES report_versions(version_id)
                );

                CREATE INDEX IF NOT EXISTS idx_audit_report
                    ON report_audit_trail(report_id);
                CREATE INDEX IF NOT EXISTS idx_audit_tenant
                    ON report_audit_trail(tenant_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_user
                    ON report_audit_trail(user_id, timestamp);
            """)
            conn.commit()

    def create_report(
        self,
        report_id: str,
        report_type: ReportType,
        content: Dict[str, Any],
        tenant_id: str = "default",
        created_by: str = "system",
        change_reason: str = "Initial creation",
        snapshot_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ReportVersion:
        """
        Create a new report (version 1).

        Args:
            report_id: Unique identifier for the report
            report_type: Type of report
            content: Report content as dictionary
            tenant_id: Tenant identifier
            created_by: Who created the report
            change_reason: Reason for creation
            snapshot_id: Link to calculation snapshot
            user_id: User making the request (for audit)
            ip_address: Client IP (for audit)
            user_agent: Client user agent (for audit)

        Returns:
            ReportVersion for the created report
        """
        version = self._create_version(
            report_id=report_id,
            version_number=1,
            report_type=report_type.value,
            content=content,
            tenant_id=tenant_id,
            created_by=created_by,
            change_type=ChangeType.CREATED.value,
            change_reason=change_reason,
            snapshot_id=snapshot_id,
            previous_version_id=None
        )

        # Record in audit trail
        self._record_audit(
            report_id=report_id,
            version_id=version.version_id,
            tenant_id=tenant_id,
            action="report_created",
            user_id=user_id or created_by,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "report_type": report_type.value,
                "change_reason": change_reason,
            }
        )

        return version

    def update_report(
        self,
        report_id: str,
        content: Dict[str, Any],
        tenant_id: str = "default",
        created_by: str = "system",
        change_type: ChangeType = ChangeType.UPDATED,
        change_reason: str = "",
        snapshot_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ReportVersion:
        """
        Create a new version of an existing report.

        Args:
            report_id: Report to update
            content: New content
            tenant_id: Tenant identifier
            created_by: Who created this version
            change_type: Type of change
            change_reason: Reason for change
            snapshot_id: Link to calculation snapshot
            user_id: User making the request (for audit)
            ip_address: Client IP (for audit)
            user_agent: Client user agent (for audit)

        Returns:
            New ReportVersion

        Raises:
            ValueError: If report doesn't exist
        """
        # Get current version
        current = self.get_latest_version(report_id, tenant_id)
        if not current:
            raise ValueError(f"Report {report_id} not found")

        # Create new version
        version = self._create_version(
            report_id=report_id,
            version_number=current.version_number + 1,
            report_type=current.report_type,
            content=content,
            tenant_id=tenant_id,
            created_by=created_by,
            change_type=change_type.value,
            change_reason=change_reason,
            snapshot_id=snapshot_id,
            previous_version_id=current.version_id
        )

        # Record in audit trail
        self._record_audit(
            report_id=report_id,
            version_id=version.version_id,
            tenant_id=tenant_id,
            action=f"report_{change_type.value}",
            user_id=user_id or created_by,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "change_type": change_type.value,
                "change_reason": change_reason,
                "previous_version": current.version_number,
                "new_version": version.version_number,
            }
        )

        return version

    def _create_version(
        self,
        report_id: str,
        version_number: int,
        report_type: str,
        content: Dict[str, Any],
        tenant_id: str,
        created_by: str,
        change_type: str,
        change_reason: str,
        snapshot_id: Optional[str],
        previous_version_id: Optional[str]
    ) -> ReportVersion:
        """Internal method to create and persist a version."""
        version_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        content_json = json.dumps(content, sort_keys=True, default=str)
        content_hash = compute_content_hash(content)
        integrity_hash = compute_version_hash(
            version_id=version_id,
            report_id=report_id,
            version_number=version_number,
            content_hash=content_hash,
            created_at=now
        )

        version = ReportVersion(
            version_id=version_id,
            report_id=report_id,
            version_number=version_number,
            report_type=report_type,
            tenant_id=tenant_id,
            content_json=content_json,
            content_hash=content_hash,
            created_at=now,
            created_by=created_by,
            change_type=change_type,
            change_reason=change_reason,
            snapshot_id=snapshot_id,
            previous_version_id=previous_version_id,
            integrity_hash=integrity_hash
        )

        # Persist
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO report_versions (
                    version_id, report_id, version_number, report_type,
                    tenant_id, content_json, content_hash, created_at,
                    created_by, change_type, change_reason, snapshot_id,
                    previous_version_id, integrity_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version.version_id,
                version.report_id,
                version.version_number,
                version.report_type,
                version.tenant_id,
                version.content_json,
                version.content_hash,
                version.created_at,
                version.created_by,
                version.change_type,
                version.change_reason,
                version.snapshot_id,
                version.previous_version_id,
                version.integrity_hash
            ))
            conn.commit()

        return version

    def _record_audit(
        self,
        report_id: str,
        version_id: str,
        tenant_id: str,
        action: str,
        user_id: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        details: Dict[str, Any]
    ):
        """Record an audit entry."""
        audit_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO report_audit_trail (
                    audit_id, report_id, version_id, tenant_id,
                    timestamp, action, user_id, ip_address,
                    user_agent, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id,
                report_id,
                version_id,
                tenant_id,
                now,
                action,
                user_id,
                ip_address,
                user_agent,
                json.dumps(details, default=str)
            ))
            conn.commit()

    def get_version(
        self,
        version_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[ReportVersion]:
        """Get a specific version by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute(
                    """SELECT * FROM report_versions
                       WHERE version_id = ? AND tenant_id = ?""",
                    (version_id, tenant_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM report_versions WHERE version_id = ?",
                    (version_id,)
                )

            row = cursor.fetchone()
            if row:
                return self._row_to_version(row)
            return None

    def get_latest_version(
        self,
        report_id: str,
        tenant_id: str = "default"
    ) -> Optional[ReportVersion]:
        """Get the latest version of a report."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM report_versions
                   WHERE report_id = ? AND tenant_id = ?
                   ORDER BY version_number DESC LIMIT 1""",
                (report_id, tenant_id)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_version(row)
            return None

    def get_version_history(
        self,
        report_id: str,
        tenant_id: str = "default"
    ) -> List[ReportVersion]:
        """Get all versions of a report in chronological order."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM report_versions
                   WHERE report_id = ? AND tenant_id = ?
                   ORDER BY version_number ASC""",
                (report_id, tenant_id)
            )
            return [self._row_to_version(row) for row in cursor.fetchall()]

    def get_audit_trail(
        self,
        report_id: str,
        tenant_id: str = "default",
        limit: int = 100
    ) -> List[AuditEntry]:
        """Get audit trail for a report."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM report_audit_trail
                   WHERE report_id = ? AND tenant_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (report_id, tenant_id, limit)
            )
            return [self._row_to_audit(row) for row in cursor.fetchall()]

    def compare_versions(
        self,
        version_id_1: str,
        version_id_2: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare two versions and return differences.

        Returns:
            Dictionary with comparison results
        """
        v1 = self.get_version(version_id_1, tenant_id)
        v2 = self.get_version(version_id_2, tenant_id)

        if not v1 or not v2:
            return {"error": "One or both versions not found"}

        if v1.report_id != v2.report_id:
            return {"error": "Versions are for different reports"}

        # Compare content
        content1 = v1.content
        content2 = v2.content

        changes = self._compare_dicts(content1, content2)

        return {
            "report_id": v1.report_id,
            "version_1": {
                "version_id": v1.version_id,
                "version_number": v1.version_number,
                "created_at": v1.created_at,
            },
            "version_2": {
                "version_id": v2.version_id,
                "version_number": v2.version_number,
                "created_at": v2.created_at,
            },
            "changes": changes,
            "has_changes": len(changes) > 0,
        }

    def _compare_dicts(
        self,
        d1: Dict[str, Any],
        d2: Dict[str, Any],
        path: str = ""
    ) -> List[Dict[str, Any]]:
        """Recursively compare two dictionaries."""
        changes = []
        all_keys = set(d1.keys()) | set(d2.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            v1 = d1.get(key)
            v2 = d2.get(key)

            if key not in d1:
                changes.append({
                    "path": current_path,
                    "type": "added",
                    "old_value": None,
                    "new_value": v2
                })
            elif key not in d2:
                changes.append({
                    "path": current_path,
                    "type": "removed",
                    "old_value": v1,
                    "new_value": None
                })
            elif isinstance(v1, dict) and isinstance(v2, dict):
                changes.extend(self._compare_dicts(v1, v2, current_path))
            elif v1 != v2:
                changes.append({
                    "path": current_path,
                    "type": "modified",
                    "old_value": v1,
                    "new_value": v2
                })

        return changes

    def verify_chain_integrity(
        self,
        report_id: str,
        tenant_id: str = "default"
    ) -> Tuple[bool, List[str]]:
        """
        Verify integrity of version chain.

        Checks:
        1. Each version's integrity hash is valid
        2. Version numbers are sequential
        3. Previous version links are correct

        Returns:
            Tuple of (is_valid, list of errors)
        """
        versions = self.get_version_history(report_id, tenant_id)
        errors = []

        if not versions:
            return True, []

        for i, version in enumerate(versions):
            # Verify integrity hash
            if not version.verify_integrity():
                errors.append(f"Version {version.version_number}: Integrity hash mismatch")

            # Verify version number sequence
            expected_num = i + 1
            if version.version_number != expected_num:
                errors.append(
                    f"Version {version.version_number}: Expected version {expected_num}"
                )

            # Verify previous version link
            if i == 0:
                if version.previous_version_id is not None:
                    errors.append("Version 1: Should not have previous_version_id")
            else:
                expected_prev = versions[i - 1].version_id
                if version.previous_version_id != expected_prev:
                    errors.append(
                        f"Version {version.version_number}: Incorrect previous_version_id"
                    )

        return len(errors) == 0, errors

    def _row_to_version(self, row: sqlite3.Row) -> ReportVersion:
        """Convert database row to ReportVersion."""
        return ReportVersion(
            version_id=row["version_id"],
            report_id=row["report_id"],
            version_number=row["version_number"],
            report_type=row["report_type"],
            tenant_id=row["tenant_id"],
            content_json=row["content_json"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            change_type=row["change_type"],
            change_reason=row["change_reason"] or "",
            snapshot_id=row["snapshot_id"],
            previous_version_id=row["previous_version_id"],
            integrity_hash=row["integrity_hash"]
        )

    def _row_to_audit(self, row: sqlite3.Row) -> AuditEntry:
        """Convert database row to AuditEntry."""
        return AuditEntry(
            audit_id=row["audit_id"],
            report_id=row["report_id"],
            version_id=row["version_id"],
            tenant_id=row["tenant_id"],
            timestamp=row["timestamp"],
            action=row["action"],
            user_id=row["user_id"],
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            details=json.loads(row["details_json"]) if row["details_json"] else {}
        )


# Global instance
_report_store: Optional[ReportVersionStore] = None


def get_report_version_store() -> ReportVersionStore:
    """Get the global report version store instance."""
    global _report_store
    if _report_store is None:
        _report_store = ReportVersionStore()
    return _report_store
