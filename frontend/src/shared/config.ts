/**
 * Общие константы публичных страниц ВайСклад (шапка, подвал).
 *
 * Подвал сейчас без ссылок: все его пункты вели на /marketplace-заглушку
 * (общая витрина отключена, см. MarketplaceComingSoonPage), а ссылка,
 * ведущая на «страницу в разработке», — тот же визуальный шум, что и пустой
 * пункт меню. Возвращать по мере появления реальных страниц: добавить сюда
 * колонку с href на готовый роут.
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
