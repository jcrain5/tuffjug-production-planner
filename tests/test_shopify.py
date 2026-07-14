from datetime import date

from app.config import Settings
from app.integrations.shopify import ShopifyClient


def test_shopify_status_successful_authentication(monkeypatch):
    client = ShopifyClient(
        config=Settings(
            shopify_store="atlas-store",
            shopify_access_token="secret",
            shopify_api_version="2024-10",
        )
    )

    def fake_graphql(query, variables=None):
        return {"shop": {"id": "gid://shopify/Shop/1", "name": "Atlas"}}

    monkeypatch.setattr(client, "_graphql", fake_graphql)

    status = client.status()

    assert status["configured"] is True
    assert status["connected"] is True


def test_shopify_orders_pagination(monkeypatch):
    client = ShopifyClient(config=Settings(shopify_store="atlas-store", shopify_access_token="secret"))

    responses = [
        {
            "orders": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Order/1",
                            "name": "#1001",
                            "createdAt": "2026-01-01T00:00:00Z",
                            "displayFinancialStatus": "PAID",
                            "displayFulfillmentStatus": "UNFULFILLED",
                            "cancelledAt": None,
                            "test": False,
                            "sourceName": "web",
                            "lineItems": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "gid://shopify/LineItem/1",
                                            "sku": "SKU-A",
                                            "name": "Item A",
                                            "quantity": 1,
                                            "currentQuantity": 1,
                                            "isGiftCard": False,
                                        }
                                    }
                                ],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            },
                        }
                    }
                ],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
            }
        },
        {
            "orders": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Order/2",
                            "name": "#1002",
                            "createdAt": "2026-01-02T00:00:00Z",
                            "displayFinancialStatus": "PAID",
                            "displayFulfillmentStatus": "UNFULFILLED",
                            "cancelledAt": None,
                            "test": False,
                            "sourceName": "web",
                            "lineItems": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "gid://shopify/LineItem/2",
                                            "sku": "SKU-B",
                                            "name": "Item B",
                                            "quantity": 2,
                                            "currentQuantity": 2,
                                            "isGiftCard": False,
                                        }
                                    }
                                ],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            },
                        }
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        },
    ]

    state = {"idx": 0}

    def fake_graphql(query, variables=None):
        idx = state["idx"]
        state["idx"] += 1
        return responses[idx]

    monkeypatch.setattr(client, "_graphql", fake_graphql)

    rows = client.get_order_lines(start_date="2026-01-01", end_date="2026-01-31")

    assert len(rows) == 2
    assert rows[0]["order_number"] == "#1001"
    assert rows[1]["order_number"] == "#1002"


def test_shopify_orders_exclusions_cancelled_refunded_missing_sku(monkeypatch):
    client = ShopifyClient(config=Settings(shopify_store="atlas-store", shopify_access_token="secret"))

    payload = {
        "orders": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/Order/1",
                        "name": "#1001",
                        "createdAt": "2026-01-01T00:00:00Z",
                        "displayFinancialStatus": "REFUNDED",
                        "displayFulfillmentStatus": "UNFULFILLED",
                        "cancelledAt": "2026-01-03T00:00:00Z",
                        "test": False,
                        "sourceName": "web",
                        "lineItems": {
                            "edges": [
                                {
                                    "node": {
                                        "id": "gid://shopify/LineItem/1",
                                        "sku": "",
                                        "name": "No SKU",
                                        "quantity": 2,
                                        "currentQuantity": 0,
                                        "isGiftCard": False,
                                    }
                                }
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        },
                    }
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }

    monkeypatch.setattr(client, "_graphql", lambda query, variables=None: payload)

    included_rows = client.get_order_lines(start_date="2026-01-01", end_date="2026-01-31", include_excluded=False)
    excluded_rows = client.get_order_lines(start_date="2026-01-01", end_date="2026-01-31", include_excluded=True)

    assert included_rows == []
    assert len(excluded_rows) == 1
    assert excluded_rows[0]["is_cancelled_order"] is True
    assert excluded_rows[0]["is_missing_sku"] is True
    assert excluded_rows[0]["is_fully_refunded"] is True


def test_shopify_demand_by_sku_aggregates_net_units(monkeypatch):
    client = ShopifyClient(config=Settings(shopify_store="atlas-store", shopify_access_token="secret"))

    rows = [
        {
            "shopify_order_id": "gid://shopify/Order/1",
            "order_number": "#1001",
            "created_at": "2026-01-01T00:00:00Z",
            "financial_status": "PAID",
            "fulfillment_status": "UNFULFILLED",
            "sku": "SKU-A",
            "line_item_name": "Item A",
            "quantity": 3.0,
            "refunded_quantity": 1.0,
            "net_quantity": 2.0,
            "cancelled_status": False,
            "is_cancelled_order": False,
            "is_test_order": False,
            "is_draft_order": False,
            "is_gift_card": False,
            "is_missing_sku": False,
            "is_fully_refunded": False,
            "is_excluded": False,
        },
        {
            "shopify_order_id": "gid://shopify/Order/2",
            "order_number": "#1002",
            "created_at": "2026-01-05T00:00:00Z",
            "financial_status": "PAID",
            "fulfillment_status": "UNFULFILLED",
            "sku": "SKU-A",
            "line_item_name": "Item A",
            "quantity": 1.0,
            "refunded_quantity": 0.0,
            "net_quantity": 1.0,
            "cancelled_status": False,
            "is_cancelled_order": False,
            "is_test_order": False,
            "is_draft_order": False,
            "is_gift_card": False,
            "is_missing_sku": False,
            "is_fully_refunded": False,
            "is_excluded": False,
        },
    ]

    monkeypatch.setattr(client, "get_order_lines", lambda start_date, end_date, include_excluded=False: rows)

    demand = client.get_demand_by_sku(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))

    assert len(demand) == 1
    assert demand[0]["sku"] == "SKU-A"
    assert demand[0]["units_ordered"] == 4.0
    assert demand[0]["units_refunded"] == 1.0
    assert demand[0]["net_units"] == 3.0
    assert demand[0]["order_count"] == 2
    assert demand[0]["first_order_date"] == "2026-01-01T00:00:00Z"
    assert demand[0]["last_order_date"] == "2026-01-05T00:00:00Z"
