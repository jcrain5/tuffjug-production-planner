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
            return {"connected": True, "configured": True}

    monkeypatch.setattr("app.main.ShopifyClient", FakeShopifyClient)
    client = TestClient(app)

    response = client.get("/shopify/status")

    assert response.status_code == 200
    assert response.json() == {"connected": True, "configured": True}
