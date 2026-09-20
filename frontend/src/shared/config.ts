/**
 * Общие константы публичных страниц ВайСклад (шапка, подвал).
 * Часть путей в подвале ещё не реализована как отдельные страницы —
 * пока ведут на /marketplace (см. PublicFooter).
 */

export const MARKETPLACE_PATH = '/marketplace'

/** Ссылки подвала. href === MARKETPLACE_PATH — страница ещё не создана, заглушка. */
export interface FooterLink {
  label: string
  href: string
}

export interface FooterColumn {
  title: string
  links: FooterLink[]
}

export const FOOTER_COLUMNS: FooterColumn[] = [
  {
    title: 'О ВайСклад',
    links: [
      { label: 'О сервисе', href: MARKETPLACE_PATH },
      { label: 'Как это работает', href: MARKETPLACE_PATH },
    ],
  },
  {
    title: 'Покупателям',
    links: [
      { label: 'Все магазины', href: MARKETPLACE_PATH },
      { label: 'Как оформить заявку', href: MARKETPLACE_PATH },
    ],
  },
  {
    title: 'Продавцам',
    links: [
      { label: 'Открыть магазин', href: MARKETPLACE_PATH },
      { label: 'Тарифы', href: MARKETPLACE_PATH },
    ],
  },
  {
    title: 'Контакты',
    links: [
      { label: 'Поддержка', href: MARKETPLACE_PATH },
      { label: 'Написать в Telegram', href: MARKETPLACE_PATH },
    ],
  },
]
