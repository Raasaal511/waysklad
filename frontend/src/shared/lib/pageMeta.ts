/** Обновляет title и базовые meta для вкладки браузера.
 *  Для превью в WhatsApp/Telegram нужен серверный OG (nginx → /api/.../og). */
export function setPageMeta(opts: { title: string; description?: string }) {
  document.title = opts.title
  const ensure = (selector: string, create: () => HTMLMetaElement) => {
    let el = document.head.querySelector(selector) as HTMLMetaElement | null
    if (!el) {
      el = create()
      document.head.appendChild(el)
    }
    return el
  }
  if (opts.description) {
    ensure('meta[name="description"]', () => {
      const m = document.createElement('meta')
      m.setAttribute('name', 'description')
      return m
    }).content = opts.description
  }
}

export function resetPageMeta(defaultTitle = 'WaySklad') {
  document.title = defaultTitle
}
