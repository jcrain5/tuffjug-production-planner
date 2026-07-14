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
            normalized[key] = cls._normalize_value(key, value)
        return cls(**normalized)

    @staticmethod
    def _normalize_value(key: str, value: Any) -> Any:
        if isinstance(value, (list, tuple)) and value:
            if isinstance(value[0], (list, tuple)):
                return value[0][0]
            if isinstance(value[0], dict):
                return value[0].get("id")
            return value[0]
        if value is False:
            return None
        return value

    @classmethod
    def _normalize_many2one(cls, value: Any) -> dict[str, Any] | None:
        if value is False or value is None:
            return None
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return {"id": value[0], "name": value[1]}
        if isinstance(value, dict):
            return {"id": value.get("id"), "name": value.get("name")}
        return {"id": value, "name": None}

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ProductModel(AtlasBaseModel):
    name: str | None = None
    default_code: str | None = None
    list_price: float | None = None
    product_tmpl_id: int | None = None
    purchase_ok: bool | None = None

    @classmethod
    def from_odoo_record(cls, record: dict[str, Any]) -> "ProductModel":
        normalized: dict[str, Any] = {}
        for key, value in record.items():
            if key == "product_tmpl_id":
                many2one = cls._normalize_many2one(value)
                normalized["product_tmpl_id"] = many2one.get("id") if many2one else None
                continue
            normalized[key] = cls._normalize_value(key, value)
        return cls(**normalized)


class BomModel(AtlasBaseModel):
    display_name: str | None = None
    code: str | None = None
    active: bool | None = None
    type: str | None = None
    product_id: int | None = None
    product_template_id: int | None = None
    product_template_name: str | None = None
    product_variant_id: int | None = None
    product_variant_name: str | None = None
    product_qty: float | None = None
    uom_id: int | None = None
    uom_name: str | None = None

    @classmethod
    def from_odoo_record(cls, record: dict[str, Any]) -> "BomModel":
        normalized: dict[str, Any] = {}
        for key, value in record.items():
            if key in {"product_tmpl_id", "uom_id", "company_id"}:
                many2one = cls._normalize_many2one(value)
                if key == "product_tmpl_id":
                    normalized["product_template_id"] = many2one.get("id") if many2one else None
                    normalized["product_template_name"] = many2one.get("name") if many2one else None
                elif key == "uom_id":
                    normalized["uom_id"] = many2one.get("id") if many2one else None
                    normalized["uom_name"] = many2one.get("name") if many2one else None
                continue
            if key == "product_id":
                many2one = cls._normalize_many2one(value)
                normalized["product_id"] = many2one.get("id") if many2one else None
                normalized["product_variant_id"] = many2one.get("id") if many2one else None
                normalized["product_variant_name"] = many2one.get("name") if many2one else None
                continue
            normalized[key] = cls._normalize_value(key, value)

        for key in ("display_name", "code", "active", "type", "product_qty"):
            if key not in normalized:
                normalized[key] = None

        return cls(**normalized)


class BomComponentModel(AtlasBaseModel):
    bom_id: int | None = None
    product_id: int | None = None
    product_id_name: str | None = None
    product_qty: float | None = None

    @classmethod
    def from_odoo_record(cls, record: dict[str, Any]) -> "BomComponentModel":
        normalized: dict[str, Any] = {}
        for key, value in record.items():
            if key == "product_id":
                many2one = cls._normalize_many2one(value)
                normalized["product_id"] = many2one.get("id") if many2one else None
                normalized["product_id_name"] = many2one.get("name") if many2one else None
                continue
            if key == "bom_id":
                many2one = cls._normalize_many2one(value)
                normalized["bom_id"] = many2one.get("id") if many2one else None
                continue
            normalized[key] = cls._normalize_value(key, value)

        return cls(**normalized)


class InventoryItemModel(AtlasBaseModel):
    product_id: int | None = None
    quantity: float | None = None
    reserved_quantity: float | None = None
    location_id: int | None = None


class ManufacturingOrderModel(AtlasBaseModel):
    name: str | None = None
    state: str | None = None
    product_id: int | None = None
    product_qty: float | None = None
    bom_id: int | None = None


class PurchaseOrderModel(AtlasBaseModel):
    name: str | None = None
    state: str | None = None
    partner_id: int | None = None
    date_order: str | None = None


class PurchaseOrderLineModel(AtlasBaseModel):
    order_id: int | None = None
    product_id: int | None = None
    product_qty: float | None = None


class ReorderingRuleModel(AtlasBaseModel):
    product_id: int | None = None
    product_min_qty: float | None = None
