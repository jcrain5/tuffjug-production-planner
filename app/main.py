from fastapi import FastAPI

from app.integrations.odoo import OdooClient

app = FastAPI(title="Atlas", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _build_collection_payload(items: list[dict], connected: bool) -> dict[str, object]:
    return {"connected": connected, "count": len(items), "items": items}


@app.get("/odoo/status")
def odoo_status() -> dict[str, bool]:
    client = OdooClient()
    return {"connected": client.connect()}


@app.get("/odoo/products")
def odoo_products() -> dict[str, object]:
    client = OdooClient()
    connected = client.connect()
    return _build_collection_payload(client.get_products(), connected)


@app.get("/odoo/boms")
def odoo_boms() -> dict[str, object]:
    client = OdooClient()
    connected = client.connect()
    return _build_collection_payload(client.get_boms(), connected)


@app.get("/odoo/reordering-rules")
def odoo_reordering_rules() -> dict[str, object]:
    client = OdooClient()
    connected = client.connect()
    return _build_collection_payload(client.get_reordering_rules(), connected)


@app.get("/odoo/inventory")
def odoo_inventory() -> dict[str, object]:
    client = OdooClient()
    connected = client.connect()
    return _build_collection_payload(client.get_inventory(), connected)


@app.get("/odoo/manufacturing-orders")
def odoo_manufacturing_orders() -> dict[str, object]:
    client = OdooClient()
    connected = client.connect()
    return _build_collection_payload(client.get_manufacturing_orders(), connected)


@app.get("/odoo/purchase-orders")
def odoo_purchase_orders() -> dict[str, object]:
    client = OdooClient()
    connected = client.connect()
    return _build_collection_payload(client.get_purchase_orders(), connected)
