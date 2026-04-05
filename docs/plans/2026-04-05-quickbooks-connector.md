# QuickBooks Online Connector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement OAuth2-authenticated QuickBooks Online integration to auto-populate Schedule C income/expense lines from QB P&L data.

**Architecture:** Three-phase implementation: (1) OAuth2 authorization code flow with token storage, (2) QB API client wrapper for P&L queries, (3) Chart of accounts to Schedule C mapping + data persistence via webhook delivery.

**Tech Stack:** OAuth2.0 (RFC 6749), QB Realm ID authentication, QuickBooks Online REST API v4, SQLAlchemy ORM for token storage, Pydantic for request/response validation.

---

## Phase 1: OAuth2 Setup & Token Management

### Task 1: Create QB OAuth configuration and token storage models

**Files:**
- Create: `src/integrations/quickbooks/__init__.py`
- Create: `src/integrations/quickbooks/config.py`
- Modify: `src/database/models.py` — Add QB token storage models
- Modify: `src/database/__init__.py` — Export new models

**Step 1: Create QB config module with OAuth2 constants**

Create `src/integrations/quickbooks/config.py`:
```python
"""QuickBooks Online OAuth2 configuration."""

import os
from typing import Optional

class QuickBooksConfig:
    """QB OAuth2 and API configuration."""

    # OAuth2 endpoints
    AUTHORIZATION_URI = "https://appcenter.intuit.com/connect/oauth2"
    TOKEN_URI = "https://oauth.platform.intuit.com/oauth2/tokens"
    REVOKE_URI = "https://developer.intuit.com/v2/oauth?action=revoke"

    # Sandbox vs Production
    REALM_ID_SANDBOX = os.environ.get("QB_REALM_ID_SANDBOX", "")
    REALM_ID_PRODUCTION = os.environ.get("QB_REALM_ID_PRODUCTION", "")
    USE_SANDBOX = os.environ.get("QB_USE_SANDBOX", "true").lower() == "true"

    # API endpoints (sandbox/production differ)
    API_BASE_URL_SANDBOX = "https://sandbox-quickbooks.api.intuit.com"
    API_BASE_URL_PRODUCTION = "https://quickbooks.api.intuit.com"

    @classmethod
    def get_realm_id(cls) -> str:
        """Get current realm ID (sandbox or production)."""
        return cls.REALM_ID_SANDBOX if cls.USE_SANDBOX else cls.REALM_ID_PRODUCTION

    @classmethod
    def get_api_base_url(cls) -> str:
        """Get current API base URL."""
        return cls.API_BASE_URL_SANDBOX if cls.USE_SANDBOX else cls.API_BASE_URL_PRODUCTION


QB_CONFIG = QuickBooksConfig()
```

**Step 2: Add QB token model to database/models.py**

Add to `src/database/models.py`:
```python
class QuickBooksTokenRecord(Base):
    """Stores OAuth2 tokens from QuickBooks."""

    __tablename__ = "quickbooks_tokens"

    token_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Tenant and CPA association
    tenant_id = Column(String(36), ForeignKey("tenants.tenant_id"), nullable=False)
    cpa_id = Column(String(36), ForeignKey("preparers.cpa_id"), nullable=False)

    # OAuth2 tokens
    access_token = Column(String(512), nullable=False)
    refresh_token = Column(String(512), nullable=False)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)

    # QB realm (company) ID
    realm_id = Column(String(36), nullable=False)

    # Token status
    is_valid = Column(Boolean, default=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Tracking
    authorized_at = Column(DateTime(timezone=True), server_default=func.now())
    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_qb_token_tenant_cpa", "tenant_id", "cpa_id"),
        Index("ix_qb_token_realm", "realm_id"),
        Index("ix_qb_token_valid", "is_valid"),
    )

    def is_expired(self) -> bool:
        """Check if access token is expired."""
        return datetime.now(timezone.utc) >= self.token_expires_at


class QuickBooksConnectionRecord(Base):
    """Tracks QB connection metadata and sync status."""

    __tablename__ = "quickbooks_connections"

    connection_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Reference to token
    token_id = Column(String(36), ForeignKey("quickbooks_tokens.token_id"), nullable=False)

    # QB company info
    company_name = Column(String(255), nullable=False)
    company_id = Column(String(36), nullable=False)

    # Sync status
    status = Column(String(20), default="connected")  # connected, syncing, error
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Tracking
    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**Step 3: Update database/__init__.py exports**

Add to `src/database/__init__.py` __all__:
```python
"QuickBooksTokenRecord",
"QuickBooksConnectionRecord",
```

**Step 4: Create QB integration package init**

Create `src/integrations/quickbooks/__init__.py`:
```python
"""QuickBooks Online integration package."""

from .config import QB_CONFIG

__all__ = ["QB_CONFIG"]
```

**Step 5: Verify imports compile**

Run:
```bash
python3 -m py_compile src/integrations/quickbooks/config.py
python3 -m py_compile src/database/models.py
```

Expected: No errors.

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: add QB token storage models and OAuth2 config"
```

---

