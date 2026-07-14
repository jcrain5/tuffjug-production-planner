from app.models.odoo import BomComponentModel, BomModel, InventoryItemModel, ProductModel
from app.planning.replenishment import ShortagePlanningEngine, build_shortage_plan


def test_shortage_engine_builds_purchase_plan_for_short_components():
    products = [
        ProductModel(id=10, name="Finished Product"),
        ProductModel(id=20, name="Raw Material A"),
        ProductModel(id=30, name="Subassembly"),
        ProductModel(id=40, name="Raw Material B"),
    ]
    boms = [
        BomModel(id=1, product_id=10, name="Finished BOM"),
        BomModel(id=2, product_id=30, name="Subassembly BOM"),
    ]
    components = [
        BomComponentModel(id=100, bom_id=1, product_id=20, product_qty=2.0),
        BomComponentModel(id=101, bom_id=1, product_id=30, product_qty=1.0),
        BomComponentModel(id=102, bom_id=2, product_id=40, product_qty=3.0),
    ]
    inventory = [
        InventoryItemModel(id=1, product_id=20, quantity=1.0),
        InventoryItemModel(id=2, product_id=30, quantity=1.0),
        InventoryItemModel(id=3, product_id=40, quantity=10.0),
    ]

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(10, quantity=2.0)

    assert plan[0]["quantity_required"] == 4.0
    assert plan[0]["quantity_available"] == 1.0
    assert plan[0]["quantity_short"] == 3.0
    assert plan[0]["recommended_action"] == "Purchase"


def test_shortage_helper_wraps_engine():
    plan = build_shortage_plan(
        10,
        quantity=1.0,
        boms=[BomModel(id=1, product_id=10, name="Finished BOM")],
        components=[BomComponentModel(id=100, bom_id=1, product_id=20, product_qty=2.0)],
        products=[ProductModel(id=10, name="Finished Product"), ProductModel(id=20, name="Raw Material A")],
        inventory=[InventoryItemModel(id=1, product_id=20, quantity=5.0)],
    )

    assert plan[0]["recommended_action"] == "Available"
    assert plan[0]["quantity_short"] == 0.0
