from app.models.odoo import BomComponentModel, BomModel, ProductModel
from app.planning.bom import BOMExplosionEngine, explode_bom


def test_explode_bom_recursively_calculates_component_quantities():
    products = [
        ProductModel(id=10, name="Finished Product"),
        ProductModel(id=20, name="Raw Material A"),
        ProductModel(id=30, name="Subassembly"),
        ProductModel(id=40, name="Raw Material B"),
    ]
    boms = [
        BomModel(id=1, product_id=10, name="Finished Product BOM"),
        BomModel(id=2, product_id=30, name="Subassembly BOM"),
    ]
    components = [
        BomComponentModel(id=100, bom_id=1, product_id=20, product_qty=2.0),
        BomComponentModel(id=101, bom_id=1, product_id=30, product_qty=1.0),
        BomComponentModel(id=102, bom_id=2, product_id=40, product_qty=3.0),
    ]

    engine = BOMExplosionEngine(boms=boms, components=components, products=products)
    exploded = engine.explode(10, quantity=2.0)

    assert exploded == [
        {"product_id": 20, "product_name": "Raw Material A", "quantity": 4.0},
        {"product_id": 40, "product_name": "Raw Material B", "quantity": 6.0},
    ]


def test_explode_bom_avoids_infinite_recursion():
    products = [ProductModel(id=1, name="Cycle A"), ProductModel(id=2, name="Cycle B")]
    boms = [BomModel(id=1, product_id=1, name="Cycle BOM A"), BomModel(id=2, product_id=2, name="Cycle BOM B")]
    components = [
        BomComponentModel(id=200, bom_id=1, product_id=2, product_qty=1.0),
        BomComponentModel(id=201, bom_id=2, product_id=1, product_qty=1.0),
    ]

    engine = BOMExplosionEngine(boms=boms, components=components, products=products)
    exploded = engine.explode(1, quantity=1.0)

    assert exploded == []


def test_helper_function_wraps_engine():
    products = [ProductModel(id=10, name="Finished Product"), ProductModel(id=20, name="Raw Material A")]
    boms = [BomModel(id=1, product_id=10, name="Finished Product BOM")]
    components = [BomComponentModel(id=100, bom_id=1, product_id=20, product_qty=2.0)]

    result = explode_bom(10, quantity=1.0, boms=boms, components=components, products=products)

    assert result[0]["product_id"] == 20
    assert result[0]["quantity"] == 2.0
