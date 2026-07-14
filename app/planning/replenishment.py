from __future__ import annotations

from typing import Any

from ..models.odoo import BomComponentModel, BomModel, InventoryItemModel, ProductModel
from .bom import BOMExplosionEngine


class ShortagePlanningEngine:
    def __init__(self, boms: list[BomModel], components: list[BomComponentModel], products: list[ProductModel], inventory: list[InventoryItemModel]) -> None:
        self.boms = boms
        self.components = components
        self.products = products
        self.inventory = inventory
        self.explosion_engine = BOMExplosionEngine(boms=boms, components=components, products=products)
        self.inventory_lookup = {
            item.product_id: item for item in inventory if getattr(item, "product_id", None) is not None
        }

    def build_plan(self, product_id: int, quantity: float = 1.0) -> list[dict[str, Any]]:
        exploded = self.explosion_engine.explode(product_id, quantity=quantity)
        plan: list[dict[str, Any]] = []
        for item in exploded:
            component_id = item["product_id"]
            required_quantity = float(item["quantity"])
            inventory_item = self.inventory_lookup.get(component_id)
            available_quantity = float(getattr(inventory_item, "quantity", 0) or 0)
            short_quantity = max(required_quantity - available_quantity, 0.0)

            if short_quantity <= 0:
                action = "Available"
            else:
                action = "Purchase"

            plan.append(
                {
                    "product": item["product_name"],
                    "quantity_required": required_quantity,
                    "quantity_available": available_quantity,
                    "quantity_short": short_quantity,
                    "recommended_action": action,
                }
            )

        return plan


def build_shortage_plan(product_id: int, quantity: float = 1.0, boms: list[BomModel] | None = None, components: list[BomComponentModel] | None = None, products: list[ProductModel] | None = None, inventory: list[InventoryItemModel] | None = None) -> list[dict[str, Any]]:
    engine = ShortagePlanningEngine(
        boms=boms or [],
        components=components or [],
        products=products or [],
        inventory=inventory or [],
    )
    return engine.build_plan(product_id=product_id, quantity=quantity)
