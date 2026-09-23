import { useShop } from '../../app/ShopContext'

type Feature = 'storefront'

/**
 * Единая точка проверки видимости функциональности в кабинете владельца,
 * управляемой существующими флагами Tenant (сейчас — только storefront,
 * Tenant.storefront_enabled). Значения полей формы товара/склада при
 * выключенном флаге НЕ затираются — компоненты просто не рендерят блок,
 * PUT/POST по-прежнему уходит с тем, что было в data. Публичные маршруты
 * (/store/:slug) этот хук не проверяет — они не завязаны
 * на кабинет владельца и не должны использоваться в этом контексте.
 */
export function useFeature(feature: Feature): boolean {
  const { shop } = useShop()
  if (feature === 'storefront') {
    // shop === null, пока профиль не загрузился впервые (см. ShopContext) —
    // на это мгновение считаем витрину скрытой (не показываем лишнее до
    // загрузки, чем на секунду мигаем полной формой), включённый флаг
    // появится сразу после refreshShop() без перезагрузки страницы.
    return shop?.storefront_enabled ?? false
  }
  return false
}
