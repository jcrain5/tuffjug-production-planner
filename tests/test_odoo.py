from fastapi.testclient import TestClient

from app.config import Settings
from app.integrations.odoo import OdooClient
from app.main import app


class FakeOdooClient:
    def __init__(self):
        self.connected = True

    def connect(self):
        return True

    def get_products(self):
        return [{"id": 1, "name": "Widget"}]

    def get_boms(self):
        return [{"id": 10, "name": "Main BOM"}]

    def get_reordering_rules(self):
        return [{"id": 100, "product_id": 1, "product_min_qty": 5}]

    def get_inventory(self):
        return [{"id": 200, "product_id": 1, "quantity": 12.0}]

    def get_manufacturing_orders(self):
        return [{"id": 300, "name": "MO-001", "state": "draft"}]

    def get_purchase_orders(self):
        return [{"id": 400, "name": "PO-001", "state": "draft"}]


class FakeCommonProxy:
    def __init__(self, url):
        self.url = url

    def version(self):
        return {"server_version": "19.0"}

    def authenticate(self, db, username, password, context):
        return 7


class FakeObjectProxy:
    def __init__(self, url):
        self.url = url

    def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
        if model == "product.product" and method == "search_read":
            return [{"id": 1, "name": "Widget"}]
        return []


def test_connect_authenticates_with_odoo(monkeypatch):
    def fake_server_proxy(url):
        return FakeCommonProxy(url)

    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", fake_server_proxy)

    client = OdooClient(
        config=Settings(
            odoo_url="https://odoo.example",
            odoo_database="atlas",
            odoo_username="admin",
            odoo_api_key="secret",
        )
    )

    assert client.connect() is True
    assert client.connected is True
    assert client.uid == 7


def test_get_products_returns_models(monkeypatch):
    def fake_server_proxy(url):
        return FakeObjectProxy(url)

    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", fake_server_proxy)

    client = OdooClient(
        config=Settings(
            odoo_url="https://odoo.example",
            odoo_database="atlas",
            odoo_username="admin",
            odoo_api_key="secret",
        )
    )
    client.connected = True
    client.uid = 7

    products = client.get_products()

    assert len(products) == 1
    assert products[0].id == 1
    assert products[0].name == "Widget"


def test_odoo_status_endpoint_returns_connected_true(monkeypatch):
    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: FakeCommonProxy(url))

    client = TestClient(app)
    response = client.get("/odoo/status")

    assert response.status_code == 200
    assert response.json() == {"connected": True}


def test_products_endpoint_returns_structured_payload(monkeypatch):
    monkeypatch.setattr("app.main.OdooClient", FakeOdooClient)

    client = TestClient(app)
    response = client.get("/odoo/products")

    assert response.status_code == 200
    assert response.json() == {"connected": True, "count": 1, "items": [{"id": 1, "name": "Widget"}]}


def test_boms_endpoint_returns_structured_payload(monkeypatch):
    monkeypatch.setattr("app.main.OdooClient", FakeOdooClient)

    client = TestClient(app)
    response = client.get("/odoo/boms")

    assert response.status_code == 200
    assert response.json() == {"connected": True, "count": 1, "items": [{"id": 10, "name": "Main BOM"}]}
