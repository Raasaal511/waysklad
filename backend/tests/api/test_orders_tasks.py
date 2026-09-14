from datetime import date, timedelta


async def test_storekeeper_limited_to_assigned_warehouse_via_api(
    client, owner_headers, random_phone
):
    # заводим кладовщика и второй склад, назначаем его только на второй склад
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Руслан", "phone": random_phone(), "password": "secret123",
            "role": "storekeeper",
        },
    )
    storekeeper_id = response.json()["id"]

    login = await client.post(
        "/api/auth/login",
        json={"phone": response.json()["phone"], "password": "secret123"},
    )
    storekeeper_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    warehouses = (await client.get("/api/inventory/warehouses", headers=owner_headers)).json()
    main_warehouse_id = warehouses[0]["id"]

    # в момент создания кладовщика склад был единственным — сотрудник привязан
    # к нему автоматически; снимаем эту привязку, чтобы проверить ограничение
    # доступа именно ко второму (явно не назначенному) складу
    response = await client.put(
        f"/api/inventory/warehouses/{main_warehouse_id}/assignments",
        headers=owner_headers,
        json={"user_ids": []},
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        "/api/inventory/warehouses",
        headers=owner_headers,
        json={"name": "Склад Б", "assigned_user_ids": [storekeeper_id]},
    )
    assert response.status_code == 201, response.text
    second_warehouse = response.json()
    assert second_warehouse["assigned_user_ids"] == [storekeeper_id]

    # кладовщик видит только назначенный склад
    response = await client.get("/api/inventory/warehouses", headers=storekeeper_headers)
    assert [w["id"] for w in response.json()] == [second_warehouse["id"]]

    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Кирпич", "purchase_price": "10", "retail_price": "15"},
        )
    ).json()

    # приёмка на назначенный склад — можно
    response = await client.post(
        "/api/inventory/receive",
        headers=storekeeper_headers,
        json={
            "warehouse_id": second_warehouse["id"],
            "lines": [{"product_id": product["id"], "quantity": "10"}],
        },
    )
    assert response.status_code == 201, response.text

    # приёмка на чужой (не назначенный) склад — запрещена
    response = await client.post(
        "/api/inventory/receive",
        headers=storekeeper_headers,
        json={
            "warehouse_id": main_warehouse_id,
            "lines": [{"product_id": product["id"], "quantity": "10"}],
        },
    )
    assert response.status_code == 403

    # владелец меняет назначения — снимает кладовщика со склада
    response = await client.put(
        f"/api/inventory/warehouses/{second_warehouse['id']}/assignments",
        headers=owner_headers,
        json={"user_ids": []},
    )
    assert response.status_code == 200, response.text
    assert response.json()["assigned_user_ids"] == []

    response = await client.get("/api/inventory/warehouses", headers=storekeeper_headers)
    assert response.json() == []


