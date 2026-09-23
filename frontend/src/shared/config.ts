/**
 * Общие константы публичных страниц ВайСклад (шапка, подвал).
 *
 * Подвал магазина собирается в PublicFooter из профиля витрины.
 * FOOTER_COLUMNS оставлен пустым на случай возврата маркетплейса.
 */

export interface FooterLink {
  label: string
  href: string
}

export interface FooterColumn {
  title: string
  links: FooterLink[]
}

export const FOOTER_COLUMNS: FooterColumn[] = []
