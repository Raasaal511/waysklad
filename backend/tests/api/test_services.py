"""Услуги: позиция каталога, которая не трогает склад.

Услуга — не отдельная таблица, а вид товара (kind='service'): иначе
пришлось бы удваивать продажу, корзину, заказ с витрины и аналитику.
Отличие ровно одно — склад её не касается, см. Product.is_service.
"""

from decimal import Decimal


async def _create_service(client, headers, name="Шиномонтаж", price="500", **extra):
    response = await client.post(
        "/api/products",
        headers=headers,
        json={
            "name": name,
            "kind": "service",
            "unit_code": "service",
            "retail_price": price,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_service_units_available_via_api(client, owner_headers):
    """Час, услуга, день и выезд должны быть в справочнике единиц магазина:
    без них услугу не в чем измерить. Час дробный — «полтора часа» норма."""
    response = await client.get("/api/products/units", headers=owner_headers)
    assert response.status_code == 200, response.text
    units = {u["code"]: u for u in response.json()}
    for code in ("hour", "service", "day", "visit"):
        assert code in units, f"единица «{code}» не засеяна магазину"
    assert units["hour"]["fractional"] is True
    assert units["service"]["fractional"] is False


async def test_service_sells_without_stock_via_api(client, owner_headers):
    """Главное в услугах: продаются без остатка. Раньше услугу приходилось
    заводить фиктивным товаром и приходовать его, иначе продажа упиралась
    в проверку остатка."""
    service = await _create_service(client, owner_headers)
    assert service["kind"] == "service"

    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": service["id"], "quantity": "1", "price": "500"}],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["total"] == "500.00"

    # остаток не появился и не ушёл в минус — услуги на складе нет вовсе
    response = await client.get("/api/inventory/stock", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert all(item["product_id"] != service["id"] for item in response.json())


async def test_service_has_no_purchase_price_via_api(client, owner_headers):
    """«Услуга это услуга — цена указывается только ту сумму»: закупочной
    цены у услуги нет, вся выручка идёт в прибыль."""
    service = await _create_service(client, owner_headers, purchase_price="300")
    assert service["purchase_price"] == "0.00"
    assert service["margin"] == "500.00"

    # и при обновлении закупочную подставить тоже нельзя
    response = await client.put(
        f"/api/products/{service['id']}",
        headers=owner_headers,
        json={**service, "purchase_price": "300", "min_stock": "5"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["purchase_price"] == "0.00"
    assert Decimal(response.json()["min_stock"]) == 0  # услуге нечему заканчиваться


async def test_service_rejects_initial_stock_via_api(client, owner_headers):
    """Приход на услугу — ошибка, а не молчаливое создание остатка."""
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Мойка",
            "kind": "service",
            "unit_code": "service",
            "retail_price": "300",
            "initial_stock_warehouse_id": 1,
            "initial_stock_quantity": "10",
        },
    )
    assert response.status_code == 400, response.text


async def test_sale_mixes_product_and_service_via_api(client, owner_headers):
    """Чек из товара и услуги: товар списывается, услуга — нет.
    Это сценарий владельца: шина + шиномонтаж одним чеком."""
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Шина", "purchase_price": "2000", "retail_price": "4000"},
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": product["id"], "quantity": "4", "cost": "2000"}],
        },
    )
    service = await _create_service(client, owner_headers)

    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [
                {"product_id": product["id"], "quantity": "1", "price": "4000"},
                {"product_id": service["id"], "quantity": "1", "price": "500"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["total"] == "4500.00"

    stock = {item["product_id"]: item for item in (await client.get("/api/inventory/stock", headers=owner_headers)).json()}
    assert stock[product["id"]]["quantity"] == "3.000"  # шина списалась
    assert service["id"] not in stock  # услуга на складе не заведена


async def test_service_return_does_not_restock_via_api(client, owner_headers):
    """Возврат услуги возвращает деньги, но не создаёт остаток из воздуха."""
    service = await _create_service(client, owner_headers)
    sale = (
        await client.post(
            "/api/sales",
            headers=owner_headers,
            json={
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": service["id"], "quantity": "2", "price": "500"}],
            },
        )
    ).json()

    response = await client.post(
        f"/api/sales/{sale['id']}/returns",
        headers=owner_headers,
        json={"items": [{"sale_line_id": sale["lines"][0]["id"], "quantity": "1"}]},
    )
    assert response.status_code == 201, response.text

    stock = (await client.get("/api/inventory/stock", headers=owner_headers)).json()
    assert all(item["product_id"] != service["id"] for item in stock)


async def test_service_addons_via_api(client, owner_headers):
    """Допы услуги — варианты с флагом addon: «балансировка +500 ₽».
    В отличие от варианта товара, допы складываются, а не выбирается один."""
    service = await _create_service(
        client,
        owner_headers,
        name="Шиномонтаж колеса",
        variants=[
            {"name": "Балансировка", "price": "500", "addon": True},
            {"name": "Утилизация старой", "price": "200", "addon": True},
        ],
    )
    assert [v["addon"] for v in service["variants"]] == [True, True]
    assert [v["price"] for v in service["variants"]] == ["500.00", "200.00"]


async def test_product_variant_is_never_addon_via_api(client, owner_headers):
    """У обычного товара допов не бывает: его варианты взаимоисключающие
    (размер S *или* M), поэтому addon у них всегда False."""
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Футболка",
                "purchase_price": "100",
                "retail_price": "300",
                "variants": [{"size": "M", "addon": True}],
            },
        )
    ).json()
    assert product["variants"][0]["addon"] is False


async def test_product_kind_cannot_change_via_api(client, owner_headers):
    """Вид позиции не меняется после создания: товар с остатком нельзя
    превратить в услугу, не оставив остаток без владельца."""
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Масло", "purchase_price": "200", "retail_price": "500"},
        )
    ).json()
    assert product["kind"] == "product"

    response = await client.put(
        f"/api/products/{product['id']}",
        headers=owner_headers,
        json={**product, "kind": "service"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "product"  # kind из запроса игнорируется
