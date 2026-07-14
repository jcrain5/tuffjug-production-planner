from pathlib import Path
from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.integrations.odoo import OdooClient
from app.integrations.shopify import ShopifyError
from app.integrations.shopify import ShopifyClient
from app.planning.replenishment import ShortagePlanningEngine

app = FastAPI(title="Atlas", version="0.1.0")

try:
    from starlette.templating import Jinja2Templates
except ImportError:  # pragma: no cover - fallback for environments without Jinja2
    Jinja2Templates = None

if Jinja2Templates is not None:
    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
else:
    templates = None


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


@app.get("/odoo/boms/diagnostic")
def odoo_boms_diagnostic() -> dict[str, object]:
    client = OdooClient()
    return client.diagnose_bom_access()


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


@app.get("/shopify/status")
def shopify_status() -> dict[str, Any]:
    client = ShopifyClient()
    return client.status()


@app.get("/shopify/orders")
def shopify_orders(
    start_date: str | None = None,
    end_date: str | None = None,
    include_excluded: bool = False,
) -> dict[str, object]:
    client = ShopifyClient()
    end_value = end_date or date.today().isoformat()
    start_value = start_date or (date.today() - timedelta(days=30)).isoformat()

    try:
        items = client.get_order_lines(start_date=start_value, end_date=end_value, include_excluded=include_excluded)
        return {
            "connected": True,
            "count": len(items),
            "start_date": start_value,
            "end_date": end_value,
            "items": items,
        }
    except ShopifyError as exc:
        return {
            "connected": False,
            "count": 0,
            "start_date": start_value,
            "end_date": end_value,
            "items": [],
            "error": str(exc),
        }
    except Exception:
        return {
            "connected": False,
            "count": 0,
            "start_date": start_value,
            "end_date": end_value,
            "items": [],
            "error": "Shopify request failed",
        }


@app.get("/shopify/demand-by-sku")
def shopify_demand_by_sku(start_date: str | None = None, end_date: str | None = None) -> dict[str, object]:
    client = ShopifyClient()
    end_value = end_date or date.today().isoformat()
    start_value = start_date or (date.today() - timedelta(days=30)).isoformat()

    try:
        items = client.get_demand_by_sku(start_date=start_value, end_date=end_value)
        return {
            "connected": True,
            "count": len(items),
            "start_date": start_value,
            "end_date": end_value,
            "items": items,
        }
    except ShopifyError as exc:
        return {
            "connected": False,
            "count": 0,
            "start_date": start_value,
            "end_date": end_value,
            "items": [],
            "error": str(exc),
        }
    except Exception:
        return {
            "connected": False,
            "count": 0,
            "start_date": start_value,
            "end_date": end_value,
            "items": [],
            "error": "Shopify request failed",
        }


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request) -> HTMLResponse:
    client = OdooClient()
    connected = client.connect()
    inventory = client.get_inventory() if connected else []
    reordering_rules = client.get_reordering_rules() if connected else []
    products = client.get_products() if connected else []

    product_lookup = {product.id: getattr(product, "name", "Unknown") for product in products if getattr(product, "id", None) is not None}
    rule_lookup = {
        getattr(rule, "product_id", None): getattr(rule, "product_min_qty", None)
        for rule in reordering_rules
        if getattr(rule, "product_id", None) is not None
    }

    inventory_rows = []
    for item in inventory:
        product_id = getattr(item, "product_id", None)
        inventory_rows.append(
            {
                "product_name": product_lookup.get(product_id, f"Product {product_id}"),
                "on_hand_quantity": getattr(item, "quantity", 0),
                "reserved_quantity": 0,
                "available_quantity": getattr(item, "quantity", 0),
                "uom": "Units",
                "reordering_rule": rule_lookup.get(product_id, "—"),
            }
        )

    context = {
        "request": request,
        "connected": connected,
        "inventory_rows": inventory_rows,
    }
    if templates is None:
        return HTMLResponse(content="<html><body><h1>Inventory</h1><p>Template rendering is unavailable in this environment.</p></body></html>")
    return templates.TemplateResponse(request, "inventory.html", context)


@app.get("/shortages", response_class=HTMLResponse)
async def shortages_page(request: Request) -> HTMLResponse:
    client = OdooClient()
    connected = client.connect()
    boms = []
    components = []
    products = []
    inventory = []
    parent_options: list[dict[str, Any]] = []
    shortage_rows: list[dict[str, Any]] = []
    selected_product_id: int | None = None
    quantity_to_produce = 1.0

    if connected:
        boms = client.get_boms()
        components = client.get_bom_components()
        products = client.get_products()
        inventory = client.get_inventory()
        parent_options = [
            {
                "id": getattr(bom, "product_template_id", None),
                "display_name": getattr(bom, "display_name", None) or "Unnamed BOM",
                "product_name": getattr(bom, "display_name", None) or "Unnamed BOM",
            }
            for bom in boms
            if getattr(bom, "product_template_id", None) is not None and getattr(bom, "active", True) is True and getattr(bom, "type", None) == "normal"
        ]

    params = request.query_params
    if params.get("parent_product"):
        selected_product_id = int(params["parent_product"])
    if params.get("quantity"):
        try:
            quantity_to_produce = float(params["quantity"])
        except ValueError:
            quantity_to_produce = 1.0

    if connected and parent_options:
        if selected_product_id is None:
            selected_product_id = parent_options[0]["id"]
        engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
        shortage_rows = engine.build_plan(selected_product_id, quantity=quantity_to_produce, product_template_id=selected_product_id) if selected_product_id is not None else []

    context = {
        "request": request,
        "connected": connected,
        "parent_options": parent_options,
        "selected_product_id": selected_product_id,
        "quantity_to_produce": quantity_to_produce,
        "shortage_rows": shortage_rows,
    }
    if templates is None:
        return HTMLResponse(content="<html><body><h1>Shortages</h1><p>Template rendering is unavailable in this environment.</p></body></html>")
    return templates.TemplateResponse(request, "shortages.html", context)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    client = OdooClient()
    connected = client.connect()
    products = client.get_products() if connected else []
    inventory = client.get_inventory() if connected else []
    manufacturing_orders = client.get_manufacturing_orders() if connected else []
    purchase_orders = client.get_purchase_orders() if connected else []

    inventory_summary = {
        "total_items": len(inventory),
        "total_quantity": round(sum(item.get("quantity", 0) for item in inventory), 2),
        "status": "Connected" if connected else "Offline",
    }

    context = {
        "request": request,
        "connected": connected,
        "inventory_summary": inventory_summary,
        "products": products,
        "manufacturing_orders": manufacturing_orders,
        "purchase_orders": purchase_orders,
        "open_sales_orders": [{"id": "placeholder", "name": "Pending sales sync", "state": "placeholder"}],
    }
    if templates is None:
        html = """
        <html>
            <body>
                <h1>Atlas Dashboard</h1>
                <p>Template rendering is unavailable in this environment.</p>
            </body>
        </html>
        """
        return HTMLResponse(content=html)
    return templates.TemplateResponse(request, "dashboard.html", context)
