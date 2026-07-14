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


def test_get_boms_queries_active_boms_from_mrp_bom(monkeypatch):
    class BOMProxy:
        def __init__(self):
            self.calls = []

        def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
            self.calls.append((model, method, args, kwargs))
            return [{"id": 10, "name": "Main BOM", "type": "normal"}]

    proxy = BOMProxy()
    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: proxy)

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
    client.models = proxy

    boms = client.get_boms()

    assert len(boms) == 1
    assert proxy.calls[0][0] == "mrp.bom"
    assert proxy.calls[0][1] == "search_read"
    assert proxy.calls[0][2] == [[['active', '=', True]]]
    assert proxy.calls[0][3]["fields"] == [
        "id",
        "display_name",
        "code",
        "active",
        "type",
        "product_tmpl_id",
        "product_id",
        "product_qty",
        "uom_id",
        "bom_line_ids",
        "operation_ids",
        "ready_to_produce",
        "produce_delay",
        "days_to_prepare_mo",
        "enable_batch_size",
        "batch_size",
        "company_id",
    ]


def test_diagnose_bom_access_keeps_running_after_a_failure(monkeypatch):
    class MixedFailureProxy:
        def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
            if method == "search_count":
                if args == [[]]:
                    raise PermissionError("Access denied")
                return 0
            if method == "search":
                return [1, 2]
            if method == "search_read":
                return [{"id": 1}]
            if method == "fields_get":
                return {"id": {"type": "integer"}}
            return None

    proxy = MixedFailureProxy()
    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: proxy)

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
    client.models = proxy

    result = client.diagnose_bom_access()

    assert result["connected"] is True
    assert result["checks"]["search_count_empty"]["error"]["type"] == "PermissionError"
    assert result["checks"]["search_count_active"]["result"] == 0
    assert result["checks"]["search"]["result"] == [1, 2]
    assert result["checks"]["search_read"]["result"] == [{"id": 1}]
    assert result["checks"]["fields_get"]["result"] == {"id": {"type": "integer"}}


def test_diagnose_bom_access_returns_zero_records(monkeypatch):
    class ZeroRecordsProxy:
        def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
            if method == "search_count":
                return 0
            if method == "search":
                return []
            if method == "search_read":
                return []
            if method == "fields_get":
                return {"id": {"type": "integer"}}
            return None

    proxy = ZeroRecordsProxy()
    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: proxy)

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
    client.models = proxy

    result = client.diagnose_bom_access()

    assert result["connected"] is True
    assert result["checks"]["search_count_empty"]["result"] == 0
    assert result["checks"]["search_count_active"]["result"] == 0
    assert result["checks"]["search"]["result"] == []
    assert result["checks"]["search_read"]["result"] == []
    assert result["checks"]["fields_get"]["error"] is None


def test_diagnose_bom_access_returns_records(monkeypatch):
    class SuccessProxy:
        def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
            if method == "search_count":
                return 2
            if method == "search":
                return [1, 2]
            if method == "search_read":
                return [{"id": 1}, {"id": 2}]
            if method == "fields_get":
                return {"id": {"type": "integer"}, "active": {"type": "boolean"}}
            return None

    proxy = SuccessProxy()
    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: proxy)

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
    client.models = proxy

    result = client.diagnose_bom_access()

    assert result["connected"] is True
    assert result["checks"]["search_count_empty"]["error"] is None
    assert result["checks"]["search_count_empty"]["result"] == 2
    assert result["checks"]["search_count_active"]["result"] == 2
    assert result["checks"]["search"]["result"] == [1, 2]
    assert result["checks"]["search_read"]["result"][0]["id"] == 1
    assert result["checks"]["fields_get"]["result"]["active"]["type"] == "boolean"


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
