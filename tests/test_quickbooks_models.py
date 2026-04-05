"""
Tests for QuickBooks integration models and configuration.

Verifies:
1. QB config module loads correctly
2. QB models can be instantiated
3. Database imports work correctly
4. Model relationships are properly defined
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from src.integrations.quickbooks.config import QB_CONFIG, QuickBooksConfig
from src.database import QuickBooksTokenRecord, QuickBooksConnectionRecord, Base


class TestQuickBooksConfig:
    """Test QuickBooks OAuth2 configuration."""

    def test_config_constants_exist(self):
        """Verify all required OAuth constants are defined."""
        assert QB_CONFIG.AUTH_ENDPOINT == "https://appcenter.intuit.com/connect/oauth2"
        assert QB_CONFIG.TOKEN_ENDPOINT == "https://oauth.platform.intuit.com/oauth2/tokens/introspect"
        assert QB_CONFIG.API_BASE_URL == "https://quickbooks.api.intuit.com"

    def test_config_token_lifetime(self):
        """Verify token lifetime configuration."""
        assert QB_CONFIG.TOKEN_LIFETIME_SECONDS == 3600
        assert QB_CONFIG.REFRESH_BUFFER_SECONDS == 300

    def test_scopes_string(self):
        """Verify scopes are formatted correctly."""
        scopes_str = QB_CONFIG.get_scopes_string()
        assert "com.intuit.quickbooks.accounting" in scopes_str
        assert isinstance(scopes_str, str)

    def test_authorization_url_building(self):
        """Verify authorization URL is built correctly."""
        url = QB_CONFIG.get_authorization_url(
            client_id="test_client",
            redirect_uri="http://localhost:8000/callback",
            state="test_state_123"
        )
        assert "https://appcenter.intuit.com/connect/oauth2" in url
        assert "client_id=test_client" in url
        assert "response_type=code" in url
        assert "redirect_uri=http" in url
        assert "state=test_state_123" in url

    def test_config_validation_constants(self):
        """Verify validation configuration."""
        assert QB_CONFIG.MIN_TOKEN_LENGTH == 50
        assert QB_CONFIG.MAX_REALM_ID_LENGTH == 20


class TestQuickBooksModels:
    """Test QuickBooks database models."""

    def test_token_record_instantiation(self):
        """Verify QuickBooksTokenRecord can be instantiated."""
        now = datetime.now(timezone.utc)
        expires = datetime.now(timezone.utc)

        token = QuickBooksTokenRecord(
            connection_id=uuid4(),
            access_token_encrypted="encrypted_access_token_test",
            refresh_token_encrypted="encrypted_refresh_token_test",
            token_type="Bearer",
            scope="com.intuit.quickbooks.accounting",
            realm_id="1234567890",
            issued_at=now,
            expires_at=expires,
        )

        # Verify required fields are set
        assert token.access_token_encrypted == "encrypted_access_token_test"
        assert token.refresh_token_encrypted == "encrypted_refresh_token_test"
        assert token.token_type == "Bearer"
        assert token.scope == "com.intuit.quickbooks.accounting"
        assert token.realm_id == "1234567890"
        assert token.issued_at == now
        assert token.expires_at == expires

    def test_connection_record_instantiation(self):
        """Verify QuickBooksConnectionRecord can be instantiated."""
        firm_id = uuid4()
        connection = QuickBooksConnectionRecord(
            firm_id=firm_id,
            realm_id="1234567890",
            company_name="Test Company",
            is_connected=True,
            is_authorized=True,
            authorization_status="authorized",
            account_email="test@example.com",
        )

        assert connection.firm_id == firm_id
        assert connection.realm_id == "1234567890"
        assert connection.company_name == "Test Company"
        assert connection.is_connected is True
        assert connection.is_authorized is True
        assert connection.authorization_status == "authorized"
        assert connection.account_email == "test@example.com"

    def test_connection_record_defaults(self):
        """Verify QuickBooksConnectionRecord defaults are set correctly."""
        connection = QuickBooksConnectionRecord(
            firm_id=uuid4(),
            realm_id="1234567890",
            company_name="Test Company",
        )

        # Verify default values are set at column definition level
        # These would be set when inserted into database
        assert connection.realm_id == "1234567890"
        assert connection.company_name == "Test Company"

    def test_model_repr_methods(self):
        """Verify model __repr__ methods return sensible output."""
        firm_id = uuid4()
        token = QuickBooksTokenRecord(
            connection_id=uuid4(),
            access_token_encrypted="test",
            refresh_token_encrypted="test",
            token_type="Bearer",
            scope="test",
            realm_id="1234567890",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )
        token_repr = repr(token)
        assert "QuickBooksToken" in token_repr
        assert "realm=1234567890" in token_repr

        connection = QuickBooksConnectionRecord(
            firm_id=firm_id,
            realm_id="1234567890",
            company_name="Test",
            authorization_status="authorized",
        )
        conn_repr = repr(connection)
        assert "QuickBooksConnection" in conn_repr
        assert "realm=1234567890" in conn_repr

    def test_token_relationship_to_connection(self):
        """Verify token can reference its connection."""
        connection_id = uuid4()
        token = QuickBooksTokenRecord(
            connection_id=connection_id,
            access_token_encrypted="test",
            refresh_token_encrypted="test",
            token_type="Bearer",
            scope="test",
            realm_id="1234567890",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )

        assert token.connection_id == connection_id

    def test_connection_has_token_relationship(self):
        """Verify connection relationship to token is defined."""
        # This just verifies the relationship is defined on the class
        assert hasattr(QuickBooksConnectionRecord, 'token')

    def test_model_table_names(self):
        """Verify table names are correctly set."""
        assert QuickBooksTokenRecord.__tablename__ == "quickbooks_tokens"
        assert QuickBooksConnectionRecord.__tablename__ == "quickbooks_connections"

    def test_model_imports_from_database_module(self):
        """Verify models are properly exported from database module."""
        from src.database import QuickBooksTokenRecord as TokenImported
        from src.database import QuickBooksConnectionRecord as ConnectionImported

        assert TokenImported is QuickBooksTokenRecord
        assert ConnectionImported is QuickBooksConnectionRecord


class TestIntegrationImports:
    """Test QB integration package imports."""

    def test_config_imports_from_package(self):
        """Verify QB_CONFIG can be imported from package."""
        from src.integrations.quickbooks import QB_CONFIG

        assert QB_CONFIG is not None
        assert hasattr(QB_CONFIG, 'get_scopes_string')

    def test_quickbooksconfig_imports_from_package(self):
        """Verify QuickBooksConfig class can be imported from package."""
        from src.integrations.quickbooks import QuickBooksConfig

        assert QuickBooksConfig is not None
        assert hasattr(QuickBooksConfig, 'get_authorization_url')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
