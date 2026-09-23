import { ExpandableText } from '../../../shared/ui/ExpandableText'
import pageStyles from './ProductPage.module.css'

/** «Гарантии» — тот же ExpandableText, первая строка жирная (как на wikkeo). Пусто → секция скрыта. */
export function WarrantySection({ warrantyText }: { warrantyText: string }) {
  const text = warrantyText?.trim()
  if (!text) return null

  return (
    <div className={pageStyles.card}>
      <ExpandableText title="Гарантии" text={text} boldFirstLine />
    </div>
  )
}
