from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AtlasBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None

    @classmethod
    def from_odoo_record(cls, record: dict[str, Any]) -> "AtlasBaseModel":
        normalized: dict[str, Any] = {}
        for key, value in record.items():
            normalized[key] = cls._normalize_value(value)
        return cls(**normalized)

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, (list, tuple)) and value:
            return value[0]
        return value

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ProductModel(AtlasBaseModel):
    name: str | None = None
    default_code: str | None = None
    list_price: float | None = None


class BomModel(AtlasBaseModel):
    name: str | None = None
    type: str | None = None
    product_id: int | None = None


class BomComponentModel(AtlasBaseModel):
    bom_id: int | None = None
    product_id: int | None = None
    product_qty: float | None = None


class InventoryItemModel(AtlasBaseModel):
    product_id: int | None = None
    quantity: float | None = None
    location_id: int | None = None


class ManufacturingOrderModel(AtlasBaseModel):
    name: str | None = None
    state: str | None = None
    product_id: int | None = None
    bom_id: int | None = None


class PurchaseOrderModel(AtlasBaseModel):
    name: str | None = None
    state: str | None = None
    partner_id: int | None = None
    date_order: str | None = None


class ReorderingRuleModel(AtlasBaseModel):
    product_id: int | None = None
    product_min_qty: float | None = None
