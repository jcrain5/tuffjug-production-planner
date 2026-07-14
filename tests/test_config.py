from app.config import Settings, get_settings


def test_settings_loads_environment_values(monkeypatch):
    monkeypatch.setenv("ODOO_URL", "https://odoo.example")
    monkeypatch.setenv("ODOO_DATABASE", "atlas_db")
    monkeypatch.setenv("ODOO_USERNAME", "atlas_user")
    monkeypatch.setenv("ODOO_API_KEY", "secret")
    monkeypatch.setenv("SHOPIFY_STORE", "store-1")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "token")
    monkeypatch.setenv("SHOPIFY_API_VERSION", "2025-01")

    settings = Settings()

    assert settings.odoo_url == "https://odoo.example"
    assert settings.odoo_database == "atlas_db"
    assert settings.odoo_username == "atlas_user"
    assert settings.odoo_api_key == "secret"
    assert settings.shopify_store == "store-1"
    assert settings.shopify_access_token == "token"
    assert settings.shopify_api_version == "2025-01"


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("ODOO_URL", "https://cached.example")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.odoo_url == "https://cached.example"
