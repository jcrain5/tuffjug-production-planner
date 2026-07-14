# Atlas

Atlas is a production planning foundation for integrating Odoo manufacturing and purchasing workflows with Shopify demand signals.

## Odoo configuration

Set the following environment variables before running the app:

- ODOO_URL: Base URL for your Odoo instance, for example https://your-company.odoo.com
- ODOO_DATABASE: Odoo database name
- ODOO_USERNAME: Odoo username
- ODOO_API_KEY: Odoo API key or password used for authentication

Example:

```bash
export ODOO_URL="https://your-company.odoo.com"
export ODOO_DATABASE="production"
export ODOO_USERNAME="admin"
export ODOO_API_KEY="your-api-key"
```

## Shopify configuration

Atlas uses Shopify Admin GraphQL in read-only mode and authenticates with client credentials.

Set the following environment variables:

- SHOPIFY_STORE: Shopify store domain, for example 8b5c56-36.myshopify.com
- SHOPIFY_CLIENT_ID: OAuth client ID for your internal app
- SHOPIFY_CLIENT_SECRET: OAuth client secret for your internal app
- SHOPIFY_API_VERSION: Shopify Admin API version, for example 2024-10

Example:

```bash
export SHOPIFY_STORE="8b5c56-36.myshopify.com"
export SHOPIFY_CLIENT_ID="your-client-id"
export SHOPIFY_CLIENT_SECRET="your-client-secret"
export SHOPIFY_API_VERSION="2024-10"
```

## Endpoints

- GET /health returns a simple health payload
- GET /odoo/status returns whether Atlas could authenticate with Odoo
- GET /shopify/status returns Shopify connection details (without secrets)
- GET /shopify/orders returns read-only order-line history for a date range
- GET /shopify/demand-by-sku returns aggregated demand by SKU for a date range

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```
