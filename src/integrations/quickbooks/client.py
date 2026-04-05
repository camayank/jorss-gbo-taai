"""
QuickBooks Online API Client.

Stateless async wrapper for QB Online REST API v3/v4.
All methods require caller-supplied realm_id and access_token;
no tokens are stored on this class.

Covered endpoints:
- Reports: ProfitAndLoss (v4)
- Query: Account entities
- Query: JournalEntry entities

Error surface:
- QBAuthError       -> caller maps to HTTP 401
- QBRateLimitError  -> caller maps to HTTP 429
- QBAPIError        -> caller maps to HTTP 502 (generic QB fault)
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .config import QB_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Typed exception hierarchy
# ---------------------------------------------------------------------------

class QBAPIError(Exception):
    """Base class for all QB API errors."""
    def __init__(self, message: str, status_code: int = 0, raw: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw


class QBAuthError(QBAPIError):
    """Raised on HTTP 401 — token is expired or invalid."""


class QBRateLimitError(QBAPIError):
    """Raised on HTTP 429 — caller must back off."""


class QBBadRequestError(QBAPIError):
    """Raised on HTTP 400 — malformed query or date range."""


# ---------------------------------------------------------------------------
# URL construction helpers
# ---------------------------------------------------------------------------

def _api_base() -> str:
    """
    Return QB API base URL.
    Reads QB_ENVIRONMENT env var: 'sandbox' -> sandbox URL, else production.
    """
    env = os.environ.get("QB_ENVIRONMENT", "production").lower()
    if env == "sandbox":
        return "https://sandbox-quickbooks.api.intuit.com"
    return QB_CONFIG.API_BASE_URL   # https://quickbooks.api.intuit.com


# QB uses v3 for entity queries and a separate /v4 path for Reports API
_QB_ENTITY_PATH = "/v3/company/{realm_id}"
_QB_REPORT_PATH = "/v3/company/{realm_id}/reports"   # Reports live under v3 path in QBO


# ---------------------------------------------------------------------------
# Client class
# ---------------------------------------------------------------------------

class QuickBooksAPIClient:
    """
    Async QuickBooks Online API client.

    Stateless — all methods receive realm_id and access_token per call.
    A new httpx.AsyncClient is created per request to match project patterns.

    Usage:
        client = QuickBooksAPIClient()
        pl = await client.get_profit_loss_report(
            realm_id="9341452714377780",
            access_token="<bearer token>",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
    """

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        """Build standard QB API request headers."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _raise_for_status(self, response: httpx.Response) -> None:
        """
        Inspect QB response status and raise the appropriate typed error.

        QB error envelope (when present):
            {"Fault": {"Error": [{"Message": "...", "code": "..."}], "type": "..."}}
        """
        if response.status_code == 200:
            return

        raw = response.text
        fault_message = self._extract_fault_message(raw)

        if response.status_code == 401:
            logger.warning("QB API: 401 Unauthorized (realm=unknown)")
            raise QBAuthError(
                f"QB access token is invalid or expired: {fault_message}",
                status_code=401,
                raw=raw,
            )

        if response.status_code == 429:
            logger.warning("QB API: 429 Rate limited")
            raise QBRateLimitError(
                "QB API rate limit exceeded. Retry after back-off.",
                status_code=429,
                raw=raw,
            )

        if response.status_code == 400:
            logger.error("QB API: 400 Bad request: %s", fault_message)
            raise QBBadRequestError(
                f"QB API bad request: {fault_message}",
                status_code=400,
                raw=raw,
            )

        logger.error(
            "QB API: unexpected status %s: %s", response.status_code, fault_message
        )
        raise QBAPIError(
            f"QB API error {response.status_code}: {fault_message}",
            status_code=response.status_code,
            raw=raw,
        )

    @staticmethod
    def _extract_fault_message(raw: str) -> str:
        """Pull error message from QB Fault envelope, or return truncated raw body."""
        try:
            body = json.loads(raw)
            errors = body.get("Fault", {}).get("Error", [])
            if errors:
                return errors[0].get("Message", raw[:200])
        except (ValueError, AttributeError):
            pass
        return raw[:200]

    # -----------------------------------------------------------------------
    # Public API methods
    # -----------------------------------------------------------------------

    async def get_profit_loss_report(
        self,
        realm_id: str,
        access_token: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Fetch Profit & Loss report from QB Reports API.

        Args:
            realm_id:     QB Company ID (Realm ID), e.g. "9341452714377780"
            access_token: Decrypted Bearer token from QuickBooksTokenRecord
            start_date:   ISO date string, e.g. "2024-01-01"
            end_date:     ISO date string, e.g. "2024-12-31"

        Returns:
            Raw QB ProfitAndLoss report dict. Callers should treat this as
            opaque and pass it to a normalizer/mapper layer.

        Raises:
            QBAuthError:        Token invalid or expired
            QBRateLimitError:   QB is throttling requests
            QBBadRequestError:  Invalid date format or params
            QBAPIError:         Any other QB API fault
        """
        url = (
            f"{_api_base()}"
            f"{_QB_REPORT_PATH.format(realm_id=realm_id)}"
            "/ProfitAndLoss"
        )
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "accounting_method": "Accrual",
        }

        logger.info(
            "QB get_profit_loss_report realm=%s start=%s end=%s",
            realm_id, start_date, end_date,
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(QB_CONFIG.REQUEST_TIMEOUT_SECONDS, connect=10.0)
            ) as client:
                response = await client.get(
                    url,
                    headers=self._build_headers(access_token),
                    params=params,
                )
        except httpx.TimeoutException as exc:
            logger.error("QB get_profit_loss_report timed out: realm=%s", realm_id)
            raise QBAPIError("QB API request timed out") from exc
        except httpx.ConnectError as exc:
            logger.error("QB get_profit_loss_report connection error: %s", exc)
            raise QBAPIError("Cannot connect to QuickBooks API") from exc

        self._raise_for_status(response)
        logger.info("QB get_profit_loss_report success: realm=%s", realm_id)
        return response.json()

    async def get_accounts(
        self,
        realm_id: str,
        access_token: str,
        account_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the Account entity list from QB.

        Args:
            realm_id:     QB Company ID
            access_token: Decrypted Bearer token
            account_type: Optional QB AccountType filter, e.g. "Income", "Expense",
                          "Bank", "AccountsReceivable". If None, all accounts returned.

        Returns:
            List of account dicts, each normalized to:
                {
                    "id":              str,   # QB Account.Id
                    "name":            str,   # QB Account.Name
                    "account_type":    str,   # QB Account.AccountType
                    "account_subtype": str,   # QB Account.AccountSubType
                    "current_balance": float, # QB Account.CurrentBalance
                    "active":          bool,  # QB Account.Active
                    "currency":        str,   # QB Account.CurrencyRef.value
                }

        Raises:
            QBAuthError, QBRateLimitError, QBBadRequestError, QBAPIError
        """
        url = (
            f"{_api_base()}"
            f"{_QB_ENTITY_PATH.format(realm_id=realm_id)}"
            "/query"
        )

        if account_type:
            sql = (
                f"SELECT * FROM Account WHERE AccountType = '{account_type}' "
                "AND Active = true MAXRESULTS 1000"
            )
        else:
            sql = "SELECT * FROM Account WHERE Active = true MAXRESULTS 1000"

        logger.info(
            "QB get_accounts realm=%s account_type=%s",
            realm_id, account_type or "all",
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(QB_CONFIG.REQUEST_TIMEOUT_SECONDS, connect=10.0)
            ) as client:
                response = await client.get(
                    url,
                    headers=self._build_headers(access_token),
                    params={"query": sql, "minorversion": "65"},
                )
        except httpx.TimeoutException as exc:
            logger.error("QB get_accounts timed out: realm=%s", realm_id)
            raise QBAPIError("QB API request timed out") from exc
        except httpx.ConnectError as exc:
            logger.error("QB get_accounts connection error: %s", exc)
            raise QBAPIError("Cannot connect to QuickBooks API") from exc

        self._raise_for_status(response)

        body = response.json()
        raw_accounts = (
            body
            .get("QueryResponse", {})
            .get("Account", [])
        )

        logger.info(
            "QB get_accounts success: realm=%s count=%d",
            realm_id, len(raw_accounts),
        )
        return [self._normalize_account(a) for a in raw_accounts]

    async def get_journal_entries(
        self,
        realm_id: str,
        access_token: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query JournalEntry entities for a date range from QB.

        Args:
            realm_id:     QB Company ID
            access_token: Decrypted Bearer token
            start_date:   ISO date string, e.g. "2024-01-01"
            end_date:     ISO date string, e.g. "2024-12-31"

        Returns:
            List of journal entry dicts, each normalized to:
                {
                    "id":        str,              # QB JournalEntry.Id
                    "txn_date":  str,              # QB JournalEntry.TxnDate (ISO date)
                    "doc_number": str | None,      # QB JournalEntry.DocNumber
                    "private_note": str | None,    # QB JournalEntry.PrivateNote
                    "lines": List[dict],           # Parsed JournalEntryLine items
                    "sync_token": str,             # QB JournalEntry.SyncToken
                    "created_at": str,             # QB MetaData.CreateTime
                    "updated_at": str,             # QB MetaData.LastUpdatedTime
                }
            Each line in "lines":
                {
                    "id":           str,
                    "description":  str | None,
                    "amount":       float,
                    "posting_type": str,   # "Debit" | "Credit"
                    "account_id":   str,
                    "account_name": str,
                }

        Raises:
            QBAuthError, QBRateLimitError, QBBadRequestError, QBAPIError
        """
        url = (
            f"{_api_base()}"
            f"{_QB_ENTITY_PATH.format(realm_id=realm_id)}"
            "/query"
        )

        sql = (
            f"SELECT * FROM JournalEntry "
            f"WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' "
            "ORDERBY TxnDate ASC MAXRESULTS 1000"
        )

        logger.info(
            "QB get_journal_entries realm=%s start=%s end=%s",
            realm_id, start_date, end_date,
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(QB_CONFIG.REQUEST_TIMEOUT_SECONDS, connect=10.0)
            ) as client:
                response = await client.get(
                    url,
                    headers=self._build_headers(access_token),
                    params={"query": sql, "minorversion": "65"},
                )
        except httpx.TimeoutException as exc:
            logger.error("QB get_journal_entries timed out: realm=%s", realm_id)
            raise QBAPIError("QB API request timed out") from exc
        except httpx.ConnectError as exc:
            logger.error("QB get_journal_entries connection error: %s", exc)
            raise QBAPIError("Cannot connect to QuickBooks API") from exc

        self._raise_for_status(response)

        body = response.json()
        raw_entries = (
            body
            .get("QueryResponse", {})
            .get("JournalEntry", [])
        )

        logger.info(
            "QB get_journal_entries success: realm=%s count=%d",
            realm_id, len(raw_entries),
        )
        return [self._normalize_journal_entry(je) for je in raw_entries]

    # -----------------------------------------------------------------------
    # Normalizers — shape raw QB JSON into stable internal dicts
    # -----------------------------------------------------------------------

    @staticmethod
    def _normalize_account(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw QB Account entity into a stable internal dict."""
        currency_ref = raw.get("CurrencyRef", {})
        return {
            "id":              raw.get("Id", ""),
            "name":            raw.get("Name", ""),
            "account_type":    raw.get("AccountType", ""),
            "account_subtype": raw.get("AccountSubType", ""),
            "current_balance": float(raw.get("CurrentBalance", 0.0)),
            "active":          bool(raw.get("Active", True)),
            "currency":        currency_ref.get("value", "USD"),
        }

    @staticmethod
    def _normalize_journal_entry(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw QB JournalEntry entity into a stable internal dict."""
        meta = raw.get("MetaData", {})
        lines = []
        for line in raw.get("Line", []):
            detail = line.get("JournalEntryLineDetail", {})
            account_ref = detail.get("AccountRef", {})
            lines.append({
                "id":           line.get("Id", ""),
                "description":  line.get("Description"),
                "amount":       float(line.get("Amount", 0.0)),
                "posting_type": detail.get("PostingType", ""),  # "Debit" | "Credit"
                "account_id":   account_ref.get("value", ""),
                "account_name": account_ref.get("name", ""),
            })
        return {
            "id":           raw.get("Id", ""),
            "txn_date":     raw.get("TxnDate", ""),
            "doc_number":   raw.get("DocNumber"),
            "private_note": raw.get("PrivateNote"),
            "lines":        lines,
            "sync_token":   raw.get("SyncToken", ""),
            "created_at":   meta.get("CreateTime", ""),
            "updated_at":   meta.get("LastUpdatedTime", ""),
        }


# ---------------------------------------------------------------------------
# Module-level singleton factory (matches get_oauth_service() pattern)
# ---------------------------------------------------------------------------

_qb_api_client: Optional[QuickBooksAPIClient] = None


def get_quickbooks_api_client() -> QuickBooksAPIClient:
    """Return the shared QuickBooksAPIClient singleton."""
    global _qb_api_client
    if _qb_api_client is None:
        _qb_api_client = QuickBooksAPIClient()
    return _qb_api_client
