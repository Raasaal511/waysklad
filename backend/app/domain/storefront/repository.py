from datetime import date, datetime
from typing import Protocol

from app.domain.storefront.entities import StorefrontMessage, StorefrontRequest


class IStorefrontRequestRepository(Protocol):
    async def add(self, request: StorefrontRequest) -> StorefrontRequest: ...
    async def save(self, request: StorefrontRequest) -> StorefrontRequest: ...
    async def get(self, request_id: int) -> StorefrontRequest: ...
    async def get_by_token(self, access_token: str) -> StorefrontRequest | None: ...
    async def list_new(self) -> list[StorefrontRequest]: ...
    async def count_new_by_phone(self, phone: str) -> int:
        """Сколько ещё не обработанных (status=new) заявок с этим телефоном
        уже есть у этого магазина — защита от заспамливания списка заявок."""
        ...

    async def list_stale_reserved(self, older_than: datetime) -> list[StorefrontRequest]:
        """NEW-заявки старше older_than с ещё не снятым резервом — кандидаты
        на авто-освобождение резерва (см. release_expired_storefront_reservations)."""
        ...

    async def list_by_customer(self, customer_id: int) -> list[StorefrontRequest]:
        """Все заявки покупателя во ВСЕХ магазинах платформы — без tenant-
        фильтра (Customer не привязан к одному tenant), новые сначала.
        Каждая StorefrontRequest.tenant_id заполнен (нужен для отображения,
        к какому магазину относится заявка)."""
        ...


class IStorefrontMessageRepository(Protocol):
    async def add(self, message: StorefrontMessage) -> StorefrontMessage: ...
    async def list_by_request(self, request_id: int) -> list[StorefrontMessage]: ...


class IProductViewRepository(Protocol):
    async def record_view(self, product_id: int, day: date) -> None:
        """Инкремент дневного счётчика (upsert) — дедупликация по IP уже
        сделана вызывающим use case через Redis, сюда попадают только
        засчитанные просмотры."""
        ...

    async def views_since(self, product_id: int, since: date) -> int:
        """Сумма count за дни >= since (включительно) — для views_90d."""
        ...
