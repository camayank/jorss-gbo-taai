"""
Immutable Snapshot System.

Prompt 3: Scenario + Snapshot - Enhanced immutability guarantees.

Provides:
1. Cryptographic sealing - snapshots cannot be modified after creation
2. Chain integrity - each snapshot references its predecessor's hash
3. Tamper detection - verification of snapshot integrity
4. Audit trail - complete history with chain verification

Design Principles:
- Once sealed, a snapshot CANNOT be modified
- Each snapshot includes a hash of the previous snapshot (chain)
- Any modification breaks the chain integrity
- All operations are idempotent (same input = same output)
"""

import hashlib
import json
import hmac
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from uuid import uuid4
import os

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"

# Secret key for HMAC - production enforced
def _get_snapshot_secret() -> str:
    """Get snapshot signing key with production enforcement."""
    import logging
    logger = logging.getLogger(__name__)

    secret = os.environ.get("SNAPSHOT_SECRET_KEY")
    is_production = os.environ.get("ENVIRONMENT", "development").lower() == "production"

    if not secret:
        if is_production:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: SNAPSHOT_SECRET_KEY environment variable is required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        logger.warning(
            "SNAPSHOT_SECRET_KEY not set - using insecure development default."
        )
        return "development-only-snapshot-secret-key"

    if len(secret) < 32:
        raise ValueError("SNAPSHOT_SECRET_KEY must be at least 32 characters")

    return secret


_SECRET_KEY = _get_snapshot_secret()


