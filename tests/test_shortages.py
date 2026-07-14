from app.models.odoo import (
    BomComponentModel,
    BomModel,
    InventoryItemModel,
    ManufacturingOrderModel,
    ProductModel,
    PurchaseOrderLineModel,
)
from app.planning.replenishment import ShortagePlanningEngine, build_shortage_plan


def test_shortage_engine_builds_purchase_plan_for_short_components():
    products = [
        ProductModel(id=10, name="Finished Product"),
        ProductModel(id=20, name="Raw Material A", purchase_ok=True),
        ProductModel(id=30, name="Subassembly"),
        ProductModel(id=40, name="Raw Material B", purchase_ok=True),
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
        products=[ProductModel(id=10, name="Finished Product"), ProductModel(id=20, name="Raw Material A", purchase_ok=True)],
        inventory=[InventoryItemModel(id=1, product_id=20, quantity=5.0)],
    )

    assert plan[0]["recommended_action"] == "Available"
    assert plan[0]["quantity_short"] == 0.0


def test_as20_quantity_5000_reports_spout_base_shortage():
    products = [
        ProductModel(id=100, name="AS20"),
        ProductModel(id=200, name="Spout Base", default_code="SPB-001", purchase_ok=True),
    ]
    boms = [BomModel(id=39, display_name="AS20 Assembly", product_template_id=100, product_id=None)]
    components = [BomComponentModel(id=1, bom_id=39, product_id=200, product_qty=1.0)]
    inventory = [InventoryItemModel(id=1, product_id=200, quantity=100.0)]

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(100, quantity=5000.0, product_template_id=100)

    assert len(plan) == 1
    assert plan[0]["parent_product"] == "AS20 Assembly"
    assert plan[0]["component_sku"] == "SPB-001"
    assert plan[0]["quantity_required"] == 5000.0
    assert plan[0]["quantity_short"] == 4900.0
    assert plan[0]["recommended_action"] == "Purchase"


def test_multi_level_bom_explosion_returns_only_leaf_components():
    products = [
        ProductModel(id=10, name="Parent"),
        ProductModel(id=20, name="Subassembly"),
        ProductModel(id=30, name="Leaf"),
    ]
    boms = [BomModel(id=1, product_id=10), BomModel(id=2, product_id=20)]
    components = [
        BomComponentModel(id=1, bom_id=1, product_id=20, product_qty=1.0),
        BomComponentModel(id=2, bom_id=2, product_id=30, product_qty=2.0),
    ]
    inventory = []

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(10, quantity=2.0)

    assert len(plan) == 1
    assert plan[0]["quantity_required"] == 4.0
    assert plan[0]["component_name"] == "Leaf"


def test_incoming_mo_reduces_shortage():
    products = [ProductModel(id=10, name="Parent"), ProductModel(id=20, name="Component")]
    boms = [BomModel(id=1, product_id=10)]
    components = [BomComponentModel(id=1, bom_id=1, product_id=20, product_qty=1.0)]
    inventory = [InventoryItemModel(id=1, product_id=20, quantity=1.0)]
    incoming_mos = [ManufacturingOrderModel(id=1, product_id=20, product_qty=2.0)]

    engine = ShortagePlanningEngine(
        boms=boms,
        components=components,
        products=products,
        inventory=inventory,
        incoming_mo_orders=incoming_mos,
    )
    plan = engine.build_plan(10, quantity=2.0)

    assert plan[0]["incoming_mo_quantity"] == 2.0
    assert plan[0]["projected_available"] == 3.0
    assert plan[0]["quantity_short"] == 0.0
    assert plan[0]["recommended_action"] == "Available"


def test_incoming_po_reduces_shortage():
    products = [ProductModel(id=10, name="Parent"), ProductModel(id=20, name="Component")]
    boms = [BomModel(id=1, product_id=10)]
    components = [BomComponentModel(id=1, bom_id=1, product_id=20, product_qty=1.0)]
    inventory = [InventoryItemModel(id=1, product_id=20, quantity=1.0)]
    incoming_po_lines = [PurchaseOrderLineModel(id=1, product_id=20, product_qty=2.0)]

    engine = ShortagePlanningEngine(
        boms=boms,
        components=components,
        products=products,
        inventory=inventory,
        incoming_purchase_order_lines=incoming_po_lines,
    )
    plan = engine.build_plan(10, quantity=2.0)

    assert plan[0]["incoming_po_quantity"] == 2.0
    assert plan[0]["projected_available"] == 3.0
    assert plan[0]["quantity_short"] == 0.0
    assert plan[0]["recommended_action"] == "Available"


def test_no_shortage_result_is_marked_available():
    products = [ProductModel(id=10, name="Parent"), ProductModel(id=20, name="Component")]
    boms = [BomModel(id=1, product_id=10)]
    components = [BomComponentModel(id=1, bom_id=1, product_id=20, product_qty=1.0)]
    inventory = [InventoryItemModel(id=1, product_id=20, quantity=10.0)]

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(10, quantity=2.0)

    assert plan[0]["quantity_short"] == 0.0
    assert plan[0]["recommended_action"] == "Available"


def test_template_level_bom_resolution_uses_template_id():
    products = [ProductModel(id=100, name="Template Parent"), ProductModel(id=200, name="Leaf")]
    boms = [BomModel(id=1, display_name="Template BOM", product_template_id=100)]
    components = [BomComponentModel(id=1, bom_id=1, product_id=200, product_qty=1.0)]
    inventory = []

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(100, quantity=1.0, product_template_id=100)

    assert len(plan) == 1
    assert plan[0]["component_name"] == "Leaf"
    assert plan[0]["parent_product"] == "Template BOM"


def test_positive_2000_on_hand_remains_positive():
    products = [ProductModel(id=10, name="Parent"), ProductModel(id=805, name="Spout Base Raw")]
    boms = [BomModel(id=1, product_id=10)]
    components = [BomComponentModel(id=1, bom_id=1, product_id=805, product_qty=1.0)]
    inventory = [InventoryItemModel(id=1, product_id=805, quantity=2000.0, reserved_quantity=2000.0)]

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(10, quantity=1.0)

    assert plan[0]["on_hand_quantity"] == 2000.0
    assert plan[0]["reserved_quantity"] == 2000.0
    assert plan[0]["free_available_quantity"] == 0.0


def test_template_level_bom_returns_manufacture():
    products = [
        ProductModel(id=10, name="Parent"),
        ProductModel(id=20, name="Component", product_tmpl_id=30),
    ]
    boms = [
        BomModel(id=1, product_id=10),
        BomModel(id=2, product_id=None, product_template_id=30, active=True, type="normal"),
    ]
    components = [BomComponentModel(id=1, bom_id=1, product_id=20, product_qty=2.0)]
    inventory = [InventoryItemModel(id=1, product_id=20, quantity=0.0, reserved_quantity=0.0)]

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(10, quantity=1.0)

    assert plan[0]["recommended_action"] == "Manufacture"


def test_purchased_component_returns_purchase():
    products = [
        ProductModel(id=10, name="Parent"),
        ProductModel(id=20, name="Buy Part", purchase_ok=True),
    ]
    boms = [BomModel(id=1, product_id=10)]
    components = [BomComponentModel(id=1, bom_id=1, product_id=20, product_qty=1.0)]
    inventory = [InventoryItemModel(id=1, product_id=20, quantity=0.0, reserved_quantity=0.0)]

    engine = ShortagePlanningEngine(boms=boms, components=components, products=products, inventory=inventory)
    plan = engine.build_plan(10, quantity=1.0)

    assert plan[0]["recommended_action"] == "Purchase"
