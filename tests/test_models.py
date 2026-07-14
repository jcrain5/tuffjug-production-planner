from app.integrations.odoo import OdooClient
from app.models.odoo import (
    BomComponentModel,
    BomModel,
    InventoryItemModel,
    ManufacturingOrderModel,
    ProductModel,
    PurchaseOrderModel,
    ReorderingRuleModel,
)


class FakeModelProxy:
    def __init__(self, records):
        self.records = records

    def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
        return self.records


def test_odoo_client_maps_products_into_product_models(monkeypatch):
    records = [{"id": 1, "name": "Widget", "default_code": "W-001", "list_price": 25.5}]
    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: FakeModelProxy(records))

    client = OdooClient()
    client.connected = True
    client.uid = 7
    client.models = FakeModelProxy(records)

    products = client.get_products()

    assert len(products) == 1
    assert isinstance(products[0], ProductModel)
    assert products[0].name == "Widget"
    assert products[0].default_code == "W-001"


def test_odoo_client_maps_boms_and_components(monkeypatch):
    bom_records = [{"id": 10, "name": "Main BOM", "type": "normal"}]
    component_records = [{"id": 100, "bom_id": 10, "product_id": 1, "product_qty": 2.0}]

    class MultiProxy:
        def __init__(self, bom_records, component_records):
            self.bom_records = bom_records
            self.component_records = component_records

        def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
            if model == "mrp.bom":
                return self.bom_records
            if model == "mrp.bom.line":
                return self.component_records
            return []

    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: MultiProxy(bom_records, component_records))

    client = OdooClient()
    client.connected = True
    client.uid = 7
    client.models = MultiProxy(bom_records, component_records)

    boms = client.get_boms()
    components = client.get_bom_components()

    assert isinstance(boms[0], BomModel)
    assert isinstance(components[0], BomComponentModel)
    assert components[0].product_qty == 2.0


def test_odoo_client_maps_inventory_and_orders(monkeypatch):
    inventory_records = [{"id": 200, "product_id": 1, "quantity": 12.0, "location_id": 3}]
    reorder_records = [{"id": 300, "product_id": 1, "product_min_qty": 5.0}]
    mo_records = [{"id": 400, "name": "MO-001", "state": "draft", "product_id": 1, "bom_id": 10}]
    po_records = [{"id": 500, "name": "PO-001", "state": "draft", "partner_id": 2, "date_order": "2024-01-01"}]

    class InventoryProxy:
        def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
            if model == "stock.quant":
                return inventory_records
            if model == "stock.warehouse.orderpoint":
                return reorder_records
            if model == "mrp.production":
                return mo_records
            if model == "purchase.order":
                return po_records
            return []

    monkeypatch.setattr("app.integrations.odoo.xmlrpc_client.ServerProxy", lambda url: InventoryProxy())

    client = OdooClient()
    client.connected = True
    client.uid = 7
    client.models = InventoryProxy()

    inventory = client.get_inventory()
    rules = client.get_reordering_rules()
    mos = client.get_manufacturing_orders()
    pos = client.get_purchase_orders()

    assert isinstance(inventory[0], InventoryItemModel)
    assert isinstance(rules[0], ReorderingRuleModel)
    assert isinstance(mos[0], ManufacturingOrderModel)
    assert isinstance(pos[0], PurchaseOrderModel)