@dataclass(frozen=True)
class ImmutableSnapshot:
    """
    A truly immutable calculation snapshot.

    This dataclass is frozen - no attributes can be modified after creation.
    Uses hash chain for integrity verification.
    """
    snapshot_id: str
    return_id: str
    tenant_id: str
    tax_year: int
    filing_status: str

    # Frozen input data (as JSON string for immutability)
    input_json: str
    input_hash: str

    # Frozen result data (as JSON string for immutability)
    result_json: str

    # Key calculated values for quick access
    total_tax: float
    effective_rate: float
    taxable_income: float
    total_credits: float

    # Chain integrity
    previous_hash: str  # Hash of previous snapshot in chain (empty if first)

    # Cryptographic seal
    created_at: str  # ISO format timestamp
    sealed_at: str  # When the snapshot was sealed
    integrity_hash: str  # SHA-256 of all data
    signature: str  # HMAC signature for tamper detection

    # Metadata
    version: int = 1
    snapshot_type: str = "calculation"  # calculation, scenario, what_if

    @property
    def input_data(self) -> Dict[str, Any]:
        """Get input data as dictionary."""
        return json.loads(self.input_json) if self.input_json else {}

    @property
    def result_data(self) -> Dict[str, Any]:
        """Get result data as dictionary."""
        return json.loads(self.result_json) if self.result_json else {}

    def verify_integrity(self) -> bool:
        """Verify the snapshot hasn't been tampered with."""
        computed_hash = compute_integrity_hash(
            snapshot_id=self.snapshot_id,
            return_id=self.return_id,
            tenant_id=self.tenant_id,
            input_hash=self.input_hash,
            result_json=self.result_json,
            previous_hash=self.previous_hash,
            created_at=self.created_at
        )
        return computed_hash == self.integrity_hash

    def verify_signature(self) -> bool:
        """Verify the cryptographic signature."""
        computed_sig = compute_signature(self.integrity_hash)
        return hmac.compare_digest(computed_sig, self.signature)

    def is_valid(self) -> Tuple[bool, List[str]]:
        """
        Full validation of snapshot integrity.

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        if not self.verify_integrity():
            errors.append("Integrity hash mismatch - data may have been modified")

        if not self.verify_signature():
            errors.append("Signature verification failed - possible tampering")

        # Verify input hash matches input data
        computed_input_hash = compute_input_hash(self.input_json)
        if computed_input_hash != self.input_hash:
            errors.append("Input hash mismatch - input data corrupted")

        return len(errors) == 0, errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "snapshot_id": self.snapshot_id,
            "return_id": self.return_id,
            "tenant_id": self.tenant_id,
            "tax_year": self.tax_year,
            "filing_status": self.filing_status,
            "input_data": self.input_data,
            "input_hash": self.input_hash,
            "result_data": self.result_data,
            "total_tax": self.total_tax,
            "effective_rate": self.effective_rate,
            "taxable_income": self.taxable_income,
            "total_credits": self.total_credits,
            "previous_hash": self.previous_hash,
            "created_at": self.created_at,
            "sealed_at": self.sealed_at,
            "integrity_hash": self.integrity_hash,
            "signature": self.signature,
            "version": self.version,
            "snapshot_type": self.snapshot_type,
        }


def compute_input_hash(input_json: str) -> str:
    """Compute deterministic hash of input data."""
    return hashlib.sha256(input_json.encode('utf-8')).hexdigest()


def compute_integrity_hash(
    snapshot_id: str,
    return_id: str,
    tenant_id: str,
    input_hash: str,
    result_json: str,
    previous_hash: str,
    created_at: str
) -> str:
    """
    Compute integrity hash from snapshot components.

    This hash covers all critical data to detect tampering.
    """
    content = f"{snapshot_id}:{return_id}:{tenant_id}:{input_hash}:{result_json}:{previous_hash}:{created_at}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def compute_signature(integrity_hash: str) -> str:
    """
    Compute HMAC signature for integrity hash.

    This provides cryptographic proof that the snapshot was created
    by an authorized system.
    """
    return hmac.new(
        _SECRET_KEY.encode('utf-8'),
        integrity_hash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def normalize_input(input_data: Dict[str, Any]) -> str:
    """
    Normalize input data to JSON string.

    Ensures deterministic serialization (sorted keys, consistent formatting).
    """
    return json.dumps(input_data, sort_keys=True, default=str, separators=(',', ':'))


class ImmutableSnapshotStore:
    """
    Persistent store for immutable snapshots with chain verification.

    Key features:
    - Snapshots are stored once and never modified
    - Each snapshot includes hash of previous snapshot
    - Full chain verification available
    - Tenant isolation enforced
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        """Create immutable snapshots table."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS immutable_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    return_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    tax_year INTEGER NOT NULL,
                    filing_status TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    total_tax REAL NOT NULL,
                    effective_rate REAL NOT NULL,
                    taxable_income REAL DEFAULT 0,
                    total_credits REAL DEFAULT 0,
                    previous_hash TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    sealed_at TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    snapshot_type TEXT DEFAULT 'calculation'
                );

                CREATE INDEX IF NOT EXISTS idx_immutable_input_hash
                    ON immutable_snapshots(input_hash);
                CREATE INDEX IF NOT EXISTS idx_immutable_return_id
                    ON immutable_snapshots(return_id);
                CREATE INDEX IF NOT EXISTS idx_immutable_tenant
                    ON immutable_snapshots(tenant_id, return_id);
                CREATE INDEX IF NOT EXISTS idx_immutable_chain
                    ON immutable_snapshots(return_id, created_at);
            """)
            conn.commit()

    def get_by_input_hash(
        self,
        input_hash: str,
        tenant_id: str = "default"
    ) -> Optional[ImmutableSnapshot]:
        """
        Get existing snapshot by input hash.

        Returns existing snapshot if same input was calculated before.
        This ensures idempotency - same input always returns same result.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM immutable_snapshots
                   WHERE input_hash = ? AND tenant_id = ?""",
                (input_hash, tenant_id)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_snapshot(row)
            return None

    def get_latest_for_return(
        self,
        return_id: str,
        tenant_id: str = "default"
    ) -> Optional[ImmutableSnapshot]:
        """Get the most recent snapshot for a return."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM immutable_snapshots
                   WHERE return_id = ? AND tenant_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (return_id, tenant_id)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_snapshot(row)
            return None

    def create_snapshot(
        self,
        return_id: str,
        input_data: Dict[str, Any],
        result_data: Dict[str, Any],
        tax_year: int,
        filing_status: str,
        total_tax: float,
        effective_rate: float,
        taxable_income: float = 0,
        total_credits: float = 0,
        tenant_id: str = "default",
        snapshot_type: str = "calculation"
    ) -> ImmutableSnapshot:
        """
        Create and seal a new immutable snapshot.

        If a snapshot with the same input hash exists, returns
        the existing one (idempotency).

        The snapshot is sealed upon creation and cannot be modified.
        """
        # Normalize input for deterministic hashing
        input_json = normalize_input(input_data)
        input_hash = compute_input_hash(input_json)

        # Check for existing snapshot with same input
        existing = self.get_by_input_hash(input_hash, tenant_id)
        if existing:
            return existing

        # Get previous snapshot's hash for chain
        previous = self.get_latest_for_return(return_id, tenant_id)
        previous_hash = previous.integrity_hash if previous else ""

        # Create snapshot data
        snapshot_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        result_json = json.dumps(result_data, sort_keys=True, default=str)

        # Compute integrity hash
        integrity_hash = compute_integrity_hash(
            snapshot_id=snapshot_id,
            return_id=return_id,
            tenant_id=tenant_id,
            input_hash=input_hash,
            result_json=result_json,
            previous_hash=previous_hash,
            created_at=now
        )

        # Compute signature
        signature = compute_signature(integrity_hash)

        # Create immutable snapshot
        snapshot = ImmutableSnapshot(
            snapshot_id=snapshot_id,
            return_id=return_id,
            tenant_id=tenant_id,
            tax_year=tax_year,
            filing_status=filing_status,
            input_json=input_json,
            input_hash=input_hash,
            result_json=result_json,
            total_tax=total_tax,
            effective_rate=effective_rate,
            taxable_income=taxable_income,
            total_credits=total_credits,
            previous_hash=previous_hash,
            created_at=now,
            sealed_at=now,
            integrity_hash=integrity_hash,
            signature=signature,
            version=1,
            snapshot_type=snapshot_type
        )

        # Persist (single insert, never update)
        self._persist_snapshot(snapshot)

        return snapshot

    def _persist_snapshot(self, snapshot: ImmutableSnapshot):
        """Persist snapshot to database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO immutable_snapshots (
                    snapshot_id, return_id, tenant_id, tax_year, filing_status,
                    input_json, input_hash, result_json, total_tax, effective_rate,
                    taxable_income, total_credits, previous_hash, created_at,
                    sealed_at, integrity_hash, signature, version, snapshot_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.snapshot_id,
                snapshot.return_id,
                snapshot.tenant_id,
                snapshot.tax_year,
                snapshot.filing_status,
                snapshot.input_json,
                snapshot.input_hash,
                snapshot.result_json,
                snapshot.total_tax,
                snapshot.effective_rate,
                snapshot.taxable_income,
                snapshot.total_credits,
                snapshot.previous_hash,
                snapshot.created_at,
                snapshot.sealed_at,
                snapshot.integrity_hash,
                snapshot.signature,
                snapshot.version,
                snapshot.snapshot_type
            ))
            conn.commit()

    def load_snapshot(
        self,
        snapshot_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[ImmutableSnapshot]:
        """Load a snapshot by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute(
                    """SELECT * FROM immutable_snapshots
                       WHERE snapshot_id = ? AND tenant_id = ?""",
                    (snapshot_id, tenant_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM immutable_snapshots WHERE snapshot_id = ?",
                    (snapshot_id,)
                )

            row = cursor.fetchone()
            if row:
                return self._row_to_snapshot(row)
            return None

    def load_chain_for_return(
        self,
        return_id: str,
        tenant_id: str = "default"
    ) -> List[ImmutableSnapshot]:
        """Load all snapshots for a return in chronological order."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM immutable_snapshots
                   WHERE return_id = ? AND tenant_id = ?
                   ORDER BY created_at ASC""",
                (return_id, tenant_id)
            )
            return [self._row_to_snapshot(row) for row in cursor.fetchall()]

    def verify_chain(
        self,
        return_id: str,
        tenant_id: str = "default"
    ) -> Tuple[bool, List[str]]:
        """
        Verify the integrity of the entire snapshot chain.

        Checks:
        1. Each snapshot's integrity hash is valid
        2. Each snapshot's signature is valid
        3. Each snapshot correctly references previous hash

        Returns:
            Tuple of (chain_valid, list of errors)
        """
        chain = self.load_chain_for_return(return_id, tenant_id)
        errors = []

        if not chain:
            return True, []  # Empty chain is valid

        previous_hash = ""
        for i, snapshot in enumerate(chain):
            # Verify individual snapshot
            valid, snap_errors = snapshot.is_valid()
            if not valid:
                errors.extend([f"Snapshot {i+1}: {e}" for e in snap_errors])

            # Verify chain linkage
            if snapshot.previous_hash != previous_hash:
                errors.append(
                    f"Snapshot {i+1}: Chain broken - previous_hash mismatch"
                )

            previous_hash = snapshot.integrity_hash

        return len(errors) == 0, errors

    def _row_to_snapshot(self, row: sqlite3.Row) -> ImmutableSnapshot:
        """Convert database row to ImmutableSnapshot."""
        return ImmutableSnapshot(
            snapshot_id=row["snapshot_id"],
            return_id=row["return_id"],
            tenant_id=row["tenant_id"],
            tax_year=row["tax_year"],
            filing_status=row["filing_status"],
            input_json=row["input_json"],
            input_hash=row["input_hash"],
            result_json=row["result_json"],
            total_tax=row["total_tax"],
            effective_rate=row["effective_rate"],
            taxable_income=row["taxable_income"] or 0,
            total_credits=row["total_credits"] or 0,
            previous_hash=row["previous_hash"] or "",
            created_at=row["created_at"],
            sealed_at=row["sealed_at"],
            integrity_hash=row["integrity_hash"],
            signature=row["signature"],
            version=row["version"] or 1,
            snapshot_type=row["snapshot_type"] or "calculation"
        )


# Global instance
_immutable_store: Optional[ImmutableSnapshotStore] = None


def get_immutable_snapshot_store() -> ImmutableSnapshotStore:
    """Get the global immutable snapshot store instance."""
    global _immutable_store
    if _immutable_store is None:
        _immutable_store = ImmutableSnapshotStore()
    return _immutable_store
