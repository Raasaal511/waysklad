import { EmptyState } from '../../shared/ui/EmptyState'
import styles from '../marketplace/MarketplaceComingSoonPage.module.css'

/** Старые ссылки /marketplace* — страница «Не найдено», без ссылок на платформу. */
export function PublicNotFoundPage() {
  return (
    <div className={styles.shell}>
      <EmptyState
        illustration="error-404-not-found"
        title="Страница не найдена"
        description="Такой страницы нет. Откройте витрину магазина по прямой ссылке."
      />
    </div>
  )
}
