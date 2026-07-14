from fastapi import FastAPI

from app.integrations.odoo import OdooClient

app = FastAPI(title="Atlas", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/odoo/status")
def odoo_status() -> dict[str, bool]:
    client = OdooClient()
    return {"connected": client.connect()}