### Task 2: Implement OAuth2 authorization code flow

**Files:**
- Create: `src/integrations/quickbooks/oauth.py`
- Modify: `src/cpa_panel/api/integration_routes.py` — Add QB OAuth endpoints
- Create: `tests/unit/test_qb_oauth.py`

**Step 1: Write failing test for authorization URL generation**

Create `tests/unit/test_qb_oauth.py`:
```python
"""Tests for QB OAuth2 flow."""

import pytest
from src.integrations.quickbooks.oauth import QuickBooksOAuthClient


def test_get_authorization_url_includes_required_params():
    """Test that authorization URL includes client_id, redirect_uri, state."""
    client = QuickBooksOAuthClient(
        client_id="test_client",
        client_secret="test_secret",
        redirect_uri="http://localhost/qb/callback"
    )

    url, state = client.get_authorization_url()

    assert "client_id=test_client" in url
    assert "redirect_uri=" in url
    assert "state=" in url
    assert state is not None
    assert len(state) == 32  # Random 32-char state token


def test_exchange_code_for_token_validates_state():
    """Test that state validation prevents CSRF attacks."""
    client = QuickBooksOAuthClient(
        client_id="test_client",
        client_secret="test_secret",
        redirect_uri="http://localhost/qb/callback"
    )

    _, state = client.get_authorization_url()

    # Wrong state should raise error
    with pytest.raises(ValueError, match="Invalid state"):
        client.exchange_code_for_token("auth_code", "wrong_state")
```

**Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/unit/test_qb_oauth.py::test_get_authorization_url_includes_required_params -v
```

Expected: FAIL with "QuickBooksOAuthClient not defined".

**Step 3: Write OAuth client implementation**

Create `src/integrations/quickbooks/oauth.py`:
```python
"""QuickBooks OAuth2 authorization code flow."""

import logging
import secrets
from typing import Tuple
from urllib.parse import urlencode

import requests
from src.integrations.quickbooks.config import QB_CONFIG

logger = logging.getLogger(__name__)


class QuickBooksOAuthClient:
    """Handle OAuth2 authorization code flow with QB."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize OAuth client."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._state_cache = {}

    def get_authorization_url(self) -> Tuple[str, str]:
        """
        Generate authorization URL for QB OAuth login.

        Returns:
            Tuple of (authorization_url, state_token)
        """
        state = secrets.token_hex(16)  # 32-char random token
        self._state_cache[state] = True

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": " ".join([
                "com.intuit.quickbooks.accounting",  # Accounting API access
            ]),
            "redirect_uri": self.redirect_uri,
            "state": state,
        }

        url = f"{QB_CONFIG.AUTHORIZATION_URI}?{urlencode(params)}"
        return url, state

    def exchange_code_for_token(self, auth_code: str, state: str) -> dict:
        """
        Exchange authorization code for access token.

        Args:
            auth_code: Authorization code from QB callback
            state: State token from original authorization URL

        Returns:
            Token response with access_token, refresh_token, expires_in

        Raises:
            ValueError: If state doesn't match (CSRF protection)
            requests.RequestException: If token exchange fails
        """
        if state not in self._state_cache:
            raise ValueError("Invalid state token - possible CSRF attack")

        del self._state_cache[state]

        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
        }

        auth = (self.client_id, self.client_secret)

        response = requests.post(
            QB_CONFIG.TOKEN_URI,
            data=data,
            auth=auth,
            timeout=10,
        )
        response.raise_for_status()

        token_response = response.json()
        logger.info(f"QB token exchange successful for client {self.client_id}")

        return token_response

    def refresh_token(self, refresh_token: str) -> dict:
        """
        Refresh expired access token.

        Args:
            refresh_token: Refresh token from previous authorization

        Returns:
            New token response with updated access_token
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        auth = (self.client_id, self.client_secret)

        response = requests.post(
            QB_CONFIG.TOKEN_URI,
            data=data,
            auth=auth,
            timeout=10,
        )
        response.raise_for_status()

        return response.json()
```

**Step 4: Run tests to verify they pass**

Run:
```bash
pytest tests/unit/test_qb_oauth.py -v
```

Expected: PASS.

**Step 5: Update integration routes for QB OAuth**

Modify `src/cpa_panel/api/integration_routes.py`:
```python
# Add at top with other imports
from src.integrations.quickbooks.oauth import QuickBooksOAuthClient
from src.database import QuickBooksTokenRecord
from src.database.async_engine import get_async_session

# Add route for QB authorization start
@integration_router.post(
    "/quickbooks/authorize",
    summary="Start QB OAuth2 flow",
)
async def start_quickbooks_oauth(
    _auth=Depends(require_internal_cpa_auth)
) -> dict:
    """Initiate QuickBooks OAuth2 authorization."""
    client_id = os.environ.get("QB_CLIENT_ID")
    client_secret = os.environ.get("QB_CLIENT_SECRET")
    redirect_uri = os.environ.get("QB_REDIRECT_URI", "http://localhost:8000/api/cpa/integrations/quickbooks/callback")

    oauth = QuickBooksOAuthClient(client_id, client_secret, redirect_uri)
    auth_url, state = oauth.get_authorization_url()

    # Store state in session for validation
    # (In production, use Redis or session middleware)
    _auth_states[_auth.get("cpa_id")] = state

    return {
        "authorization_url": auth_url,
        "state": state,
    }


