"""
Tenant Persistence Layer

Database operations for multi-tenant white-labeling system.
Supports SQLite with JSON columns for flexible schema.
"""

import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from .tenant_models import (
    Tenant,
    TenantBranding,
    TenantFeatureFlags,
    CPABranding,
    TenantStatus,
    SubscriptionTier,
)


class TenantPersistence:
    """
    Handles all tenant-related database operations.
    Thread-safe with connection pooling.
    """

    def __init__(self, db_path: str = "./data/tax_returns.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _initialize_schema(self):
        """Create tenant tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Tenants table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    tenant_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    subscription_tier TEXT NOT NULL,
                    branding JSON NOT NULL,
                    features JSON NOT NULL,
                    custom_domain TEXT,
                    custom_domain_verified INTEGER DEFAULT 0,
                    admin_user_id TEXT,
                    admin_email TEXT NOT NULL,
                    stripe_customer_id TEXT,
                    subscription_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata JSON,
                    total_returns INTEGER DEFAULT 0,
                    total_cpas INTEGER DEFAULT 0,
                    total_clients INTEGER DEFAULT 0,
                    storage_used_gb REAL DEFAULT 0.0
                )
            """)

            # CPA branding table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cpa_branding (
                    cpa_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    display_name TEXT,
                    tagline TEXT,
                    accent_color TEXT,
                    profile_photo_url TEXT,
                    signature_image_url TEXT,
                    direct_email TEXT,
                    direct_phone TEXT,
                    office_address TEXT,
                    bio TEXT,
                    credentials JSON,
                    years_experience INTEGER,
                    specializations JSON,
                    welcome_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                )
            """)

            # Domain mapping table (for custom domains)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS domain_mappings (
                    domain TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    verified INTEGER DEFAULT 0,
                    verification_token TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenants(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenant_domain ON tenants(custom_domain)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpa_tenant ON cpa_branding(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_domain_lookup ON domain_mappings(domain)")

            conn.commit()

    # =============================================================================
    # TENANT OPERATIONS
    # =============================================================================

    def create_tenant(self, tenant: Tenant) -> bool:
        """Create a new tenant"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                tenant_dict = tenant.to_dict()

                cursor.execute("""
                    INSERT INTO tenants (
                        tenant_id, tenant_name, status, subscription_tier,
                        branding, features, custom_domain, custom_domain_verified,
                        admin_user_id, admin_email, stripe_customer_id,
                        subscription_expires_at, created_at, updated_at,
                        metadata, total_returns, total_cpas, total_clients,
                        storage_used_gb
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tenant_dict['tenant_id'],
                    tenant_dict['tenant_name'],
                    tenant_dict['status'],
                    tenant_dict['subscription_tier'],
                    json.dumps(tenant_dict['branding']),
                    json.dumps(tenant_dict['features']),
                    tenant_dict['custom_domain'],
                    1 if tenant_dict['custom_domain_verified'] else 0,
                    tenant_dict['admin_user_id'],
                    tenant_dict['admin_email'],
                    tenant_dict['stripe_customer_id'],
                    tenant_dict['subscription_expires_at'],
                    tenant_dict['created_at'],
                    tenant_dict['updated_at'],
                    json.dumps(tenant_dict['metadata']),
                    tenant_dict['total_returns'],
                    tenant_dict['total_cpas'],
                    tenant_dict['total_clients'],
                    tenant_dict['storage_used_gb'],
                ))

                conn.commit()
                return True

        except sqlite3.IntegrityError:
            return False

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_tenant(row, cursor.description)

    def get_tenant_by_domain(self, domain: str) -> Optional[Tenant]:
        """Get tenant by custom domain"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Try direct domain lookup first
            cursor.execute("""
                SELECT * FROM tenants
                WHERE custom_domain = ? AND custom_domain_verified = 1
            """, (domain,))
            row = cursor.fetchone()

            if row:
                return self._row_to_tenant(row, cursor.description)

            # Try domain mappings table
            cursor.execute("""
                SELECT t.* FROM tenants t
                JOIN domain_mappings dm ON t.tenant_id = dm.tenant_id
                WHERE dm.domain = ? AND dm.verified = 1
            """, (domain,))
            row = cursor.fetchone()

            if row:
                return self._row_to_tenant(row, cursor.description)

            return None

    def update_tenant(self, tenant: Tenant) -> bool:
        """Update tenant information"""
        try:
            tenant.updated_at = datetime.now()
            tenant_dict = tenant.to_dict()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tenants SET
                        tenant_name = ?,
                        status = ?,
                        subscription_tier = ?,
                        branding = ?,
                        features = ?,
                        custom_domain = ?,
                        custom_domain_verified = ?,
                        admin_user_id = ?,
                        admin_email = ?,
                        stripe_customer_id = ?,
                        subscription_expires_at = ?,
                        updated_at = ?,
                        metadata = ?,
                        total_returns = ?,
                        total_cpas = ?,
                        total_clients = ?,
                        storage_used_gb = ?
                    WHERE tenant_id = ?
                """, (
                    tenant_dict['tenant_name'],
                    tenant_dict['status'],
                    tenant_dict['subscription_tier'],
                    json.dumps(tenant_dict['branding']),
                    json.dumps(tenant_dict['features']),
                    tenant_dict['custom_domain'],
                    1 if tenant_dict['custom_domain_verified'] else 0,
                    tenant_dict['admin_user_id'],
                    tenant_dict['admin_email'],
                    tenant_dict['stripe_customer_id'],
                    tenant_dict['subscription_expires_at'],
                    tenant_dict['updated_at'],
                    json.dumps(tenant_dict['metadata']),
                    tenant_dict['total_returns'],
                    tenant_dict['total_cpas'],
                    tenant_dict['total_clients'],
                    tenant_dict['storage_used_gb'],
                    tenant_dict['tenant_id'],
                ))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating tenant: {e}")
            return False

    def update_tenant_branding(self, tenant_id: str, branding: TenantBranding) -> bool:
        """Update only branding for a tenant"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tenants SET
                        branding = ?,
                        updated_at = ?
                    WHERE tenant_id = ?
                """, (
                    json.dumps(branding.to_dict()),
                    datetime.now().isoformat(),
                    tenant_id,
                ))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating tenant branding: {e}")
            return False

    def update_tenant_features(self, tenant_id: str, features: TenantFeatureFlags) -> bool:
        """Update only features for a tenant"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tenants SET
                        features = ?,
                        updated_at = ?
                    WHERE tenant_id = ?
                """, (
                    json.dumps(features.to_dict()),
                    datetime.now().isoformat(),
                    tenant_id,
                ))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating tenant features: {e}")
            return False

    def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        tier: Optional[SubscriptionTier] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Tenant]:
        """List tenants with optional filtering"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM tenants WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if tier:
                query += " AND subscription_tier = ?"
                params.append(tier.value)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_tenant(row, cursor.description) for row in rows]

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant (soft delete recommended in production)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error deleting tenant: {e}")
            return False

    # =============================================================================
    # CPA BRANDING OPERATIONS
    # =============================================================================

    def save_cpa_branding(self, cpa_branding: CPABranding) -> bool:
        """Save or update CPA branding"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                branding_dict = cpa_branding.to_dict()

                cursor.execute("""
                    INSERT OR REPLACE INTO cpa_branding (
                        cpa_id, tenant_id, display_name, tagline,
                        accent_color, profile_photo_url, signature_image_url,
                        direct_email, direct_phone, office_address,
                        bio, credentials, years_experience, specializations,
                        welcome_message, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    branding_dict['cpa_id'],
                    branding_dict['tenant_id'],
                    branding_dict['display_name'],
                    branding_dict['tagline'],
                    branding_dict['accent_color'],
                    branding_dict['profile_photo_url'],
                    branding_dict['signature_image_url'],
                    branding_dict['direct_email'],
                    branding_dict['direct_phone'],
                    branding_dict['office_address'],
                    branding_dict['bio'],
                    json.dumps(branding_dict['credentials']),
                    branding_dict['years_experience'],
                    json.dumps(branding_dict['specializations']),
                    branding_dict['welcome_message'],
                    branding_dict['created_at'],
                    branding_dict['updated_at'],
                ))

                conn.commit()
                return True

        except Exception as e:
            print(f"Error saving CPA branding: {e}")
            return False

    def get_cpa_branding(self, cpa_id: str) -> Optional[CPABranding]:
        """Get CPA branding by CPA ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cpa_branding WHERE cpa_id = ?", (cpa_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_cpa_branding(row, cursor.description)

    def get_tenant_cpas_branding(self, tenant_id: str) -> List[CPABranding]:
        """Get all CPA brandings for a tenant"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cpa_branding WHERE tenant_id = ?", (tenant_id,))
            rows = cursor.fetchall()

            return [self._row_to_cpa_branding(row, cursor.description) for row in rows]

    def delete_cpa_branding(self, cpa_id: str) -> bool:
        """Delete CPA branding"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cpa_branding WHERE cpa_id = ?", (cpa_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error deleting CPA branding: {e}")
            return False

    # =============================================================================
    # DOMAIN OPERATIONS
    # =============================================================================

    def add_custom_domain(self, tenant_id: str, domain: str, verification_token: str) -> bool:
        """Add a custom domain for a tenant"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO domain_mappings (domain, tenant_id, verified, verification_token, created_at)
                    VALUES (?, ?, 0, ?, ?)
                """, (domain, tenant_id, verification_token, datetime.now().isoformat()))

                conn.commit()
                return True

        except sqlite3.IntegrityError:
            return False

    def verify_custom_domain(self, domain: str) -> bool:
        """Mark a custom domain as verified"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE domain_mappings SET verified = 1 WHERE domain = ?
                """, (domain,))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error verifying domain: {e}")
            return False

    # =============================================================================
    # HELPER METHODS
    # =============================================================================

    def _row_to_tenant(self, row: tuple, description: list) -> Tenant:
        """Convert database row to Tenant object"""
        columns = [col[0] for col in description]
        data = dict(zip(columns, row))

        # Parse JSON fields
        data['branding'] = json.loads(data['branding'])
        data['features'] = json.loads(data['features'])
        data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}

        # Convert boolean
        data['custom_domain_verified'] = bool(data['custom_domain_verified'])

        return Tenant.from_dict(data)

    def _row_to_cpa_branding(self, row: tuple, description: list) -> CPABranding:
        """Convert database row to CPABranding object"""
        columns = [col[0] for col in description]
        data = dict(zip(columns, row))

        # Parse JSON fields
        data['credentials'] = json.loads(data['credentials']) if data['credentials'] else []
        data['specializations'] = json.loads(data['specializations']) if data['specializations'] else []

        return CPABranding.from_dict(data)

    def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get usage stats for a tenant"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT total_returns, total_cpas, total_clients, storage_used_gb
                FROM tenants WHERE tenant_id = ?
            """, (tenant_id,))

            row = cursor.fetchone()
            if not row:
                return {}

            return {
                'total_returns': row[0],
                'total_cpas': row[1],
                'total_clients': row[2],
                'storage_used_gb': row[3],
            }

    def increment_tenant_stats(
        self,
        tenant_id: str,
        returns: int = 0,
        cpas: int = 0,
        clients: int = 0,
        storage_gb: float = 0.0
    ) -> bool:
        """Increment tenant usage stats"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE tenants SET
                        total_returns = total_returns + ?,
                        total_cpas = total_cpas + ?,
                        total_clients = total_clients + ?,
                        storage_used_gb = storage_used_gb + ?,
                        updated_at = ?
                    WHERE tenant_id = ?
                """, (returns, cpas, clients, storage_gb, datetime.now().isoformat(), tenant_id))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error incrementing tenant stats: {e}")
            return False


# Global instance (singleton pattern)
_tenant_persistence: Optional[TenantPersistence] = None


def get_tenant_persistence(db_path: str = "./data/tax_returns.db") -> TenantPersistence:
    """Get global tenant persistence instance"""
    global _tenant_persistence

    if _tenant_persistence is None:
        _tenant_persistence = TenantPersistence(db_path)

    return _tenant_persistence
