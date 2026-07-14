from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app.config import Settings
from app.integrations.shopify import ShopifyClient, ShopifyTokenError


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.content = b"{}"

    def json(self):
        return self._json_data


class FakeHTTPClient:
    def __init__(self, responses, calls):
        self._responses = responses
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None, data=None):
        self._calls.append({"url": url, "headers": headers or {}, "json": json, "data": data})
        if not self._responses:
            raise AssertionError("No fake HTTP responses left")
        return self._responses.pop(0)


def _build_client():
    return ShopifyClient(
        config=Settings(
            shopify_store="8b5c56-36.myshopify.com",
            shopify_client_id="client-id",
            shopify_client_secret="client-secret",
            shopify_api_version="2024-10",
        )
    )


def test_successful_token_acquisition(monkeypatch):
    ShopifyClient._token_cache.clear()
    client = _build_client()
    calls = []
    responses = [
        FakeResponse(
            200,
            {
                "access_token": "token-1",
                "scope": "read_orders",
                "expires_in": 3600,
            },
        )
    ]

    monkeypatch.setattr("app.integrations.shopify.httpx.Client", lambda timeout=30.0: FakeHTTPClient(responses, calls))

    token = client._get_access_token()

    assert token.access_token == "token-1"
    assert token.scopes == ["read_orders"]
    assert token.expires_in == 3600
    assert len(calls) == 1
    assert calls[0]["data"]["grant_type"] == "client_credentials"


def test_cached_token_reuse(monkeypatch):
    ShopifyClient._token_cache.clear()
    client = _build_client()
    calls = []
    responses = [
        FakeResponse(200, {"access_token": "token-1", "scope": "read_orders", "expires_in": 3600})
    ]

    monkeypatch.setattr("app.integrations.shopify.httpx.Client", lambda timeout=30.0: FakeHTTPClient(responses, calls))

    first = client._get_access_token()
    second = client._get_access_token()

    assert first.access_token == second.access_token
    assert len(calls) == 1


def test_automatic_refresh_before_expiration(monkeypatch):
    ShopifyClient._token_cache.clear()
    client = _build_client()
    key = client._cache_key()
    client._token_cache[key] = type("T", (), {
        "access_token": "stale",
        "scopes": ["read_orders"],
        "expires_in": 3600,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=200),
    })()

    calls = []
    responses = [
        FakeResponse(200, {"access_token": "fresh", "scope": "read_orders", "expires_in": 3600})
    ]
    monkeypatch.setattr("app.integrations.shopify.httpx.Client", lambda timeout=30.0: FakeHTTPClient(responses, calls))

    token = client._get_access_token()

    assert token.access_token == "fresh"
    assert len(calls) == 1


def test_refresh_after_authentication_failure(monkeypatch):
    ShopifyClient._token_cache.clear()
    client = _build_client()

    token_responses = [
        FakeResponse(200, {"access_token": "old-token", "scope": "read_orders", "expires_in": 3600}),
        FakeResponse(200, {"access_token": "new-token", "scope": "read_orders", "expires_in": 3600}),
    ]
    graphql_responses = [
        FakeResponse(401, {"errors": [{"message": "Invalid API key or access token"}]}),
        FakeResponse(200, {"data": {"shop": {"id": "gid://shopify/Shop/1"}}}),
    ]

    calls = []

    def fake_client(timeout=30.0):
        if token_responses:
            # token request occurs when data payload is provided
            return FakeHTTPClient(token_responses, calls)
        return FakeHTTPClient(graphql_responses, calls)

    # Route calls by URL within a single fake client factory
    def fake_client_router(timeout=30.0):
        class Router(FakeHTTPClient):
            def post(self_inner, url, headers=None, json=None, data=None):
                if url.endswith("/admin/oauth/access_token"):
                    return FakeHTTPClient(token_responses, calls).post(url, headers=headers, json=json, data=data)
                return FakeHTTPClient(graphql_responses, calls).post(url, headers=headers, json=json, data=data)

        return Router([], calls)

    monkeypatch.setattr("app.integrations.shopify.httpx.Client", fake_client_router)

    data = client._graphql("query { shop { id } }")

    assert data["shop"]["id"] == "gid://shopify/Shop/1"


def test_token_endpoint_error(monkeypatch):
    ShopifyClient._token_cache.clear()
    client = _build_client()
    calls = []
    responses = [FakeResponse(401, {"error": "invalid_client"})]

    monkeypatch.setattr("app.integrations.shopify.httpx.Client", lambda timeout=30.0: FakeHTTPClient(responses, calls))

    with pytest.raises(ShopifyTokenError):
        client._get_access_token()


def test_no_credential_leakage_in_status_error(monkeypatch):
    ShopifyClient._token_cache.clear()
    client = _build_client()

    monkeypatch.setattr(client, "_request_access_token", lambda: (_ for _ in ()).throw(ShopifyTokenError("Token endpoint failure")))

    status = client.status()

    text = str(status)
    assert "client-secret" not in text
    assert "token" not in text.lower() or "token_expiration_time" in text


def test_shopify_orders_pagination(monkeypatch):
    client = _build_client()

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


def test_shopify_demand_by_sku_aggregates_net_units(monkeypatch):
    client = _build_client()

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