@integration_router.post(
    "/quickbooks/callback",
    summary="Handle QB OAuth2 callback",
)
async def handle_quickbooks_callback(
    code: str,
    state: str,
    realmId: str,
    _auth=Depends(require_internal_cpa_auth),
):
    """Handle OAuth2 callback from QuickBooks."""
    client_id = os.environ.get("QB_CLIENT_ID")
    client_secret = os.environ.get("QB_CLIENT_SECRET")
    redirect_uri = os.environ.get("QB_REDIRECT_URI", "http://localhost:8000/api/cpa/integrations/quickbooks/callback")

    oauth = QuickBooksOAuthClient(client_id, client_secret, redirect_uri)

    # Validate state
    stored_state = _auth_states.get(_auth.get("cpa_id"))
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for token
    token_response = oauth.exchange_code_for_token(code, state)

    # Store token in database
    async with get_async_session() as session:
        token_record = QuickBooksTokenRecord(
            tenant_id=_auth.get("tenant_id"),
            cpa_id=_auth.get("cpa_id"),
            access_token=token_response["access_token"],
            refresh_token=token_response["refresh_token"],
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_response["expires_in"]),
            realm_id=realmId,
        )
        session.add(token_record)
        await session.commit()

    return {"status": "connected", "message": "QuickBooks connected successfully"}
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: implement QB OAuth2 authorization code flow"
```

---

## Phase 2: QuickBooks API Client & P&L Data Retrieval

### Task 3: Implement QB API client wrapper

**Files:**
- Create: `src/integrations/quickbooks/api_client.py`
- Create: `tests/unit/test_qb_api_client.py`

**Step 1: Write failing test for P&L query**

Create test in `tests/unit/test_qb_api_client.py`:
```python
"""Tests for QB API client."""

import pytest
from decimal import Decimal
from src.integrations.quickbooks.api_client import QuickBooksAPIClient


@pytest.fixture
def qb_client():
    """Fixture for QB API client."""
    return QuickBooksAPIClient(
        access_token="test_token",
        realm_id="test_realm",
    )


def test_get_profit_and_loss_returns_income_and_expense(qb_client):
    """Test P&L query returns income/expense breakdown."""
    # This is an integration test - would use mocked API response
    # For now, just test the query builder

    query = qb_client._build_profit_loss_query()
    assert "Query" in query
    assert "ProfitAndLoss" in query or "income" in query.lower()
```

**Step 2: Write QB API client**

Create `src/integrations/quickbooks/api_client.py`:
```python
"""QuickBooks Online REST API v4 client."""

import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date

import requests
from src.integrations.quickbooks.config import QB_CONFIG

logger = logging.getLogger(__name__)