async def test_counterparties_scoped_by_warehouse_via_api(client, owner_headers, random_phone):
    # клиент/поставщик привязаны к складу транзитивно — через продажу/приёмку
    # на этом складе (warehouse_client_links/warehouse_supplier_links); продавец,
    # привязанный только к своему складу, не должен видеть чужих контрагентов
    warehouses = (await client.get("/api/inventory/warehouses", headers=owner_headers)).json()
    main_warehouse_id = warehouses[0]["id"]

    response = await client.post(
        "/api/inventory/warehouses", headers=owner_headers, json={"name": "Склад Б"}
    )
    assert response.status_code == 201, response.text
    second_warehouse_id = response.json()["id"]

    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для контрагентов", "purchase_price": "50", "retail_price": "100"},
    )
    product_id = response.json()["id"]
    for warehouse_id in (main_warehouse_id, second_warehouse_id):
        await client.post(
            "/api/inventory/receive",
            headers=owner_headers,
            json={"warehouse_id": warehouse_id, "lines": [{"product_id": product_id, "quantity": "10"}]},
        )

    client_main = (
        await client.post(
            "/api/counterparties/clients", headers=owner_headers, json={"name": "Клиент склада А"}
        )
    ).json()
    client_second = (
        await client.post(
            "/api/counterparties/clients", headers=owner_headers, json={"name": "Клиент склада Б"}
        )
    ).json()
    supplier_main = (
        await client.post(
            "/api/counterparties/suppliers", headers=owner_headers, json={"name": "Поставщик склада А"}
        )
    ).json()
    supplier_second = (
        await client.post(
            "/api/counterparties/suppliers", headers=owner_headers, json={"name": "Поставщик склада Б"}
        )
    ).json()

    # засвечиваем каждого контрагента на своём складе продажей/приёмкой
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": main_warehouse_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
            "client_id": client_main["id"],
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": second_warehouse_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
            "client_id": client_second["id"],
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": main_warehouse_id,
            "lines": [{"product_id": product_id, "quantity": "1", "cost": "50"}],
            "supplier_id": supplier_main["id"],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": second_warehouse_id,
            "lines": [{"product_id": product_id, "quantity": "1", "cost": "50"}],
            "supplier_id": supplier_second["id"],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert response.status_code == 201, response.text

    # владелец видит всех
    response = await client.get("/api/counterparties/clients", headers=owner_headers)
    names = {c["name"] for c in response.json()}
    assert {"Клиент склада А", "Клиент склада Б"} <= names
    response = await client.get("/api/counterparties/suppliers", headers=owner_headers)
    names = {s["name"] for s in response.json()}
    assert {"Поставщик склада А", "Поставщик склада Б"} <= names

    # продавец, назначенный только на склад А, видит только своих контрагентов
    seller_phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Продавец А", "phone": seller_phone, "password": "secret123",
            "role": "seller", "warehouse_ids": [main_warehouse_id],
        },
    )
    assert response.status_code == 201, response.text
    login = await client.post(
        "/api/auth/login", json={"phone": seller_phone, "password": "secret123"}
    )
    seller_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("/api/counterparties/clients", headers=seller_headers)
    names = {c["name"] for c in response.json()}
    assert "Клиент склада А" in names
    assert "Клиент склада Б" not in names

    response = await client.get("/api/counterparties/suppliers", headers=seller_headers)
    names = {s["name"] for s in response.json()}
    assert "Поставщик склада А" in names
    assert "Поставщик склада Б" not in names


async def test_order_full_lifecycle_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Торт на заказ", "purchase_price": "1500", "retail_price": "3000"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "1"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Милана"}
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "3000"}],
            "due_date": date.today().isoformat(),
            "prepayment": "1000",
            "source": "whatsapp",
            "note": "надпись «С юбилеем»",
        },
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["to_pay"] == "2000.00"
    assert order["source"] == "whatsapp"
    assert order["number"] is not None
    order_id = order["id"]

    # остаток зарезервирован под заказ — обычная продажа не пройдёт
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1", "price": "3000"}],
        },
    )
    assert response.status_code == 400

    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "in_progress"}
    )
    assert response.status_code == 200

    # нельзя перескочить сразу в "выдан" из "в работе" сменой статуса — только через /issue
    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "issued"}
    )
    assert response.status_code == 400

    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "ready"}
    )
    assert response.status_code == 200

    response = await client.post(
        f"/api/orders/{order_id}/issue",
        headers=owner_headers,
        json={"payment_method": "cash", "cash_received": "2000"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["sale"]["total"] == "2000.00"  # доплата, не полная сумма заказа
    assert result["sale"]["change"] == "0.00"
    assert result["order"]["status"] == "issued"
    assert result["order"]["sale_id"] == result["sale"]["id"]
    assert result["sale"]["order_id"] == order_id

    response = await client.get("/api/orders", headers=owner_headers)
    assert response.json() == []  # выданные заказы не входят в список активных

    response = await client.get("/api/orders/completed", headers=owner_headers)
    assert response.status_code == 200
    completed = response.json()
    assert len(completed) == 1
    assert completed[0]["id"] == order_id
    assert completed[0]["status"] == "issued"
    assert completed[0]["number"] is not None

    response = await client.get(f"/api/orders/{order_id}", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "issued"

    response = await client.get(f"/api/orders/{order_id}/history", headers=owner_headers)
    assert response.status_code == 200
    actions = [e["action"] for e in response.json()]
    assert "order.create" in actions
    assert "order.issue" in actions

    # остаток физически списан (весь куплен) — позиция с нулевым остатком не
    # входит в список (GET /inventory/stock отдаёт только ненулевые остатки)
    response = await client.get("/api/inventory/stock", headers=owner_headers)
    assert all(i["product_id"] != product_id for i in response.json())


async def test_order_edit_and_cancel_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Платье", "purchase_price": "1000", "retail_price": "2000"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "5"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Хава"}
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "2", "price": "2000"}],
            "due_date": date.today().isoformat(),
        },
    )
    order_id = response.json()["id"]

    # редактирование состава пересчитывает резерв
    response = await client.patch(
        f"/api/orders/{order_id}",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "4", "price": "2000"}],
            "due_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == "8000.00"

    response = await client.get("/api/inventory/stock", headers=owner_headers)
    stock = next(i for i in response.json() if i["product_id"] == product_id)
    assert stock["reserved"] == "4.000"

    # отмена освобождает резерв
    response = await client.post(
        f"/api/orders/{order_id}/cancel", headers=owner_headers, json={"reason": "передумала"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    response = await client.get("/api/inventory/stock", headers=owner_headers)
    stock = next(i for i in response.json() if i["product_id"] == product_id)
    assert stock["reserved"] == "0.000"

    response = await client.get("/api/orders/completed", headers=owner_headers)
    completed = response.json()
    assert len(completed) == 1
    assert completed[0]["status"] == "cancelled"

    # отменённый заказ нельзя редактировать/выдать
    response = await client.patch(
        f"/api/orders/{order_id}",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "2000"}],
        },
    )
    assert response.status_code == 400


