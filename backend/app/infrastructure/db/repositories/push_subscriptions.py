from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.domain.notifications.push import (
    MAX_DEVICES_PER_USER,
    IPushSubscriptionRepository,
    PushSubscription,
)
from app.infrastructure.db.models.notifications import PushSubscriptionModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


def _to_entity(model: PushSubscriptionModel) -> PushSubscription:
    return PushSubscription(
        id=model.id,
        user_id=model.user_id,
        endpoint=model.endpoint,
        p256dh=model.p256dh,
        auth=model.auth,
        token_version=model.token_version,
        confirmed_at=model.confirmed_at,
    )


class SqlAlchemyPushSubscriptionRepository(SqlAlchemyRepository, IPushSubscriptionRepository):
    async def upsert(self, subscription: PushSubscription) -> PushSubscription:
        # одной командой: две вкладки кабинета подтверждают подписку одновременно,
        # и «SELECT, потом INSERT» упал бы на уникальности endpoint. Поиск без
        # фильтра по магазину: браузер мог быть подписан сотрудником другого
        # магазина — он уходит к тому, кто вошёл сейчас.
        values = {
            "tenant_id": self._tenant,
            "user_id": subscription.user_id,
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
            "token_version": subscription.token_version,
            "confirmed_at": func.now(),
        }
        stmt = (
            pg_insert(PushSubscriptionModel)
            .values(endpoint=subscription.endpoint, **values)
            .on_conflict_do_update(index_elements=[PushSubscriptionModel.endpoint], set_=values)
            .returning(PushSubscriptionModel.id, PushSubscriptionModel.confirmed_at)
        )
        saved_id, confirmed_at = (await self._session.execute(stmt)).one()

        stale_ids = (
            await self._session.execute(
                select(PushSubscriptionModel.id)
                .where(
                    PushSubscriptionModel.tenant_id == self._tenant,
                    PushSubscriptionModel.user_id == subscription.user_id,
                    PushSubscriptionModel.id != saved_id,
                )
                .order_by(PushSubscriptionModel.confirmed_at.desc(), PushSubscriptionModel.id.desc())
                .offset(MAX_DEVICES_PER_USER - 1)
            )
        ).scalars().all()
        if stale_ids:
            await self._session.execute(
                delete(PushSubscriptionModel).where(PushSubscriptionModel.id.in_(stale_ids))
            )
        await self._session.flush()

        subscription.id = saved_id
        subscription.confirmed_at = confirmed_at
        return subscription

    async def list_for_user(self, user_id: int) -> list[PushSubscription]:
        models = (
            await self._session.execute(
                select(PushSubscriptionModel)
                .where(
                    PushSubscriptionModel.tenant_id == self._tenant,
                    PushSubscriptionModel.user_id == user_id,
                )
                .order_by(PushSubscriptionModel.id)
            )
        ).scalars().all()
        return [_to_entity(m) for m in models]

    async def delete(self, subscription_id: int) -> None:
        await self._session.execute(
            delete(PushSubscriptionModel).where(
                PushSubscriptionModel.tenant_id == self._tenant,
                PushSubscriptionModel.id == subscription_id,
            )
        )
        await self._session.flush()

    async def delete_for_user(self, user_id: int, endpoint: str) -> bool:
        result = await self._session.execute(
            delete(PushSubscriptionModel).where(
                PushSubscriptionModel.tenant_id == self._tenant,
                PushSubscriptionModel.user_id == user_id,
                PushSubscriptionModel.endpoint == endpoint,
            )
        )
        await self._session.flush()
        return (result.rowcount or 0) > 0