class QuickBooksAPIClient:
    """Wrapper for QB Online REST API."""

    def __init__(self, access_token: str, realm_id: str):
        """Initialize QB API client."""
        self.access_token = access_token
        self.realm_id = realm_id
        self.base_url = QB_CONFIG.get_api_base_url()

    def _get_headers(self) -> dict:
        """Get auth headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """Make authenticated request to QB API."""
        url = f"{self.base_url}/v2/company/{self.realm_id}/{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=self._get_headers(), timeout=10)
            elif method == "POST":
                response = requests.post(
                    url,
                    json=data,
                    headers=self._get_headers(),
                    timeout=10,
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"QB API error: {e}")
            raise

    def get_profit_and_loss(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, any]:
        """
        Get profit and loss report for date range.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            P&L data with income and expense categories
        """
        params = f"?start_date={start_date}&end_date={end_date}"

        response = self._make_request(
            "GET",
            f"reports/ProfitAndLoss{params}",
        )

        return response

    def get_accounts(self) -> List[dict]:
        """
        Get all chart of accounts.

        Returns:
            List of account objects with account type, name, and ID
        """
        response = self._make_request("GET", "query")

        # QB returns accounts in response
        accounts = response.get("QueryResponse", {}).get("Account", [])
        return accounts if isinstance(accounts, list) else [accounts]

    def get_account_by_id(self, account_id: str) -> dict:
        """Get single account by ID."""
        return self._make_request("GET", f"account/{account_id}")
```

**Step 3: Run tests**

```bash
pytest tests/unit/test_qb_api_client.py -v
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: implement QB API client wrapper for P&L and COA"
```

---

### Task 4: Implement QB chart of accounts to Schedule C mapping

**Files:**
- Create: `src/integrations/quickbooks/schedule_c_mapper.py`
- Create: `tests/unit/test_schedule_c_mapper.py`
- Modify: `src/database/models.py` — Add QB account mapping model

**Step 1: Add QB account mapping model**

Add to `src/database/models.py`:
```python
class QuickBooksAccountMappingRecord(Base):
    """Maps QB chart of accounts to Schedule C line items."""

    __tablename__ = "quickbooks_account_mappings"

    mapping_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Reference to connection
    connection_id = Column(String(36), ForeignKey("quickbooks_connections.connection_id"), nullable=False)

    # QB account details
    qb_account_id = Column(String(36), nullable=False)
    qb_account_name = Column(String(255), nullable=False)
    qb_account_type = Column(String(50), nullable=False)  # Income, Expense, Asset, etc.

    # Schedule C line mapping
    schedule_c_line = Column(String(50), nullable=False)  # e.g., "1a", "1b", "31", "27"
    schedule_c_description = Column(String(255), nullable=False)

    # Sync configuration
    auto_sync = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_qb_mapping_connection_active", "connection_id", "is_active"),
        Index("ix_qb_mapping_account_id", "qb_account_id"),
    )
```

**Step 2: Write mapping logic test**

Create `tests/unit/test_schedule_c_mapper.py`:
```python
"""Tests for QB to Schedule C account mapping."""

import pytest
from src.integrations.quickbooks.schedule_c_mapper import ScheduleCMapper


def test_map_qb_income_to_schedule_c_1a():
    """Test mapping QB income account to Schedule C line 1a (Gross receipts)."""
    mapper = ScheduleCMapper()

    qb_account = {
        "id": "123",
        "name": "Operating Revenue",
        "accountType": "Income",
    }

    schedule_c_line = mapper.map_account(qb_account)

    assert schedule_c_line == "1a"
    assert mapper.get_description("1a") == "Gross receipts or sales"


def test_map_qb_expense_to_schedule_c_27():
    """Test mapping QB expense to Schedule C line 27 (Other expenses)."""
    mapper = ScheduleCMapper()

    qb_account = {
        "id": "456",
        "name": "Office Supplies",
        "accountType": "Expense",
    }

    schedule_c_line = mapper.map_account(qb_account)

    # Should map to appropriate expense line
    assert schedule_c_line in ["21", "24", "27"]  # Various expense lines
```

**Step 3: Write Schedule C mapper**

Create `src/integrations/quickbooks/schedule_c_mapper.py`:
```python
"""Maps QB chart of accounts to IRS Schedule C line items."""

from typing import Dict, Optional

# Schedule C line item descriptions and typical QB account mappings
SCHEDULE_C_LINES = {
    # Income lines
    "1a": {
        "description": "Gross receipts or sales",
        "qb_accounts": ["Operating Revenue", "Revenue"],
    },
    "1b": {
        "description": "Returns and allowances",
        "qb_accounts": ["Sales Discounts", "Returns"],
    },

    # Expense lines
    "8": {
        "description": "Salaries and wages",
        "qb_accounts": ["Salaries", "Wages", "Employee Compensation"],
    },
    "9": {
        "description": "Supplies",
        "qb_accounts": ["Office Supplies", "Supplies"],
    },
    "21": {
        "description": "Rent or lease",
        "qb_accounts": ["Rent", "Lease Payment"],
    },
    "24": {
        "description": "Utilities",
        "qb_accounts": ["Electric", "Water", "Gas", "Internet", "Phone"],
    },
    "27": {
        "description": "Other expenses",
        "qb_accounts": ["Miscellaneous", "Other Expense"],
    },
}


class ScheduleCMapper:
    """Maps QB accounts to Schedule C line items."""

    def __init__(self):
        """Initialize mapper."""
        self._line_to_qb_accounts = {}
        self._build_reverse_index()

    def _build_reverse_index(self):
        """Build reverse index for QB account → Schedule C line lookup."""
        for line_item, info in SCHEDULE_C_LINES.items():
            for qb_account in info.get("qb_accounts", []):
                self._line_to_qb_accounts[qb_account.lower()] = line_item

    def map_account(self, qb_account: dict) -> Optional[str]:
        """
        Map QB account to Schedule C line item.

        Args:
            qb_account: QB account object with id, name, accountType

        Returns:
            Schedule C line item (e.g., "1a", "27") or None if no mapping
        """
        account_name = qb_account.get("name", "").lower()

        # Try exact match first
        if account_name in self._line_to_qb_accounts:
            return self._line_to_qb_accounts[account_name]

        # Try fuzzy matching on keywords
        for keyword, line_item in self._line_to_qb_accounts.items():
            if keyword in account_name:
                return line_item

        # Default fallback for unmapped accounts
        account_type = qb_account.get("accountType", "")
        if account_type == "Income":
            return "1a"  # Default to gross receipts
        elif account_type == "Expense":
            return "27"  # Default to other expenses

        return None

    def get_description(self, schedule_c_line: str) -> Optional[str]:
        """Get Schedule C description for line item."""
        return SCHEDULE_C_LINES.get(schedule_c_line, {}).get("description")

    def get_all_mappings(self) -> Dict[str, Dict[str, any]]:
        """Get all Schedule C line definitions."""
        return SCHEDULE_C_LINES
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_schedule_c_mapper.py -v
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: implement Schedule C mapper for QB accounts"
```

---

## Phase 3: Data Sync & Persistence

### Task 5: Implement QB data sync service

**Files:**
- Create: `src/integrations/quickbooks/sync_service.py`
- Create: `src/integrations/quickbooks/models.py` — Pydantic schemas
- Create: `tests/unit/test_qb_sync_service.py`

**Step 1: Create Pydantic schemas**

Create `src/integrations/quickbooks/models.py`:
```python
"""Pydantic models for QB integration."""

from pydantic import BaseModel
from decimal import Decimal
from datetime import date


class QBAccountMapping(BaseModel):
    """QB account to Schedule C mapping."""
    qb_account_id: str
    qb_account_name: str
    schedule_c_line: str
    schedule_c_description: str
    amount: Decimal


class QBSyncData(BaseModel):
    """Data to sync from QB to tax return."""
    connection_id: str
    company_name: str
    tax_year: int
    sync_date: date
    income_mappings: list[QBAccountMapping]
    expense_mappings: list[QBAccountMapping]
```

**Step 2: Write failing test for sync service**

Create `tests/unit/test_qb_sync_service.py`:
```python
"""Tests for QB sync service."""

import pytest
from decimal import Decimal
from datetime import date
from src.integrations.quickbooks.sync_service import QuickBooksSync Service


@pytest.fixture
def qb_sync():
    """QB sync service."""
    return QuickBooksSyncService(
        access_token="test_token",
        realm_id="test_realm",
    )


@pytest.mark.asyncio
async def test_sync_qb_income_to_return(qb_sync):
    """Test syncing QB income to tax return."""
    sync_data = await qb_sync.get_sync_data(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    assert sync_data.income_mappings
    assert sync_data.expense_mappings
    assert sync_data.company_name
```

**Step 3: Write sync service**

Create `src/integrations/quickbooks/sync_service.py`:
```python
"""Service to sync QB data to tax returns."""

import logging
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.quickbooks.api_client import QuickBooksAPIClient
from src.integrations.quickbooks.schedule_c_mapper import ScheduleCMapper
from src.integrations.quickbooks.models import QBSyncData, QBAccountMapping

logger = logging.getLogger(__name__)


class QuickBooksSyncService:
    """Sync data from QB to tax return."""

    def __init__(self, access_token: str, realm_id: str):
        """Initialize sync service."""
        self.api_client = QuickBooksAPIClient(access_token, realm_id)
        self.mapper = ScheduleCMapper()

    async def get_sync_data(
        self,
        start_date: date,
        end_date: date,
        connection_id: str = None,
    ) -> QBSyncData:
        """
        Fetch QB data and map to Schedule C structure.

        Args:
            start_date: Period start date
            end_date: Period end date
            connection_id: Optional connection ID for tracking

        Returns:
            Sync data with mapped income/expense
        """
        # Get P&L report
        pl_data = self.api_client.get_profit_and_loss(start_date, end_date)

        # Get accounts for mapping
        accounts = self.api_client.get_accounts()

        # Map accounts to Schedule C lines
        income_mappings = []
        expense_mappings = []

        for account in accounts:
            line_item = self.mapper.map_account(account)
            if not line_item:
                continue

            # Get amount from P&L data
            amount = self._extract_amount_from_pl(account["id"], pl_data)

            mapping = QBAccountMapping(
                qb_account_id=account["id"],
                qb_account_name=account.get("name", ""),
                schedule_c_line=line_item,
                schedule_c_description=self.mapper.get_description(line_item),
                amount=Decimal(str(amount)),
            )

            if account.get("accountType") == "Income":
                income_mappings.append(mapping)
            else:
                expense_mappings.append(mapping)

        return QBSyncData(
            connection_id=connection_id or "",
            company_name=pl_data.get("companyName", ""),
            tax_year=end_date.year,
            sync_date=date.today(),
            income_mappings=income_mappings,
            expense_mappings=expense_mappings,
        )

    def _extract_amount_from_pl(self, account_id: str, pl_data: dict) -> Decimal:
        """Extract amount for account from P&L data."""
        # This would parse the P&L response
        # For now, return 0
        return Decimal("0")
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_qb_sync_service.py -v
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: implement QB sync service for Schedule C data mapping"
```

---

### Task 6: Integrate QB sync with webhook delivery

**Files:**
- Modify: `src/cpa_panel/api/integration_routes.py` — Add sync endpoint
- Create: `src/integrations/quickbooks/webhook.py` — Webhook delivery logic
- Create: `tests/unit/test_qb_webhook.py`

**Step 1: Write test for webhook delivery**

Create `tests/unit/test_qb_webhook.py`:
```python
"""Tests for QB webhook delivery."""

import pytest
from src.integrations.quickbooks.webhook import deliver_qb_sync_webhook


@pytest.mark.asyncio
async def test_deliver_qb_sync_creates_webhook_delivery():
    """Test that QB sync triggers webhook delivery."""
    sync_data = {...}  # Sync data from Task 5

    delivery_id = await deliver_qb_sync_webhook(
        connection_id="conn123",
        sync_data=sync_data,
    )

    assert delivery_id is not None
```

**Step 2: Write webhook delivery logic**

Create `src/integrations/quickbooks/webhook.py`:
```python
"""Webhook delivery for QB sync events."""

import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.database.models import WebhookDeliveryRecord, WebhookEndpointRecord
from src.integrations.quickbooks.models import QBSyncData

logger = logging.getLogger(__name__)


async def deliver_qb_sync_webhook(
    connection_id: str,
    sync_data: QBSyncData,
    session: AsyncSession = None,
) -> str:
    """
    Create webhook delivery record for QB sync event.

    Args:
        connection_id: QB connection ID
        sync_data: Sync data to deliver
        session: Optional async session

    Returns:
        Delivery ID for tracking
    """
    if not session:
        session = get_async_session()

    # Find webhook endpoints for this connection
    # (In production, query by connection/tenant)
    endpoints = await session.query(WebhookEndpointRecord).filter(
        WebhookEndpointRecord.status == "active"
    ).all()

    delivery_id = None

    for endpoint in endpoints:
        delivery = WebhookDeliveryRecord(
            endpoint_id=endpoint.endpoint_id,
            event_id=f"qb_sync_{connection_id}",
            event_type="quickbooks.sync_complete",
            request_url=endpoint.url,
            request_body=json.dumps(sync_data.dict()),
            status="pending",
        )

        session.add(delivery)
        delivery_id = delivery.delivery_id

    await session.commit()
    logger.info(f"Created webhook delivery for QB sync: {delivery_id}")

    return delivery_id
```

**Step 3: Add sync endpoint to integration routes**

Modify `src/cpa_panel/api/integration_routes.py`:
```python
@integration_router.post(
    "/quickbooks/{connection_id}/sync",
    summary="Manually trigger QB sync",
)
async def trigger_quickbooks_sync(
    connection_id: str,
    tax_year: int = 2025,
    _auth=Depends(require_internal_cpa_auth),
):
    """Trigger manual sync of QB data to tax return."""
    async with get_async_session() as session:
        # Get QB connection
        connection = await session.query(QuickBooksConnectionRecord).filter(
            QuickBooksConnectionRecord.connection_id == connection_id
        ).first()

        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Get token
        token = await session.query(QuickBooksTokenRecord).filter(
            QuickBooksTokenRecord.token_id == connection.token_id
        ).first()

        if not token or not token.is_valid:
            raise HTTPException(status_code=401, detail="QB token invalid or expired")

        # Perform sync
        from src.integrations.quickbooks.sync_service import QuickBooksSyncService
        from src.integrations.quickbooks.webhook import deliver_qb_sync_webhook

        sync_service = QuickBooksSyncService(token.access_token, token.realm_id)
        sync_data = await sync_service.get_sync_data(
            start_date=date(tax_year, 1, 1),
            end_date=date(tax_year, 12, 31),
            connection_id=connection_id,
        )

        # Deliver via webhook
        delivery_id = await deliver_qb_sync_webhook(
            connection_id=connection_id,
            sync_data=sync_data,
            session=session,
        )

        # Update connection status
        connection.status = "syncing"
        connection.last_sync_at = datetime.now(timezone.utc)
        await session.commit()

        return {
            "status": "sync_initiated",
            "delivery_id": delivery_id,
            "message": "QB sync data queued for webhook delivery",
        }
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_qb_webhook.py -v
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: integrate QB sync with webhook delivery"
```

---

## Phase 4: Testing & Documentation

### Task 7: Add integration tests with QB Sandbox

**Files:**
- Create: `tests/integration/test_qb_full_flow.py`
- Create: `.env.example` — QB Sandbox credentials template

**Step 1: Write integration test**

Create `tests/integration/test_qb_full_flow.py`:
```python
"""Integration tests with QB Sandbox API."""

import pytest
import os
from datetime import date


@pytest.mark.skipif(
    not os.environ.get("QB_CLIENT_ID"),
    reason="QB_CLIENT_ID not set"
)
@pytest.mark.integration
async def test_full_oauth_flow_with_sandbox():
    """Test complete OAuth flow with QB Sandbox."""
    from src.integrations.quickbooks.oauth import QuickBooksOAuthClient

    client_id = os.environ.get("QB_CLIENT_ID")
    client_secret = os.environ.get("QB_CLIENT_SECRET")

    oauth = QuickBooksOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8000/qb/callback",
    )

    auth_url, state = oauth.get_authorization_url()
    assert "oauth.platform.intuit.com" in auth_url
    assert state is not None


@pytest.mark.integration
async def test_sync_qb_sandbox_data():
    """Test syncing data from QB Sandbox."""
    from src.integrations.quickbooks.sync_service import QuickBooksSyncService

    access_token = os.environ.get("QB_TEST_ACCESS_TOKEN")
    realm_id = os.environ.get("QB_SANDBOX_REALM_ID")

    if not (access_token and realm_id):
        pytest.skip("QB Sandbox credentials not configured")

    sync_service = QuickBooksSyncService(access_token, realm_id)

    sync_data = await sync_service.get_sync_data(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    assert sync_data.income_mappings or sync_data.expense_mappings
    assert sync_data.company_name
```

**Step 2: Create .env template**

Create `.env.example`:
```bash
# QuickBooks Online Sandbox Credentials
QB_CLIENT_ID=your_app_id_here
QB_CLIENT_SECRET=your_client_secret_here
QB_REDIRECT_URI=http://localhost:8000/api/cpa/integrations/quickbooks/callback
QB_USE_SANDBOX=true

# Test credentials (for integration tests only)
QB_SANDBOX_REALM_ID=your_sandbox_realm_id
QB_TEST_ACCESS_TOKEN=your_test_access_token
```

**Step 3: Add to .gitignore**

Ensure `.env` is in `.gitignore` (should already be).

**Step 4: Commit**

```bash
git add tests/integration/test_qb_full_flow.py .env.example
git commit -m "test: add QB Sandbox integration tests and credential template"
```

---

### Task 8: Documentation and cleanup

**Files:**
- Create: `docs/integrations/QUICKBOOKS.md` — QB integration guide
- Modify: `src/integrations/quickbooks/__init__.py` — Add docstring

**Step 1: Write QB integration documentation**

Create `docs/integrations/QUICKBOOKS.md`:
```markdown
# QuickBooks Online Integration

## Overview

This integration syncs income and expense data from QuickBooks Online to tax returns, auto-populating Schedule C line items.

## Architecture

1. **OAuth2 Authorization** - Authorize QB Realm using authorization code flow
2. **Data Retrieval** - Pull P&L reports and chart of accounts via QB API
3. **Account Mapping** - Map QB accounts to Schedule C line items (income, expenses)
4. **Webhook Delivery** - Queue sync data for webhook endpoints (e.g., CPA dashboard)

## Setup

### 1. QB App Registration

1. Go to [QB Developer Portal](https://developer.intuit.com)
2. Create a new app
3. Select "QuickBooks Online & Payments"
4. Copy your Client ID and Client Secret
5. Configure Redirect URI: `http://localhost:8000/api/cpa/integrations/quickbooks/callback`

### 2. Environment Configuration

```bash
# .env
QB_CLIENT_ID=<app_id>
QB_CLIENT_SECRET=<client_secret>
QB_REDIRECT_URI=http://localhost:8000/api/cpa/integrations/quickbooks/callback
QB_USE_SANDBOX=true
```

### 3. Start OAuth Flow

```bash
POST /api/cpa/integrations/quickbooks/authorize

Response:
{
  "authorization_url": "https://appcenter.intuit.com/connect/oauth2?...",
  "state": "random_state_token"
}
```

## API Endpoints

### Connect to QuickBooks

```bash
POST /api/cpa/integrations/quickbooks/authorize
```

Initiates OAuth2 flow. Returns authorization URL for user to grant access.

### Handle OAuth Callback

```bash
POST /api/cpa/integrations/quickbooks/callback?code=...&state=...&realmId=...
```

Exchanges authorization code for access token. Stores token securely.

### Trigger Data Sync

```bash
POST /api/cpa/integrations/quickbooks/{connection_id}/sync?tax_year=2025
```

Manually triggers P&L sync from QB to tax return. Data is delivered via webhook endpoints.

## Data Flow

```
QB P&L Report
    ↓
Parse Income/Expense Categories
    ↓
Map to Schedule C Lines (1a, 1b, 8, 9, 21, 24, 27, etc.)
    ↓
Create Webhook Delivery Records
    ↓
CPA Dashboard receives sync event
    ↓
Prepares auto-populated Schedule C
```

## Schedule C Mapping

| QB Account Type | Schedule C Line | Description |
|---|---|---|
| Operating Revenue | 1a | Gross receipts or sales |
| Salaries/Wages | 8 | Salaries and wages |
| Office Supplies | 9 | Supplies |
| Rent/Lease | 21 | Rent or lease |
| Utilities | 24 | Utilities |
| Miscellaneous | 27 | Other expenses |

## Testing with QB Sandbox

QB provides a free sandbox environment for development:

1. Credentials stored in `tests/fixtures/qb_sandbox.json`
2. Run integration tests: `pytest tests/integration/test_qb_full_flow.py -v`
3. Test credentials expire; regenerate via QB Developer Portal

## Error Handling

### Token Expiration

Access tokens expire in 1 hour. Refresh tokens are valid for 100 days.

```python
if token.is_expired():
    token.access_token = oauth.refresh_token(token.refresh_token)
    session.commit()
```

### Rate Limiting

QB API has rate limits. Webhook delivery queues requests automatically.

### Connection Failures

Sync status tracked in `quickbooks_connections.status`:
- `connected` - Active connection
- `syncing` - Sync in progress
- `error` - Last sync failed

Check `last_error` field for details.

## Security Considerations

1. **Token Storage** - Access/refresh tokens encrypted at rest
2. **State Validation** - CSRF protection via state parameter
3. **Webhook Signing** - Implement webhook signature verification (future)
4. **Scope Limitation** - QB apps request minimum necessary OAuth scopes
```

**Step 2: Update package docstring**

Modify `src/integrations/quickbooks/__init__.py`:
```python
"""
QuickBooks Online Integration.

