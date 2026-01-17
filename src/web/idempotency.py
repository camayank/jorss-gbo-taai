"""
Idempotency Layer for API Requests.

Provides idempotency key handling to prevent duplicate submissions
and ensure safe request retries.

Prompt 8: Failure Modes - Handle duplicate submissions gracefully.

Usage:
    1. Client sends X-Idempotency-Key header with unique key
    2. Server checks if key has been seen before
    3. If seen, return cached response
    4. If new, process request and cache response
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger(__name__)

# Header name for idempotency key
IDEMPOTENCY_KEY_HEADER = "X-Idempotency-Key"

# Default TTL for idempotency records (24 hours)
DEFAULT_TTL_HOURS = 24

# Database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


@dataclass
class IdempotencyRecord:
    """Record of an idempotent request."""
    idempotency_key: str
    request_hash: str
    response_status: int
    response_body: str
    response_headers: Dict[str, str]
    created_at: str
    expires_at: str


class IdempotencyStore:
    """
    Database-backed store for idempotency records.

    Tracks processed requests by idempotency key to enable
    safe retries and duplicate detection.
    """

    def __init__(self, db_path: Optional[Path] = None, ttl_hours: int = DEFAULT_TTL_HOURS):
        """
        Initialize idempotency store.

        Args:
            db_path: Path to SQLite database.
            ttl_hours: Time-to-live for idempotency records.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.ttl_hours = ttl_hours
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create idempotency table if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    idempotency_key TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    response_status INTEGER NOT NULL,
                    response_body TEXT NOT NULL,
                    response_headers_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_idempotency_expires
                ON idempotency_records(expires_at)
            """)

            conn.commit()

    def get(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        """
        Get a cached response by idempotency key.

        Args:
            idempotency_key: The idempotency key.

        Returns:
            IdempotencyRecord if found and not expired, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT idempotency_key, request_hash, response_status,
                       response_body, response_headers_json, created_at, expires_at
                FROM idempotency_records
                WHERE idempotency_key = ?
            """, (idempotency_key,))

            row = cursor.fetchone()
            if not row:
                return None

            # Check if expired
            expires_at = datetime.fromisoformat(row[6])
            if datetime.utcnow() > expires_at:
                self.delete(idempotency_key)
                return None

            return IdempotencyRecord(
                idempotency_key=row[0],
                request_hash=row[1],
                response_status=row[2],
                response_body=row[3],
                response_headers=json.loads(row[4]) if row[4] else {},
                created_at=row[5],
                expires_at=row[6]
            )

    def set(
        self,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_body: str,
        response_headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Store a response for an idempotency key.

        Args:
            idempotency_key: The idempotency key.
            request_hash: Hash of the request for verification.
            response_status: HTTP status code.
            response_body: Response body.
            response_headers: Response headers to cache.
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.ttl_hours)
        response_headers = response_headers or {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO idempotency_records (
                    idempotency_key, request_hash, response_status,
                    response_body, response_headers_json, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                idempotency_key,
                request_hash,
                response_status,
                response_body,
                json.dumps(response_headers),
                now.isoformat(),
                expires_at.isoformat()
            ))

            conn.commit()

    def delete(self, idempotency_key: str) -> bool:
        """Delete an idempotency record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM idempotency_records WHERE idempotency_key = ?",
                (idempotency_key,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_expired(self) -> int:
        """Remove all expired idempotency records."""
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM idempotency_records WHERE expires_at < ?",
                (now,)
            )
            conn.commit()
            return cursor.rowcount


def compute_request_hash(method: str, path: str, body: bytes) -> str:
    """
    Compute a hash of the request for verification.

    Args:
        method: HTTP method
        path: Request path
        body: Request body

    Returns:
        SHA-256 hash of the request
    """
    content = f"{method}:{path}:{body.hex() if body else ''}".encode()
    return hashlib.sha256(content).hexdigest()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware that handles idempotency for POST/PUT/PATCH requests.

    When a request includes X-Idempotency-Key header:
    1. Check if key exists in store
    2. If exists, return cached response
    3. If new, process request and cache response

    This prevents duplicate submissions from being processed multiple times.
    """

    def __init__(self, app, store: Optional[IdempotencyStore] = None):
        super().__init__(app)
        self.store = store or IdempotencyStore()

    async def dispatch(self, request: Request, call_next) -> Response:
        """Handle idempotent request processing."""
        # Only apply to mutating methods
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        # Check for idempotency key
        idempotency_key = request.headers.get(IDEMPOTENCY_KEY_HEADER)
        if not idempotency_key:
            return await call_next(request)

        # Validate idempotency key format (UUID or similar)
        if len(idempotency_key) > 128:
            return JSONResponse(
                status_code=400,
                content={"error": "Idempotency key too long (max 128 characters)"}
            )

        # Read request body for hashing
        body = await request.body()
        request_hash = compute_request_hash(
            request.method,
            str(request.url.path),
            body
        )

        # Check for existing response
        existing = self.store.get(idempotency_key)
        if existing:
            # Verify request hash matches (same request)
            if existing.request_hash != request_hash:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": "Idempotency key reused with different request",
                        "detail": "The idempotency key was previously used for a different request"
                    }
                )

            # Return cached response
            logger.debug(f"Returning cached response for idempotency key: {idempotency_key}")
            response = Response(
                content=existing.response_body,
                status_code=existing.response_status,
                headers=existing.response_headers,
                media_type="application/json"
            )
            response.headers["X-Idempotency-Replayed"] = "true"
            return response

        # Process the request
        response = await call_next(request)

        # Cache successful responses (2xx status codes)
        if 200 <= response.status_code < 300:
            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Store the response
            self.store.set(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_status=response.status_code,
                response_body=response_body.decode("utf-8"),
                response_headers={
                    k: v for k, v in response.headers.items()
                    if k.lower() not in ("content-length", "transfer-encoding")
                }
            )

            # Return new response with body
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        return response


def require_idempotency_key(request: Request) -> str:
    """
    Get idempotency key from request, raising error if missing.

    Use in endpoints that REQUIRE idempotency (e.g., payments, submissions).

    Args:
        request: The request object

    Returns:
        The idempotency key

    Raises:
        ValueError: If idempotency key is missing
    """
    key = request.headers.get(IDEMPOTENCY_KEY_HEADER)
    if not key:
        raise ValueError(f"Missing required header: {IDEMPOTENCY_KEY_HEADER}")
    return key


def generate_idempotency_key() -> str:
    """Generate a new idempotency key."""
    import uuid
    return str(uuid.uuid4())


# Global store instance
_idempotency_store: Optional[IdempotencyStore] = None


def get_idempotency_store() -> IdempotencyStore:
    """Get the global idempotency store instance."""
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = IdempotencyStore()
    return _idempotency_store
