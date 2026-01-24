#!/usr/bin/env python3
"""
PII Encryption Migration Script

Encrypts existing unencrypted PII data in the database.
This is a one-time migration for production deployment.

SECURITY: Run this script BEFORE going live with encryption.
After migration, all new data will be automatically encrypted.

Usage:
    # Dry run (preview changes)
    python scripts/migrate_encrypt_pii.py --dry-run

    # Actual migration
    python scripts/migrate_encrypt_pii.py

    # With custom database path
    python scripts/migrate_encrypt_pii.py --db-path /path/to/database.db

Requirements:
    - ENCRYPTION_MASTER_KEY environment variable must be set
    - Database backup recommended before running
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from database.encrypted_fields import (
    encrypt_email, encrypt_phone, encrypt_ssn,
    mask_email, mask_phone, mask_ssn
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Default database path
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "tax_returns.db"

# PII fields to encrypt
PII_FIELDS = {
    'email': (encrypt_email, mask_email),
    'phone': (encrypt_phone, mask_phone),
    'ssn': (encrypt_ssn, mask_ssn),
    'social_security_number': (encrypt_ssn, mask_ssn),
}


class PIIMigration:
    """Handles PII encryption migration."""

    def __init__(self, db_path: Path, dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run
        self.stats = {
            'leads_processed': 0,
            'leads_encrypted': 0,
            'leads_skipped': 0,
            'sessions_processed': 0,
            'sessions_encrypted': 0,
            'sessions_skipped': 0,
            'errors': []
        }

    def run(self):
        """Run the migration."""
        logger.info("=" * 60)
        logger.info("PII ENCRYPTION MIGRATION")
        logger.info("=" * 60)
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info("=" * 60)

        if not self.db_path.exists():
            logger.error(f"Database not found: {self.db_path}")
            return False

        # Check encryption key
        if not os.environ.get("ENCRYPTION_MASTER_KEY"):
            logger.error("ENCRYPTION_MASTER_KEY environment variable not set")
            logger.info("Generate with: python -c \"import secrets; print(secrets.token_hex(32))\"")
            return False

        try:
            self.migrate_leads()
            self.migrate_sessions()
            self.print_summary()
            return len(self.stats['errors']) == 0
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    def migrate_leads(self):
        """Migrate PII in leads table."""
        logger.info("\n--- Migrating Leads ---")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if leads table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='leads'
            """)
            if not cursor.fetchone():
                logger.info("No leads table found - skipping")
                return

            # Get all leads
            cursor.execute("""
                SELECT lead_id, tenant_id, metadata_json
                FROM leads
            """)

            leads = cursor.fetchall()
            logger.info(f"Found {len(leads)} leads to process")

            for lead_id, tenant_id, metadata_json in leads:
                self.stats['leads_processed'] += 1

                if not metadata_json:
                    self.stats['leads_skipped'] += 1
                    continue

                try:
                    metadata = json.loads(metadata_json)

                    # Check if already encrypted
                    if metadata.get('_pii_encrypted'):
                        self.stats['leads_skipped'] += 1
                        continue

                    # Check if has PII to encrypt
                    has_pii = any(field in metadata for field in PII_FIELDS)
                    if not has_pii:
                        self.stats['leads_skipped'] += 1
                        continue

                    # Encrypt PII fields
                    encrypted = self._encrypt_metadata(metadata, tenant_id)

                    if self.dry_run:
                        logger.debug(f"  Would encrypt lead {lead_id}")
                    else:
                        cursor.execute("""
                            UPDATE leads SET metadata_json = ?
                            WHERE lead_id = ?
                        """, (json.dumps(encrypted, default=str), lead_id))

                    self.stats['leads_encrypted'] += 1

                except Exception as e:
                    error_msg = f"Lead {lead_id}: {e}"
                    logger.error(f"  Error: {error_msg}")
                    self.stats['errors'].append(error_msg)

            if not self.dry_run:
                conn.commit()

        logger.info(f"Leads encrypted: {self.stats['leads_encrypted']}")

    def migrate_sessions(self):
        """Migrate PII in session tables."""
        logger.info("\n--- Migrating Sessions ---")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if session_states table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='session_states'
            """)
            if not cursor.fetchone():
                logger.info("No session_states table found - skipping")
                return

            # Get all sessions
            cursor.execute("""
                SELECT session_id, tenant_id, data_json
                FROM session_states
            """)

            sessions = cursor.fetchall()
            logger.info(f"Found {len(sessions)} sessions to process")

            for session_id, tenant_id, data_json in sessions:
                self.stats['sessions_processed'] += 1

                if not data_json:
                    self.stats['sessions_skipped'] += 1
                    continue

                try:
                    data = json.loads(data_json)

                    # Check if already encrypted
                    if data.get('_pii_encrypted'):
                        self.stats['sessions_skipped'] += 1
                        continue

                    # Recursively find and encrypt PII
                    encrypted, changed = self._encrypt_nested(data, tenant_id)

                    if not changed:
                        self.stats['sessions_skipped'] += 1
                        continue

                    if self.dry_run:
                        logger.debug(f"  Would encrypt session {session_id}")
                    else:
                        cursor.execute("""
                            UPDATE session_states SET data_json = ?
                            WHERE session_id = ?
                        """, (json.dumps(encrypted, default=str), session_id))

                    self.stats['sessions_encrypted'] += 1

                except Exception as e:
                    error_msg = f"Session {session_id}: {e}"
                    logger.error(f"  Error: {error_msg}")
                    self.stats['errors'].append(error_msg)

            if not self.dry_run:
                conn.commit()

        logger.info(f"Sessions encrypted: {self.stats['sessions_encrypted']}")

    def _encrypt_metadata(self, metadata: dict, tenant_id: str) -> dict:
        """Encrypt PII fields in metadata."""
        encrypted = metadata.copy()

        for field, (encrypt_fn, mask_fn) in PII_FIELDS.items():
            if field in encrypted and encrypted[field]:
                original = encrypted[field]
                # Skip if already looks encrypted
                if isinstance(original, str) and original.startswith('v1:'):
                    continue
                encrypted[field] = encrypt_fn(original, tenant_id)
                encrypted[f'{field}_masked'] = mask_fn(original)

        encrypted['_pii_encrypted'] = True
        encrypted['_encrypted_at'] = datetime.utcnow().isoformat()

        return encrypted

    def _encrypt_nested(self, data: dict, tenant_id: str, path: str = "") -> tuple:
        """Recursively encrypt PII in nested structures."""
        if not isinstance(data, dict):
            return data, False

        encrypted = data.copy()
        changed = False

        for key, value in data.items():
            if isinstance(value, dict):
                encrypted[key], nested_changed = self._encrypt_nested(value, tenant_id, f"{path}.{key}")
                changed = changed or nested_changed
            elif isinstance(value, list):
                new_list = []
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        enc_item, item_changed = self._encrypt_nested(item, tenant_id, f"{path}.{key}[{i}]")
                        new_list.append(enc_item)
                        changed = changed or item_changed
                    else:
                        new_list.append(item)
                encrypted[key] = new_list
            elif key in PII_FIELDS and value:
                # Skip if already encrypted
                if isinstance(value, str) and value.startswith('v1:'):
                    continue
                encrypt_fn, mask_fn = PII_FIELDS[key]
                encrypted[key] = encrypt_fn(value, tenant_id)
                encrypted[f'{key}_masked'] = mask_fn(value)
                changed = True

        if changed:
            encrypted['_pii_encrypted'] = True

        return encrypted, changed

    def print_summary(self):
        """Print migration summary."""
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)

        logger.info(f"\nLeads:")
        logger.info(f"  Processed: {self.stats['leads_processed']}")
        logger.info(f"  Encrypted: {self.stats['leads_encrypted']}")
        logger.info(f"  Skipped:   {self.stats['leads_skipped']}")

        logger.info(f"\nSessions:")
        logger.info(f"  Processed: {self.stats['sessions_processed']}")
        logger.info(f"  Encrypted: {self.stats['sessions_encrypted']}")
        logger.info(f"  Skipped:   {self.stats['sessions_skipped']}")

        if self.stats['errors']:
            logger.info(f"\nErrors ({len(self.stats['errors'])}):")
            for err in self.stats['errors'][:10]:  # Show first 10
                logger.info(f"  - {err}")
            if len(self.stats['errors']) > 10:
                logger.info(f"  ... and {len(self.stats['errors']) - 10} more")

        if self.dry_run:
            logger.info("\n*** DRY RUN - No changes were made ***")
            logger.info("Run without --dry-run to apply changes")
        else:
            logger.info("\n*** Migration complete ***")

        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Encrypt existing PII data in the database"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying database'
    )
    parser.add_argument(
        '--db-path',
        type=Path,
        default=DEFAULT_DB_PATH,
        help='Path to SQLite database'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    migration = PIIMigration(args.db_path, args.dry_run)
    success = migration.run()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
