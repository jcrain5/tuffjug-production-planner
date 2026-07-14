from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shopify_status_endpoint_returns_connected(monkeypatch):
    class FakeShopifyClient:
        def status(self):
            return {
                "connected": True,
                "store": "8b5c56-36.myshopify.com",
                "granted_scopes": ["read_orders"],
                "token_expiration_time": "2026-01-01T00:00:00+00:00",
            }

    monkeypatch.setattr("app.main.ShopifyClient", FakeShopifyClient)
    client = TestClient(app)

    response = client.get("/shopify/status")

    assert response.status_code == 200
    assert response.json() == {
        "connected": True,
        "store": "8b5c56-36.myshopify.com",
        "granted_scopes": ["read_orders"],
        "token_expiration_time": "2026-01-01T00:00:00+00:00",
    }
