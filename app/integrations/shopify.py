from __future__ import annotations

from ..config import Settings, get_settings


class ShopifyClient:
    def __init__(self, config: Settings | None = None) -> None:
        self.config = config or get_settings()

    def ping(self) -> str:
        return "Shopify client ready"
