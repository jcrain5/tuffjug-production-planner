from __future__ import annotations

import xmlrpc.client as xmlrpc_client
from typing import Any

from ..config import Settings, get_settings
from ..models.odoo import (
    BomComponentModel,
    BomModel,
    InventoryItemModel,
    ManufacturingOrderModel,
    ProductModel,
    PurchaseOrderModel,
    ReorderingRuleModel,
)


class OdooClient:
    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or get_settings()
        self.connected = False
        self.uid: int | None = None
        self.common: Any | None = None
        self.models: Any | None = None

    def connect(self) -> bool:
        try:
            self.common = xmlrpc_client.ServerProxy(f"{self.config.odoo_url}/xmlrpc/2/common")
            self.models = xmlrpc_client.ServerProxy(f"{self.config.odoo_url}/xmlrpc/2/object")
            self.uid = self.common.authenticate(
                self.config.odoo_database,
                self.config.odoo_username,
                self.config.odoo_api_key,
                {},
            )
            self.connected = bool(self.uid)
            return self.connected
        except Exception:
            self.connected = False
            self.uid = None
            self.common = None
            self.models = None
            return False

    def _require_connection(self) -> bool:
        if self.connected and self.models is None:
            try:
                self.models = xmlrpc_client.ServerProxy(f"{self.config.odoo_url}/xmlrpc/2/object")
            except Exception:
                return False

        if not self.connected and not self.connect():
            return False
        return True

    def _execute(self, model: str, method: str = "search_read", domain: list[Any] | None = None, fields: list[str] | None = None) -> list[dict[str, Any]]:
        if not self._require_connection():
            return []

        if self.models is None or self.uid is None:
            return []

        args = domain or []
        kwargs: dict[str, Any] = {"fields": fields or []}
        try:
            result = self.models.execute_kw(
                self.config.odoo_database,
                self.uid,
                self.config.odoo_api_key,
                model,
                method,
                [args],
                kwargs,
            )
            if isinstance(result, list):
                return result
            return []
        except Exception:
            return []

    def _map_records(self, records: list[dict[str, Any]], model_cls: type[Any]) -> list[Any]:
        return [model_cls.from_odoo_record(record) for record in records]

    def get_products(self) -> list[ProductModel]:
        records = self._execute("product.product", fields=["id", "name", "default_code", "list_price"])
        return self._map_records(records, ProductModel)

    def get_boms(self) -> list[BomModel]:
        records = self._execute("mrp.bom", fields=["id", "name", "type"])
        return self._map_records(records, BomModel)

    def get_bom_components(self) -> list[BomComponentModel]:
        records = self._execute("mrp.bom.line", fields=["id", "bom_id", "product_id", "product_qty"])
        return self._map_records(records, BomComponentModel)

    def get_reordering_rules(self) -> list[ReorderingRuleModel]:
        records = self._execute("stock.warehouse.orderpoint", fields=["id", "product_id", "product_min_qty"])
        return self._map_records(records, ReorderingRuleModel)

    def get_inventory(self) -> list[InventoryItemModel]:
        records = self._execute("stock.quant", fields=["id", "product_id", "quantity", "location_id"])
        return self._map_records(records, InventoryItemModel)

    def get_manufacturing_orders(self) -> list[ManufacturingOrderModel]:
        records = self._execute("mrp.production", fields=["id", "name", "state", "product_id", "bom_id"])
        return self._map_records(records, ManufacturingOrderModel)

    def get_purchase_orders(self) -> list[PurchaseOrderModel]:
        records = self._execute("purchase.order", fields=["id", "name", "state", "partner_id", "date_order"])
        return self._map_records(records, PurchaseOrderModel)

    def ping(self) -> str:
        return "Odoo client ready"
