"""Список заказов покупателя (A5): состав, суммы, пагинация, фильтр, изоляция."""

from datetime import date, timedelta

MY_URL = "/api/storefront/requests/my"


async def prepare_shop(client, owner_headers) -> dict:
    """Магазин с витриной и одним товаром на складе."""
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_enabled": True},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Шуруповёрт", "purchase_price": "50", "retail_price": "120"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={
                **product,
                "photo": "https://example.com/drill.jpg",
                "show_on_storefront": True,
            },
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": product["id"], "quantity": "50", "cost": "50"}],
        },
    )
    return product


async def create_request(client, buyer_headers, product_id: int, quantity: str = "2") -> int:
    response = await client.post(
        "/api/storefront/magazin-berkat/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Ахмед",
            "items": [{"product_id": product_id, "quantity": quantity}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_my_requests_include_lines_and_shop(client, owner_headers, customer_headers):
    buyer_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)
    await create_request(client, buyer_headers, product["id"], "2")

    response = await client.get(MY_URL, headers=buyer_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1

    item = body["items"][0]
    assert item["shop_name"] == "Магазин Беркат"
    assert item["shop_slug"] == "magazin-berkat"
    assert item["created_at"]

    assert len(item["order_lines"]) == 1
    line = item["order_lines"][0]
    assert line["name"] == "Шуруповёрт"
    assert line["photo"] == "https://example.com/drill.jpg"
    assert line["quantity"] == "2.000"
    assert line["price"] == "120.00"
    # сумма заявки — по розничным ценам магазина
    assert item["order_total"] == "240.00"

    # заявка ещё не принята — заказных полей нет
    assert item["due_date"] is None
    assert item["to_pay"] is None


async def test_accepted_request_has_order_fields(client, owner_headers, customer_headers):
    buyer_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)
    request_id = await create_request(client, buyer_headers, product["id"], "3")

    due = (date.today() + timedelta(days=3)).isoformat()
    accepted = await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due, "prepayment": "100"},
    )
    assert accepted.status_code == 200, accepted.text

    item = (await client.get(MY_URL, headers=buyer_headers)).json()["items"][0]
    assert item["status"] == "accepted"
    assert item["due_date"] == due
    assert item["accepted_total"] == "360.00"
    assert item["prepayment"] == "100.00"
    assert item["to_pay"] == "260.00"
    assert item["order_status"]


async def test_pagination_and_status_filter(client, owner_headers, customer_headers):
    buyer_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)
    first_id = await create_request(client, buyer_headers, product["id"])
    await create_request(client, buyer_headers, product["id"])
    await create_request(client, buyer_headers, product["id"])

    await client.post(f"/api/storefront/requests/{first_id}/reject", headers=owner_headers)

    page = (await client.get(f"{MY_URL}?limit=2", headers=buyer_headers)).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2

    second = (await client.get(f"{MY_URL}?limit=2&offset=2", headers=buyer_headers)).json()
    assert second["total"] == 3
    assert len(second["items"]) == 1
    # страницы не пересекаются
    assert {i["id"] for i in page["items"]}.isdisjoint({i["id"] for i in second["items"]})

    rejected = (await client.get(f"{MY_URL}?status=rejected", headers=buyer_headers)).json()
    assert rejected["total"] == 1
    assert rejected["items"][0]["id"] == first_id

    new_only = (await client.get(f"{MY_URL}?status=new", headers=buyer_headers)).json()
    assert new_only["total"] == 2


async def test_other_customer_requests_not_visible(client, owner_headers, customer_headers):
    buyer_headers, _ = await customer_headers()
    stranger_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)
    await create_request(client, buyer_headers, product["id"])

    mine = (await client.get(MY_URL, headers=buyer_headers)).json()
    assert mine["total"] == 1

    theirs = (await client.get(MY_URL, headers=stranger_headers)).json()
    assert theirs["total"] == 0
    assert theirs["items"] == []


async def test_no_n_plus_one_on_many_requests(client, owner_headers, customer_headers, db_engine_queries):
    """Число SQL-запросов не должно расти вместе с числом заказов."""
    buyer_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)

    await create_request(client, buyer_headers, product["id"])
    with db_engine_queries() as counter_one:
        await client.get(MY_URL, headers=buyer_headers)
    baseline = counter_one.count

    for _ in range(4):
        await create_request(client, buyer_headers, product["id"])
    with db_engine_queries() as counter_many:
        await client.get(MY_URL, headers=buyer_headers)

    # пять заказов в одном магазине стоят столько же запросов, сколько один
    assert counter_many.count == baseline, (
        f"было {baseline} запросов на 1 заказ, стало {counter_many.count} на 5 — похоже на N+1"
    )
