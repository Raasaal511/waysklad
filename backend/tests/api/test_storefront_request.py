from datetime import date, timedelta


async def test_storefront_request_full_flow_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, buyer_phone = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Товар для заявки",
                "purchase_price": "50",
                "retail_price": "120",
                "show_on_storefront": True,
            },
        )
    ).json()
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "10", "cost": "50"}]},
    )
    assert response.status_code == 201, response.text

    # заявка от авторизованного покупателя
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Ахмед",
            "note": "Хочу два, если есть скидка — напишите",
            "items": [{"product_id": product["id"], "quantity": "2"}],
        },
    )
    assert response.status_code == 201, response.text
    request = response.json()
    assert request["status"] == "new"
    assert request["customer_name"] == "Ахмед"

    # владелец видит заявку в списке новых
    response = await client.get("/api/storefront/requests/new", headers=owner_headers)
    assert response.status_code == 200, response.text
    ids = [r["id"] for r in response.json()]
    assert request["id"] in ids

    # без авторизации список заявок недоступен
    response = await client.get("/api/storefront/requests/new")
    assert response.status_code in (401, 403), response.text

    due = (date.today() + timedelta(days=3)).isoformat()
    response = await client.post(
        f"/api/storefront/requests/{request['id']}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text
    order = response.json()
    assert order["source"] == "storefront"
    assert order["due_date"] == due
    assert order["lines"][0]["product_id"] == product["id"]
    assert order["lines"][0]["price"] == "120.00"  # цена взята из актуального retail_price

    # клиент создан по имени+телефону из заявки (телефон — из аккаунта покупателя)
    response = await client.get("/api/counterparties/clients", headers=owner_headers, params={"query": "Ахмед"})
    assert response.status_code == 200, response.text
    clients = response.json()
    assert any(c["phone"] == buyer_phone for c in clients)

    # повторно принять ту же заявку нельзя
    response = await client.post(
        f"/api/storefront/requests/{request['id']}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 400, response.text

    # повторная заявка с того же аккаунта не плодит второго клиента
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Ахмед",
            "items": [{"product_id": product["id"], "quantity": "1"}],
        },
    )
    assert response.status_code == 201, response.text
    second_request_id = response.json()["id"]
    response = await client.post(
        f"/api/storefront/requests/{second_request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text
    second_order = response.json()
    assert second_order["client_id"] == order["client_id"]  # тот же клиент, не дубль

    response = await client.get("/api/counterparties/clients", headers=owner_headers, params={"query": "Ахмед"})
    assert sum(1 for c in response.json() if c["phone"] == buyer_phone) == 1


async def test_storefront_request_rejects_unknown_variant_via_api(client, owner_headers, customer_headers):
    """variant_id в заявке должен принадлежать указанному товару — иначе
    заявка тихо приняла бы ссылку на несуществующий/чужой вариант."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product_with_variant = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Платье",
                "purchase_price": "500",
                "retail_price": "1500",
                "show_on_storefront": True,
                "variants": [{"size": "M", "color": "Красный"}],
            },
        )
    ).json()
    real_variant_id = product_with_variant["variants"][0]["id"]

    other_product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Кроссовки",
                "purchase_price": "800",
                "retail_price": "2500",
                "show_on_storefront": True,
                "variants": [{"size": "42", "color": "Синий"}],
            },
        )
    ).json()
    other_variant_id = other_product["variants"][0]["id"]

    # вариант, принадлежащий ДРУГОМУ товару — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [
                {"product_id": product_with_variant["id"], "quantity": "1", "variant_id": other_variant_id}
            ],
        },
    )
    assert response.status_code == 400, response.text

    # несуществующий variant_id — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product_with_variant["id"], "quantity": "1", "variant_id": 999999}],
        },
    )
    assert response.status_code == 400, response.text

    # правильный вариант этого же товара — принято
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [
                {"product_id": product_with_variant["id"], "quantity": "1", "variant_id": real_variant_id}
            ],
        },
    )
    assert response.status_code == 201, response.text


async def test_storefront_request_reject_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    request = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=buyer_headers,
            json={"customer_name": "Тест", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()

    response = await client.post(
        f"/api/storefront/requests/{request['id']}/reject", headers=owner_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"

    # повторно отклонить/принять нельзя
    response = await client.post(
        f"/api/storefront/requests/{request['id']}/reject", headers=owner_headers
    )
    assert response.status_code == 400, response.text

    # заявка на скрытый товар отклоняется на уровне создания
    hidden = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Скрытый", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Тест", "items": [{"product_id": hidden["id"], "quantity": "1"}]},
    )
    assert response.status_code == 400, response.text


async def test_storefront_request_reserves_stock_via_api(client, owner_headers, customer_headers):
    """Заявка сразу резервирует остаток — следующая заявка на весь оставшийся
    остаток должна увидеть недостаточность и пометить это флагом, а не тихо
    принять невозможный заказ."""
    slug = "magazin-berkat"
    first_buyer, _ = await customer_headers()
    second_buyer, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Резервируемый товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "5", "cost": "50"}]},
    )
    assert response.status_code == 201, response.text

    # первая заявка на весь остаток — резерв полностью покрыт
    first = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=first_buyer,
            json={"customer_name": "Первый", "items": [{"product_id": product["id"], "quantity": "5"}]},
        )
    ).json()
    assert first["insufficient_stock_at_request"] is False

    # вторая заявка на тот же товар — остатка уже нет (весь зарезервирован первой)
    second = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=second_buyer,
            json={"customer_name": "Второй", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    assert second["insufficient_stock_at_request"] is True

    # владелец увидел уведомление о новой заявке
    response = await client.get("/api/notifications", headers=owner_headers)
    assert response.status_code == 200, response.text
    kinds = [n["kind"] for n in response.json()["items"]]
    assert kinds.count("storefront_request_new") == 2


async def test_storefront_request_accept_does_not_double_reserve_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    first_buyer, _ = await customer_headers()
    second_buyer, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "3", "cost": "50"}]},
    )

    request = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=first_buyer,
            json={"customer_name": "Клиент", "items": [{"product_id": product["id"], "quantity": "3"}]},
        )
    ).json()
    assert request["insufficient_stock_at_request"] is False

    due = (date.today() + timedelta(days=3)).isoformat()
    response = await client.post(
        f"/api/storefront/requests/{request['id']}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text

    # если бы резерв на создании и на принятии складывались — новая заявка на
    # тот же остаток увидела бы "недостаточно" уже при 1 штуке (3 занято create + 3 accept > 3 факт)
    third = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=second_buyer,
            json={"customer_name": "Третий", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    # остаток физически весь ушёл в принятый заказ — новая заявка честно не резервирует
    assert third["insufficient_stock_at_request"] is True


async def test_storefront_request_reject_releases_reservation_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    first_buyer, _ = await customer_headers()
    second_buyer, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "2", "cost": "50"}]},
    )

    request = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=first_buyer,
            json={"customer_name": "Клиент", "items": [{"product_id": product["id"], "quantity": "2"}]},
        )
    ).json()
    assert request["insufficient_stock_at_request"] is False

    response = await client.post(
        f"/api/storefront/requests/{request['id']}/reject", headers=owner_headers
    )
    assert response.status_code == 200, response.text

    # резерв снят отклонением — новая заявка на тот же остаток снова видит его целиком
    after_reject = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=second_buyer,
            json={"customer_name": "Второй", "items": [{"product_id": product["id"], "quantity": "2"}]},
        )
    ).json()
    assert after_reject["insufficient_stock_at_request"] is False


async def test_storefront_chat_rest_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    created = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=buyer_headers,
            json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    assert "access_token" in created and created["access_token"]
    token = created["access_token"]

    # owner-side ответ (список заявок) не содержит токен
    response = await client.get("/api/storefront/requests/new", headers=owner_headers)
    assert "access_token" not in response.json()[0]

    # покупатель пишет по своему токену
    response = await client.post(
        "/api/storefront/requests/chat", params={"token": token}, json={"text": "Уточните размер, пожалуйста"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["author"] == "customer"

    # неверный токен — заявка не найдена
    response = await client.post(
        "/api/storefront/requests/chat", params={"token": "garbage"}, json={"text": "тест"}
    )
    assert response.status_code == 404, response.text

    # сотрудник читает и отвечает
    response = await client.get(
        f"/api/storefront/requests/{created['id']}/chat", headers=owner_headers
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["text"] == "Уточните размер, пожалуйста"

    response = await client.post(
        f"/api/storefront/requests/{created['id']}/chat",
        headers=owner_headers,
        json={"text": "Размер M подойдёт?"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["author"] == "staff"

    # покупатель по токену видит оба сообщения
    response = await client.get("/api/storefront/requests/chat", params={"token": token})
    assert response.status_code == 200, response.text
    texts = [m["text"] for m in response.json()]
    assert texts == ["Уточните размер, пожалуйста", "Размер M подойдёт?"]

    # без авторизации staff-эндпоинт недоступен
    response = await client.get(f"/api/storefront/requests/{created['id']}/chat")
    assert response.status_code in (401, 403), response.text


async def test_storefront_chat_websocket_via_api(client, owner_headers, customer_headers):
    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    created = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=buyer_headers,
            json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    token = created["access_token"]

    sync_client = TestClient(fastapi_app)
    with sync_client.websocket_connect(f"/api/storefront/requests/chat/ws?token={token}") as ws:
        response = await client.post(
            f"/api/storefront/requests/{created['id']}/chat",
            headers=owner_headers,
            json={"text": "Ответ владельца через WS"},
        )
        assert response.status_code == 201, response.text

        event = ws.receive_json()
        assert event["author"] == "staff"
        assert event["text"] == "Ответ владельца через WS"


async def test_storefront_request_status_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "150", "show_on_storefront": True},
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "5", "cost": "50"}]},
    )
    created = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=buyer_headers,
            json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    token = created["access_token"]

    response = await client.get("/api/storefront/requests/status", params={"token": token})
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "new", "order": None}

    due = (date.today() + timedelta(days=2)).isoformat()
    await client.post(
        f"/api/storefront/requests/{created['id']}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )

    response = await client.get("/api/storefront/requests/status", params={"token": token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["order"]["due_date"] == due
    assert body["order"]["total"] == "150.00"

    response = await client.get("/api/storefront/requests/status", params={"token": "garbage"})
    assert response.status_code == 404, response.text


async def test_storefront_request_spam_protection_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    spammer_headers, _ = await customer_headers()
    other_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()

    for _ in range(5):
        response = await client.post(
            f"/api/storefront/{slug}/requests",
            headers=spammer_headers,
            json={
                "customer_name": "Спамер",
                "items": [{"product_id": product["id"], "quantity": "1"}],
            },
        )
        assert response.status_code == 201, response.text

    # шестая необработанная заявка с того же аккаунта — отклонена
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=spammer_headers,
        json={
            "customer_name": "Спамер",
            "items": [{"product_id": product["id"], "quantity": "1"}],
        },
    )
    assert response.status_code == 400, response.text

    # другой аккаунт — не ограничен предыдущими заявками
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=other_headers,
        json={
            "customer_name": "Другой человек",
            "items": [{"product_id": product["id"], "quantity": "1"}],
        },
    )
    assert response.status_code == 201, response.text

    # без авторизации заявку оформить нельзя вообще
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={"customer_name": "Аноним", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    assert response.status_code == 401, response.text


async def test_storefront_request_min_and_step_qty_via_api(client, owner_headers, customer_headers):
    """Мин. количество и шаг заказа — ограничение только для заявки с витрины,
    не для обычной продажи/заказа (тех тестов эта фича не касается)."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Мука оптом",
                "purchase_price": "50",
                "retail_price": "100",
                "show_on_storefront": True,
                "storefront_min_qty": "10",
                "storefront_step_qty": "10",
            },
        )
    ).json()
    assert product["storefront_min_qty"] == "10"
    assert product["storefront_step_qty"] == "10"

    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    listed = next(p for p in response.json()["products"] if p["id"] == product["id"])
    assert listed["min_order_qty"] == "10.000"
    assert listed["order_step_qty"] == "10.000"

    # меньше минимума — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product["id"], "quantity": "5"}],
        },
    )
    assert response.status_code == 400, response.text

    # не кратно шагу от минимума — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product["id"], "quantity": "15"}],
        },
    )
    assert response.status_code == 400, response.text

    # минимум плюс шаг — принято
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product["id"], "quantity": "20"}],
        },
    )
    assert response.status_code == 201, response.text

    # тот же товар двумя строками (например, два разных варианта) —
    # мин.кол-во и шаг проверяются суммарно по товару, не по каждой строке
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [
                {"product_id": product["id"], "quantity": "5"},
                {"product_id": product["id"], "quantity": "5"},
            ],
        },
    )
    assert response.status_code == 201, response.text  # 5+5=10 — валидно, хотя каждая строка меньше минимума