async def test_task_full_lifecycle_via_api(client, owner_headers, random_phone):
    # 1. сотрудник, которому назначим задачу
    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Хеда", "phone": phone, "password": "secret123", "role": "seller"},
    )
    assert response.status_code == 201, response.text
    employee_id = response.json()["id"]

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123"}
    )
    employee_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    # 2. владелец ставит задачу сотруднику
    response = await client.post(
        "/api/tasks",
        headers=owner_headers,
        json={
            "title": "Позвонить поставщику",
            "assigned_user_id": employee_id,
            "note": "по цементу",
            "due_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    task = response.json()
    task_id = task["id"]
    assert task["status"] == "new"
    assert task["number"] is not None
    assert task["assigned_user_name"] == "Хеда"

    # 3. уведомление о назначении пришло сотруднику, а не владельцу
    response = await client.get("/api/notifications", headers=employee_headers)
    assert response.status_code == 200
    notifications = response.json()
    assert notifications["unread"] == 1
    assert notifications["items"][0]["kind"] == "task_assigned"

    response = await client.get("/api/notifications", headers=owner_headers)
    assert response.json()["unread"] == 0

    # 4. сотрудник видит только свою задачу и ведёт её по доске
    response = await client.get("/api/tasks", headers=employee_headers)
    assert [t["id"] for t in response.json()] == [task_id]

    response = await client.patch(
        f"/api/tasks/{task_id}/status", headers=employee_headers, json={"new_status": "in_progress"}
    )
    assert response.status_code == 200

    response = await client.patch(
        f"/api/tasks/{task_id}/status", headers=employee_headers, json={"new_status": "done"}
    )
    assert response.status_code == 200

    # done — терминальный статус
    response = await client.patch(
        f"/api/tasks/{task_id}/status", headers=employee_headers, json={"new_status": "new"}
    )
    assert response.status_code == 400

    # 5. активные/завершённые списки и история
    response = await client.get("/api/tasks", headers=owner_headers)
    assert response.json() == []

    response = await client.get("/api/tasks/completed", headers=owner_headers)
    completed = response.json()
    assert len(completed) == 1 and completed[0]["status"] == "done"

    response = await client.get(f"/api/tasks/{task_id}/history", headers=owner_headers)
    actions = [e["action"] for e in response.json()]
    assert actions == ["task.status", "task.status", "task.create"]

    # 6. автор получил уведомление о выполнении
    response = await client.get("/api/notifications", headers=owner_headers)
    owner_notifications = response.json()
    assert owner_notifications["unread"] == 1
    assert owner_notifications["items"][0]["kind"] == "task_done"
    notification_id = owner_notifications["items"][0]["id"]

    response = await client.post(
        f"/api/notifications/{notification_id}/read", headers=owner_headers
    )
    assert response.status_code == 200
    assert (await client.get("/api/notifications", headers=owner_headers)).json()["unread"] == 0


async def test_task_client_link_via_api(client, owner_headers, random_phone):
    # CRM: задача может быть привязана к клиенту — попадает в его ленту событий
    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Ахмед"}
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/tasks",
        headers=owner_headers,
        json={"title": "Перезвонить по заказу", "client_id": client_id},
    )
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["client_id"] == client_id

    # несуществующий клиент — понятная ошибка, а не молчаливое сохранение
    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Без клиента", "client_id": 999999},
    )
    assert response.status_code == 404, response.text

    # PATCH может как сменить привязку, так и явно снять её
    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Марьям"}
    )
    other_client_id = response.json()["id"]

    response = await client.patch(
        f"/api/tasks/{task['id']}", headers=owner_headers, json={"client_id": other_client_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["client_id"] == other_client_id

    response = await client.patch(
        f"/api/tasks/{task['id']}", headers=owner_headers, json={"client_id": None},
    )
    assert response.status_code == 200
    assert response.json()["client_id"] is None


async def test_task_client_link_tenant_isolation_via_api(client, owner_headers, random_phone):
    # клиент другого магазина не должен быть доступен для привязки задачи
    other_owner_phone = random_phone()
    await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Чужой магазин", "owner_name": "Другой", "phone": other_owner_phone,
            "password": "secret123",
        },
    )
    login = await client.post(
        "/api/auth/login", json={"phone": other_owner_phone, "password": "secret123"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        "/api/counterparties/clients", headers=other_headers, json={"name": "Чужой клиент"}
    )
    foreign_client_id = response.json()["id"]

    response = await client.post(
        "/api/tasks",
        headers=owner_headers,
        json={"title": "Задача", "client_id": foreign_client_id},
    )
    assert response.status_code == 404, response.text


async def test_client_timeline_via_api(client, owner_headers):
    # CRM: единая лента событий клиента вместо поиска по Продажам/Заказам/Долгам/Задачам
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для ленты", "purchase_price": "100", "retail_price": "200"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Ахмед лента"}
    )
    client_id = response.json()["id"]

    # пустая лента для нового клиента — не ошибка
    response = await client.get(f"/api/counterparties/clients/{client_id}/timeline", headers=owner_headers)
    assert response.status_code == 200
    assert response.json() == []

    # обычная продажа
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1, "payment_method": "cash", "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
        },
    )
    assert response.status_code == 201, response.text

    # продажа в долг + погашение
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1, "payment_method": "credit", "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert response.status_code == 201, response.text
    debts = (await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)).json()["debts"]
    debt_id = debts[0]["id"]
    response = await client.post(
        f"/api/debts/{debt_id}/repayments", headers=owner_headers, json={"amount": "50"},
    )
    assert response.status_code == 200, response.text

    # заказ
    response = await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id, "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "due_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["id"]

    # задача, привязанная к клиенту
    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Уточнить размер", "client_id": client_id},
    )
    assert response.status_code == 201, response.text
    task_id = response.json()["id"]

    response = await client.get(f"/api/counterparties/clients/{client_id}/timeline", headers=owner_headers)
    assert response.status_code == 200
    events = response.json()

    assert any(e["type"] == "sale" for e in events)
    assert sum(1 for e in events if e["type"] == "sale") == 2
    assert any(e["type"] == "debt_issued" and e["entity_id"] == debt_id for e in events)
    assert any(e["type"] == "debt_repaid" and e["entity_id"] == debt_id for e in events)
    assert any(e["type"] == "order_created" and e["entity_id"] == order_id for e in events)
    assert any(e["type"] == "task" and e["entity_id"] == task_id for e in events)

    # новые события сверху (по убыванию даты) — свежесозданная задача первая
    assert events[0]["type"] == "task"

    # несуществующий клиент — 404, не пустая лента (не спутать «нет событий» с «нет доступа»)
    response = await client.get("/api/counterparties/clients/999999/timeline", headers=owner_headers)
    assert response.status_code == 404


