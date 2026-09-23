import { ErrorState } from '../../shared/ui/ErrorState'
import styles from '../marketplace/MarketplaceComingSoonPage.module.css'

/** Старые ссылки /marketplace* — страница «Не найдено», без ссылок на платформу. */
export function PublicNotFoundPage() {
  return (
    <div className={styles.shell}>
      <ErrorState
        illustration="error-404-not-found"
        title="Страница не найдена"
        description="Такой страницы нет. Откройте витрину магазина по прямой ссылке."
      />
    </div>
  )
}