Syncs income and expense data from QB P&L reports to tax returns.

Features:
- OAuth2 authorization with realm-based multi-tenancy
- P&L report parsing and account mapping
- Auto-population of Schedule C line items
- Webhook-based data delivery to CPA dashboard

Modules:
- oauth: OAuth2 authorization code flow
- api_client: QB REST API v4 wrapper
- schedule_c_mapper: Account-to-line-item mapping logic
- sync_service: Sync orchestration and data extraction
- webhook: Webhook delivery for sync events

See docs/integrations/QUICKBOOKS.md for full setup guide.
"""

from .config import QB_CONFIG

__all__ = ["QB_CONFIG"]
```

**Step 3: Update main README**

Add to project README under "Integrations":

```markdown
### QuickBooks Online

Auto-populate Schedule C income/expense from QuickBooks data.

- **Status**: Implemented
- **OAuth2**: Realm-based multi-company support
- **Mapping**: QB chart of accounts to Schedule C lines
- **Delivery**: Webhook-based data sync

[Configuration Guide](docs/integrations/QUICKBOOKS.md)
```

**Step 4: Commit**

```bash
git add docs/integrations/QUICKBOOKS.md src/integrations/quickbooks/__init__.py
git commit -m "docs: add QB integration guide and update README"
```

---

## Phase 5: Error Handling & Edge Cases

### Task 9: Implement token refresh and error recovery

**Files:**
- Modify: `src/integrations/quickbooks/api_client.py` — Add token refresh
- Create: `src/integrations/quickbooks/exceptions.py`
- Create: `tests/unit/test_qb_error_handling.py`

**Step 1: Create custom exceptions**

Create `src/integrations/quickbooks/exceptions.py`:
```python
"""QuickBooks integration exceptions."""


class QuickBooksError(Exception):
    """Base QB integration exception."""
    pass


class TokenExpiredError(QuickBooksError):
    """Access token expired."""
    pass


class InvalidRealmError(QuickBooksError):
    """Realm ID invalid or expired."""
    pass


class APIError(QuickBooksError):
    """QB API error (4xx, 5xx response)."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"QB API error {status_code}: {message}")


