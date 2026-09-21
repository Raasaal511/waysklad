import { EmptyState } from '../../shared/ui/EmptyState'
import styles from './MarketplaceComingSoonPage.module.css'

/**
 * Заглушка маркетплейса. Общая витрина всех магазинов платформы выключена
 * (backend: MARKETPLACE_ENABLED=false, /api/marketplace/* отдаёт 404), и ссылок
 * на неё в интерфейсе больше нет — но прямые заходы по сохранённым/расшаренным
 * /marketplace остаются, и им лучше показать понятную страницу, чем пустоту.
 * Без кнопки действия: вести покупателя некуда — "/" это кабинет владельца за
 * RequireAuth, а общей точки входа для покупателя пока нет.
 * Готовые страницы маркетплейса (MarketplacePage, MarketplaceShopsPage и
 * pages/marketplace/home/*) не удалены — вернуть их можно, поменяв роуты в
 * App.tsx обратно и включив флаг на backend.
 */
export function MarketplaceComingSoonPage() {
  return (
    <div className={styles.shell}>
      <EmptyState
        illustration="empty-box"
        title="Страница в разработке"
        description="Общий каталог всех магазинов ВайСклад пока в работе. Загляните позже — а сейчас откройте витрину нужного магазина по прямой ссылке."
      />
    </div>
  )
}
