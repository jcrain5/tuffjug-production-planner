from __future__ import annotations

import xmlrpc.client as xmlrpc_client
from typing import Any

from ..config import Settings, get_settings


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

    def get_products(self) -> list[dict[str, Any]]:
        return self._execute("product.product", fields=["id", "name"])

    def get_boms(self) -> list[dict[str, Any]]:
        return self._execute("mrp.bom", fields=["id", "name"])

    def get_bom_components(self) -> list[dict[str, Any]]:
        return self._execute("mrp.bom.line", fields=["id", "product_id", "product_qty"])

    def get_reordering_rules(self) -> list[dict[str, Any]]:
        return self._execute("stock.warehouse.orderpoint", fields=["id", "product_id", "product_min_qty"])

    def get_inventory(self) -> list[dict[str, Any]]:
        return self._execute("stock.quant", fields=["id", "product_id", "quantity"])

    def get_manufacturing_orders(self) -> list[dict[str, Any]]:
        return self._execute("mrp.production", fields=["id", "name", "state"])

    def get_purchase_orders(self) -> list[dict[str, Any]]:
        return self._execute("purchase.order", fields=["id", "name", "state"])

    def ping(self) -> str:
        return "Odoo client ready"