async def test_client_summary_via_api(client, owner_headers):
    # CRM: карточка клиента как хаб — баланс долга и счётчики активных заказов/задач
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для сводки", "purchase_price": "100", "retail_price": "200"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Ахмед сводка"}
    )
    client_id = response.json()["id"]

    response = await client.get(f"/api/counterparties/clients/{client_id}", headers=owner_headers)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["client"]["id"] == client_id
    assert summary["debt_balance"] == "0.00"
    assert summary["active_orders_count"] == 0
    assert summary["open_tasks_count"] == 0

    # продажа в долг — баланс растёт
    await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1, "payment_method": "credit", "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )

    # активный заказ
    await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id, "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "due_date": date.today().isoformat(),
        },
    )

    # одна задача останется открытой, вторую закроем — в счётчик попадает только открытая
    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Закроем", "client_id": client_id},
    )
    task_to_close_id = response.json()["id"]
    await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Останется открытой", "client_id": client_id},
    )
    await client.patch(
        f"/api/tasks/{task_to_close_id}/status", headers=owner_headers, json={"new_status": "done"},
    )

    response = await client.get(f"/api/counterparties/clients/{client_id}", headers=owner_headers)
    summary = response.json()
    assert summary["debt_balance"] == "200.00"
    assert summary["active_orders_count"] == 1
    assert summary["open_tasks_count"] == 1

    response = await client.get("/api/counterparties/clients/999999", headers=owner_headers)
    assert response.status_code == 404


