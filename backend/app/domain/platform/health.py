"""Состояние магазина на платформе — «живой, затих или бросил».

Пороги собраны здесь, а не разбросаны по SQL и фронту: это продуктовое
решение, которое будет меняться по мере наблюдения за пилотом, и менять его
нужно в одном месте.
"""

from datetime import datetime, timedelta
from enum import StrEnum

# продажа была не дальше этого срока — магазин работает
ACTIVE_WITHIN = timedelta(days=3)
# продаж не было дольше этого срока — считаем, что магазин бросили
CHURNED_AFTER = timedelta(days=14)
# сколько у нового магазина есть времени на первую продажу, прежде чем
# он перестанет считаться «новым» и станет «бросил»
NEW_GRACE_PERIOD = timedelta(days=7)


class TenantHealth(StrEnum):
    NEW = "new"
    ACTIVE = "active"
    QUIET = "quiet"
    CHURNED = "churned"


def tenant_health(
    created_at: datetime, last_sale_at: datetime | None, now: datetime
) -> TenantHealth:
    """Состояние магазина по дате регистрации и последней продаже.

    Магазин без продаж: пока не вышел NEW_GRACE_PERIOD — NEW (ещё
    настраивается), после — CHURNED (неделю не может пробить ни одного чека).
    """
    if last_sale_at is None:
        return (
            TenantHealth.NEW
            if now - created_at < NEW_GRACE_PERIOD
            else TenantHealth.CHURNED
        )

    since_sale = now - last_sale_at
    if since_sale <= ACTIVE_WITHIN:
        return TenantHealth.ACTIVE
    if since_sale <= CHURNED_AFTER:
        return TenantHealth.QUIET
    return TenantHealth.CHURNED
