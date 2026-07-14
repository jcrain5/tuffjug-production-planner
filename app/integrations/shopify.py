from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from ..config import Settings, get_settings


class ShopifyClient:
    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or get_settings()

    def _normalize_store(self) -> str:
        store = (self.config.shopify_store or "").strip()
        store = store.replace("https://", "").replace("http://", "")
        store = store.strip("/")
        if not store:
            return ""
        if "." not in store:
            return f"{store}.myshopify.com"
        return store

    def _graphql_url(self) -> str:
        store = self._normalize_store()
        return f"https://{store}/admin/api/{self.config.shopify_api_version}/graphql.json"

    def _is_configured(self) -> bool:
        return bool((self.config.shopify_store or "").strip() and (self.config.shopify_access_token or "").strip())

    def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._is_configured():
            raise RuntimeError("Shopify is not configured")

        headers = {
            "X-Shopify-Access-Token": self.config.shopify_access_token,
            "Content-Type": "application/json",
        }
        payload = {"query": query, "variables": variables or {}}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self._graphql_url(), headers=headers, json=payload)

        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError("Shopify GraphQL query failed")
        return data.get("data", {})

    @staticmethod
    def _format_date(value: date | datetime | str) -> str:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, date):
            dt = datetime(value.year, value.month, value.day)
        elif isinstance(value, str):
            return value
        else:
            raise ValueError("Unsupported date value")
        return dt.isoformat() + "Z"

    def status(self) -> dict[str, Any]:
        if not self._is_configured():
            return {"connected": False, "configured": False}
        try:
            data = self._graphql("query { shop { id name } }")
            return {"connected": bool(data.get("shop")), "configured": True}
        except Exception:
            return {"connected": False, "configured": True}

    @staticmethod
    def _refunded_quantity(line_node: dict[str, Any]) -> float:
        quantity = float(line_node.get("quantity") or 0)
        current_quantity = line_node.get("currentQuantity")
        if current_quantity is None:
            return 0.0
        refunded = quantity - float(current_quantity)
        return refunded if refunded > 0 else 0.0

    @staticmethod
    def _line_exclusion_flags(order_node: dict[str, Any], line_node: dict[str, Any], refunded_quantity: float) -> dict[str, bool]:
        quantity = float(line_node.get("quantity") or 0)
        cancelled = order_node.get("cancelledAt") is not None
        test_order = bool(order_node.get("test") or False)
        source_name = (order_node.get("sourceName") or "").lower()
        draft_order = "draft" in source_name
        gift_card = bool(line_node.get("isGiftCard") or False)
        missing_sku = not bool((line_node.get("sku") or "").strip())
        fully_refunded = quantity > 0 and refunded_quantity >= quantity
        return {
            "is_cancelled_order": cancelled,
            "is_test_order": test_order,
            "is_draft_order": draft_order,
            "is_gift_card": gift_card,
            "is_missing_sku": missing_sku,
            "is_fully_refunded": fully_refunded,
        }

    @staticmethod
    def _is_excluded(flags: dict[str, bool]) -> bool:
        return any(flags.values())

    def _fetch_line_items_for_order(self, order_id: str, first_page_edges: list[dict[str, Any]] | None = None, has_next_page: bool = False, end_cursor: str | None = None) -> list[dict[str, Any]]:
        all_edges = list(first_page_edges or [])
        cursor = end_cursor
        next_page = has_next_page

        query = """
        query OrderLineItems($id: ID!, $after: String) {
          order(id: $id) {
            lineItems(first: 250, after: $after) {
              edges {
                cursor
                node {
                  id
                  sku
                  name
                  quantity
                  currentQuantity
                  isGiftCard
                }
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
          }
        }
        """

        while next_page:
            data = self._graphql(query, {"id": order_id, "after": cursor})
            line_items = data.get("order", {}).get("lineItems", {})
            edges = line_items.get("edges", [])
            all_edges.extend(edges)
            page_info = line_items.get("pageInfo", {})
            next_page = bool(page_info.get("hasNextPage"))
            cursor = page_info.get("endCursor")

        return all_edges

    def get_order_lines(self, start_date: date | datetime | str, end_date: date | datetime | str, include_excluded: bool = False) -> list[dict[str, Any]]:
        start_text = self._format_date(start_date)
        end_text = self._format_date(end_date)

        query = """
        query OrdersPage($query: String!, $after: String) {
          orders(first: 100, query: $query, after: $after, sortKey: CREATED_AT) {
            edges {
              cursor
              node {
                id
                name
                createdAt
                displayFinancialStatus
                displayFulfillmentStatus
                cancelledAt
                test
                sourceName
                lineItems(first: 250) {
                  edges {
                    cursor
                    node {
                      id
                      sku
                      name
                      quantity
                      currentQuantity
                      isGiftCard
                    }
                  }
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """

        after: str | None = None
        has_next_page = True
        rows: list[dict[str, Any]] = []
        order_query = f"created_at:>={start_text} created_at:<={end_text}"

        while has_next_page:
            data = self._graphql(query, {"query": order_query, "after": after})
            orders = data.get("orders", {})
            for edge in orders.get("edges", []):
                order_node = edge.get("node", {})
                line_items = order_node.get("lineItems", {})
                edges = self._fetch_line_items_for_order(
                    order_id=str(order_node.get("id")),
                    first_page_edges=line_items.get("edges", []),
                    has_next_page=bool(line_items.get("pageInfo", {}).get("hasNextPage")),
                    end_cursor=line_items.get("pageInfo", {}).get("endCursor"),
                )

                for line_edge in edges:
                    line_node = line_edge.get("node", {})
                    quantity = float(line_node.get("quantity") or 0)
                    refunded_quantity = self._refunded_quantity(line_node)
                    net_quantity = quantity - refunded_quantity
                    flags = self._line_exclusion_flags(order_node, line_node, refunded_quantity)
                    excluded = self._is_excluded(flags)
                    row = {
                        "shopify_order_id": order_node.get("id"),
                        "order_number": order_node.get("name"),
                        "created_at": order_node.get("createdAt"),
                        "financial_status": order_node.get("displayFinancialStatus"),
                        "fulfillment_status": order_node.get("displayFulfillmentStatus"),
                        "sku": line_node.get("sku"),
                        "line_item_name": line_node.get("name"),
                        "quantity": quantity,
                        "refunded_quantity": refunded_quantity,
                        "net_quantity": net_quantity,
                        "cancelled_status": flags["is_cancelled_order"],
                        "is_cancelled_order": flags["is_cancelled_order"],
                        "is_test_order": flags["is_test_order"],
                        "is_draft_order": flags["is_draft_order"],
                        "is_gift_card": flags["is_gift_card"],
                        "is_missing_sku": flags["is_missing_sku"],
                        "is_fully_refunded": flags["is_fully_refunded"],
                        "is_excluded": excluded,
                    }
                    if include_excluded or not excluded:
                        rows.append(row)

            page_info = orders.get("pageInfo", {})
            has_next_page = bool(page_info.get("hasNextPage"))
            after = page_info.get("endCursor")

        return rows

    def get_demand_by_sku(self, start_date: date | datetime | str, end_date: date | datetime | str) -> list[dict[str, Any]]:
        lines = self.get_order_lines(start_date=start_date, end_date=end_date, include_excluded=False)
        grouped: dict[str, dict[str, Any]] = {}

        for row in lines:
            sku = (row.get("sku") or "").strip()
            if not sku:
                continue

            created_at = row.get("created_at")
            existing = grouped.get(sku)
            if existing is None:
                grouped[sku] = {
                    "sku": sku,
                    "product_name": row.get("line_item_name"),
                    "units_ordered": float(row.get("quantity") or 0),
                    "units_refunded": float(row.get("refunded_quantity") or 0),
                    "net_units": float(row.get("net_quantity") or 0),
                    "order_ids": {row.get("shopify_order_id")},
                    "first_order_date": created_at,
                    "last_order_date": created_at,
                }
                continue

            existing["units_ordered"] += float(row.get("quantity") or 0)
            existing["units_refunded"] += float(row.get("refunded_quantity") or 0)
            existing["net_units"] += float(row.get("net_quantity") or 0)
            existing["order_ids"].add(row.get("shopify_order_id"))
            if created_at and (existing["first_order_date"] is None or created_at < existing["first_order_date"]):
                existing["first_order_date"] = created_at
            if created_at and (existing["last_order_date"] is None or created_at > existing["last_order_date"]):
                existing["last_order_date"] = created_at

        output: list[dict[str, Any]] = []
        for _, item in grouped.items():
            output.append(
                {
                    "sku": item["sku"],
                    "product_name": item["product_name"],
                    "units_ordered": item["units_ordered"],
                    "units_refunded": item["units_refunded"],
                    "net_units": item["net_units"],
                    "order_count": len(item["order_ids"]),
                    "first_order_date": item["first_order_date"],
                    "last_order_date": item["last_order_date"],
                }
            )
        output.sort(key=lambda row: row["sku"])
        return output

    def ping(self) -> str:
        return "Shopify client ready"