async def test_seller_sees_only_own_tasks_via_api(client, owner_headers, random_phone):
    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Заур", "phone": phone, "password": "secret123", "role": "seller"},
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123"}
    )
    seller_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Задача владельца себе"}
    )
    assert response.status_code == 201, response.text
    owner_task_id = response.json()["id"]

    response = await client.get("/api/tasks", headers=seller_headers)
    assert response.json() == []

    response = await client.get(f"/api/tasks/{owner_task_id}", headers=seller_headers)
    assert response.status_code == 403

    # продавцу нельзя назначать задачи другим (нет USERS_MANAGE)
    response = await client.post(
        "/api/tasks",
        headers=seller_headers,
        json={"title": "Чужая задача", "assigned_user_id": 1},
    )
    assert response.status_code == 403


async def test_storekeeper_cannot_view_orders_via_api(client, owner_headers, random_phone):
    storekeeper_phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Иса",
            "phone": storekeeper_phone,
            "password": "secret123",
            "role": "storekeeper",
        },
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/auth/login", json={"phone": storekeeper_phone, "password": "secret123"}
    )
    storekeeper_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.get("/api/orders", headers=storekeeper_headers)
    assert response.status_code == 403

    response = await client.get("/api/orders/1", headers=storekeeper_headers)
    assert response.status_code == 403


async def test_audit_log_records_actions_on_entity_history(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Мёд горный",
            "unit_code": "kg",
            "purchase_price": "400",
            "retail_price": "700",
        },
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )
    sale = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1.5", "price": "700"}],
        },
    )
    sale_id = sale.json()["id"]

    # история продажи — записана через тот же журнал, но по конкретной сущности
    response = await client.get(f"/api/sales/{sale_id}/history", headers=owner_headers)
    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json()]
    assert actions == ["sale.create"]
    assert response.json()[0]["details"]["total"] == "1050.00"

    # история товара — отдельный журнал по своей сущности
    response = await client.get(f"/api/products/{product_id}/history", headers=owner_headers)
    assert response.status_code == 200
    assert [entry["action"] for entry in response.json()] == ["product.create"]
