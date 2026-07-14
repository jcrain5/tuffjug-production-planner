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

## Endpoints

- GET /health returns a simple health payload
- GET /odoo/status returns whether Atlas could authenticate with Odoo

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```
