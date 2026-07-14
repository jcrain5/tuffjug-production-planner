from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..models.odoo import BomComponentModel, BomModel, ProductModel


class BOMExplosionEngine:
    def __init__(self, boms: list[BomModel], components: list[BomComponentModel], products: list[ProductModel]) -> None:
        self.boms = boms
        self.components = components
        self.products = products
        self.product_lookup = {product.id: product for product in products if getattr(product, "id", None) is not None}
        self.bom_lookup = {getattr(bom, "product_id", None): bom for bom in boms if getattr(bom, "product_id", None) is not None}
        self.template_bom_lookup = {
            getattr(bom, "product_template_id", None): bom
            for bom in boms
            if getattr(bom, "product_template_id", None) is not None
        }
        self.components_by_bom: dict[int, list[BomComponentModel]] = defaultdict(list)
        for component in components:
            bom_id = getattr(component, "bom_id", None)
            if bom_id is not None:
                self.components_by_bom[bom_id].append(component)

    def _resolve_bom(self, product_id: int | None, template_id: int | None) -> BomModel | None:
        if product_id is not None:
            bom = self.bom_lookup.get(product_id)
            if bom is not None:
                return bom
        if template_id is not None:
            return self.template_bom_lookup.get(template_id)
        return None

    def explode(self, product_id: int, quantity: float = 1.0, visited: set[int] | None = None, template_id: int | None = None) -> list[dict[str, Any]]:
        if quantity <= 0:
            return []

        visited = visited or set()
        if product_id in visited:
            return []

        bom = self._resolve_bom(product_id, template_id)
        if bom is None:
            return []

        exploded: list[dict[str, Any]] = []
        child_components = self.components_by_bom.get(getattr(bom, "id", None), [])
        if not child_components:
            return []

        for component in child_components:
            component_product_id = getattr(component, "product_id", None)
            component_quantity = float(getattr(component, "product_qty", 0) or 0) * quantity
            if component_product_id is None:
                continue

            nested_bom = self._resolve_bom(component_product_id, None)
            if nested_bom is not None:
                nested = self.explode(component_product_id, quantity=component_quantity, visited=visited | {product_id})
                exploded.extend(nested)
            else:
                product_name = self.product_lookup.get(component_product_id).name if component_product_id in self.product_lookup else "Unknown"
                exploded.append(
                    {
                        "product_id": component_product_id,
                        "product_name": product_name,
                        "quantity": component_quantity,
                    }
                )

        return exploded


def explode_bom(product_id: int, quantity: float = 1.0, boms: list[BomModel] | None = None, components: list[BomComponentModel] | None = None, products: list[ProductModel] | None = None, template_id: int | None = None) -> list[dict[str, Any]]:
    engine = BOMExplosionEngine(
        boms=boms or [],
        components=components or [],
        products=products or [],
    )
    return engine.explode(product_id, quantity=quantity, template_id=template_id)


def build_bom() -> dict[str, str]:
    return {"status": "not implemented"}
