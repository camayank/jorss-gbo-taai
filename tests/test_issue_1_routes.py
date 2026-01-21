"""
Test Issue #1: Single Entry Point Routes

Tests that all entry point routes work correctly after implementation.
"""

from fastapi.testclient import TestClient
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.web.app import app

client = TestClient(app)


def test_root_route_exists():
    """Test that / route exists and returns 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_file_route_exists():
    """Test that /file route exists and returns 200."""
    response = client.get("/file")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_file_route_serves_same_content_as_root():
    """Test that /file serves the same interface as /."""
    root_response = client.get("/")
    file_response = client.get("/file")

    # Both should return 200
    assert root_response.status_code == 200
    assert file_response.status_code == 200

    # Both should be HTML
    assert "text/html" in root_response.headers["content-type"]
    assert "text/html" in file_response.headers["content-type"]

    # Content should be identical (same template)
    assert len(root_response.text) == len(file_response.text)


def test_smart_tax_redirects_to_file():
    """Test that /smart-tax redirects to /file?mode=smart."""
    response = client.get("/smart-tax", follow_redirects=False)

    # Should be a 301 permanent redirect
    assert response.status_code == 301
    assert response.headers["location"] == "/file?mode=smart"


def test_smart_tax_redirect_chain_works():
    """Test that following /smart-tax redirect chain works."""
    response = client.get("/smart-tax", follow_redirects=True)

    # After following redirects, should land on /file successfully
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_client_redirects_to_file():
    """Test that /client redirects to /file."""
    response = client.get("/client", follow_redirects=False)

    # Should be a 302 temporary redirect
    assert response.status_code == 302
    assert response.headers["location"] == "/file"


def test_client_redirect_works():
    """Test that following /client redirect works."""
    response = client.get("/client", follow_redirects=True)

    # After following redirect, should land on /file successfully
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_file_with_mode_parameter():
    """Test that /file?mode=smart accepts query parameters."""
    response = client.get("/file?mode=smart")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_file_with_express_mode():
    """Test that /file?mode=express works."""
    response = client.get("/file?mode=express")
    assert response.status_code == 200


def test_file_with_chat_mode():
    """Test that /file?mode=chat works."""
    response = client.get("/file?mode=chat")
    assert response.status_code == 200


def test_no_404_errors_on_main_routes():
    """Test that main client-facing routes don't return 404."""
    routes = ["/", "/file", "/smart-tax", "/client"]

    for route in routes:
        response = client.get(route, follow_redirects=True)
        assert response.status_code != 404, f"Route {route} returned 404"
        assert response.status_code == 200, f"Route {route} returned {response.status_code}"


if __name__ == "__main__":
    print("Running Issue #1 Route Tests...")
    print()

    print("✓ Testing / route...")
    test_root_route_exists()

    print("✓ Testing /file route...")
    test_file_route_exists()

    print("✓ Testing / and /file serve same content...")
    test_file_route_serves_same_content_as_root()

    print("✓ Testing /smart-tax redirect...")
    test_smart_tax_redirects_to_file()

    print("✓ Testing /smart-tax redirect chain...")
    test_smart_tax_redirect_chain_works()

    print("✓ Testing /client redirect...")
    test_client_redirects_to_file()

    print("✓ Testing /client redirect chain...")
    test_client_redirect_works()

    print("✓ Testing /file with mode parameters...")
    test_file_with_mode_parameter()
    test_file_with_express_mode()
    test_file_with_chat_mode()

    print("✓ Testing no 404 errors...")
    test_no_404_errors_on_main_routes()

    print()
    print("✅ All Issue #1 tests passed!")