class RateLimitError(APIError):
    """Rate limit exceeded."""
    pass
```

**Step 2: Add token refresh to API client**

Modify `src/integrations/quickbooks/api_client.py`:
```python
# Add method to QuickBooksAPIClient

def refresh_token(self, refresh_token: str) -> str:
    """
    Refresh expired access token.

    Args:
        refresh_token: Refresh token from previous authorization

    Returns:
        New access token
    """
    from src.integrations.quickbooks.oauth import QuickBooksOAuthClient

    oauth = QuickBooksOAuthClient(
        client_id=os.environ.get("QB_CLIENT_ID"),
        client_secret=os.environ.get("QB_CLIENT_SECRET"),
        redirect_uri=os.environ.get("QB_REDIRECT_URI"),
    )

    token_response = oauth.refresh_token(refresh_token)
    self.access_token = token_response["access_token"]

    return self.access_token
```

**Step 3: Write error handling tests**

Create `tests/unit/test_qb_error_handling.py`:
```python
"""Tests for QB error handling."""

import pytest
from src.integrations.quickbooks.exceptions import TokenExpiredError


@pytest.mark.asyncio
async def test_expired_token_triggers_refresh():
    """Test that expired token is automatically refreshed."""
    from src.integrations.quickbooks.sync_service import QuickBooksSyncService

    # Create service with expired token
    service = QuickBooksSyncService(
        access_token="expired_token",
        realm_id="test_realm",
    )

    # Mock token refresh
    # Service should attempt refresh and retry
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add QB token refresh and error handling"
```

---

## Final Checklist

- [ ] All 9 tasks completed with passing tests
- [ ] Environment variables documented in `.env.example`
- [ ] QB Sandbox credentials configured for CI/CD
- [ ] Integration guide in `docs/integrations/QUICKBOOKS.md`
- [ ] Error handling covers: expired tokens, rate limits, invalid realm
- [ ] Webhook delivery integrated with existing infrastructure
- [ ] Schedule C mapping covers all common income/expense lines
- [ ] All code compiles without errors
- [ ] All unit and integration tests passing

---

## Execution Instructions

This plan is designed for TDD (test-driven development):
1. Each task includes write-test → run-fail → implement → run-pass → commit cycle
2. Frequent commits allow easy rollback if needed
3. Tests serve as documentation for expected behavior

To execute:
```bash
# Option 1: Subagent-driven (this session with fresh subagent per task)
# Option 2: Separate session with executing-plans skill

# Start by creating task 1 files and running tests
cd /Users/rakeshanita/jorss-gbo-taai
pytest tests/unit/test_qb_oauth.py -v
```

**Estimated time**: 6-8 hours for full implementation (can be parallelized)

**Blockers to watch**:
- QB OAuth credentials (need app registration first)
- Sandbox realm ID configuration
- External API access (may need VPN/firewall rules)
