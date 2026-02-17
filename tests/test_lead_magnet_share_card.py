from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.lead_magnet_pages import lead_magnet_pages_router


def _build_web_app() -> FastAPI:
    app = FastAPI()
    app.include_router(lead_magnet_pages_router)
    return app


def test_share_card_svg_endpoint_renders():
    client = TestClient(_build_web_app())
    response = client.get("/lead-magnet/share-card.svg?score=67&band=Good&cpa=default&savings=%245%2C200")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in response.text
    assert "67" in response.text

