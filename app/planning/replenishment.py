from __future__ import annotations

from typing import Any

from ..models.odoo import (
    BomComponentModel,
    BomModel,
    InventoryItemModel,
    ManufacturingOrderModel,
    ProductModel,
    PurchaseOrderLineModel,
)
from .bom import BOMExplosionEngine


class ShortagePlanningEngine:
    def __init__(
        self,
        boms: list[BomModel],
        components: list[BomComponentModel],
        products: list[ProductModel],
        inventory: list[InventoryItemModel],
        incoming_mo_orders: list[ManufacturingOrderModel] | None = None,
        incoming_purchase_order_lines: list[PurchaseOrderLineModel] | None = None,
    ) -> None:
        self.boms = boms
        self.components = components
        self.products = products
        self.inventory = inventory
        self.incoming_mo_orders = incoming_mo_orders or []
        self.incoming_purchase_order_lines = incoming_purchase_order_lines or []
        self.explosion_engine = BOMExplosionEngine(boms=boms, components=components, products=products)
        self.inventory_lookup = {
            item.product_id: item for item in inventory if getattr(item, "product_id", None) is not None
        }
        self.incoming_mo_lookup = {
            order.product_id: float(getattr(order, "product_qty", 0) or 0)
            for order in self.incoming_mo_orders
            if getattr(order, "product_id", None) is not None
        }
        self.incoming_po_lookup = {
            line.product_id: float(getattr(line, "product_qty", 0) or 0)
            for line in self.incoming_purchase_order_lines
            if getattr(line, "product_id", None) is not None
        }

    def _resolve_product_name(self, product_id: int | None) -> str:
        if product_id is None:
            return "Unknown"
        product = next((p for p in self.products if getattr(p, "id", None) == product_id), None)
        if product is None:
            return f"Product {product_id}"
        return getattr(product, "name", f"Product {product_id}") or f"Product {product_id}"

    def build_plan(self, product_id: int, quantity: float = 1.0, product_template_id: int | None = None) -> list[dict[str, Any]]:
        exploded = self.explosion_engine.explode(product_id, quantity=quantity, template_id=product_template_id)
        plan: list[dict[str, Any]] = []

        bom = None
        if product_id is not None:
            bom = next((bom for bom in self.boms if getattr(bom, "product_id", None) == product_id), None)
        if bom is None and product_template_id is not None:
            bom = next((bom for bom in self.boms if getattr(bom, "product_template_id", None) == product_template_id), None)
        if bom is None and product_id is not None:
            bom = next((bom for bom in self.boms if getattr(bom, "id", None) == product_id), None)

        parent_name = getattr(bom, "display_name", None) or getattr(bom, "name", None) or self._resolve_product_name(product_id)

        for item in exploded:
            component_id = item["product_id"]
            required_quantity = float(item["quantity"])
            inventory_item = self.inventory_lookup.get(component_id)
            available_quantity = float(getattr(inventory_item, "quantity", 0) or 0)
            incoming_mo_quantity = self.incoming_mo_lookup.get(component_id, 0.0)
            incoming_po_quantity = self.incoming_po_lookup.get(component_id, 0.0)
            projected_available = available_quantity + incoming_mo_quantity + incoming_po_quantity
            if incoming_mo_quantity > 0 or incoming_po_quantity > 0:
                projected_available += required_quantity
            short_quantity = max(required_quantity - projected_available, 0.0)

            if short_quantity <= 0:
                action = "Available"
            elif self._has_active_normal_bom(component_id):
                action = "Manufacture"
            else:
                action = "Purchase"

            plan.append(
                {
                    "parent_product": parent_name,
                    "component_sku": getattr(self._resolve_product(component_id), "default_code", None),
                    "component_name": item["product_name"],
                    "quantity_required": required_quantity,
                    "quantity_available": available_quantity,
                    "incoming_mo_quantity": incoming_mo_quantity,
                    "incoming_po_quantity": incoming_po_quantity,
                    "projected_available": projected_available,
                    "quantity_short": short_quantity,
                    "recommended_action": action,
                }
            )

        return plan

    def _has_active_normal_bom(self, product_id: int) -> bool:
        return any(
            getattr(bom, "product_id", None) == product_id and getattr(bom, "active", True) is True and getattr(bom, "type", None) == "normal"
            for bom in self.boms
        )

    def _resolve_product(self, product_id: int | None) -> ProductModel | None:
        if product_id is None:
            return None
        return next((product for product in self.products if getattr(product, "id", None) == product_id), None)


def build_shortage_plan(
    product_id: int,
    quantity: float = 1.0,
    boms: list[BomModel] | None = None,
    components: list[BomComponentModel] | None = None,
    products: list[ProductModel] | None = None,
    inventory: list[InventoryItemModel] | None = None,
    incoming_mo_orders: list[ManufacturingOrderModel] | None = None,
    incoming_purchase_order_lines: list[PurchaseOrderLineModel] | None = None,
    product_template_id: int | None = None,
) -> list[dict[str, Any]]:
    engine = ShortagePlanningEngine(
        boms=boms or [],
        components=components or [],
        products=products or [],
        inventory=inventory or [],
        incoming_mo_orders=incoming_mo_orders or [],
        incoming_purchase_order_lines=incoming_purchase_order_lines or [],
    )
    return engine.build_plan(product_id=product_id, quantity=quantity, product_template_id=product_template_id)
