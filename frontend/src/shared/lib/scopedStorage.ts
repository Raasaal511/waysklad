/** Данные о работе с конкретным магазином (черновики продаж/приёмки, корзины
 * дозаказа и т.п.) не должны быть видны другому аккаунту на этом же
 * устройстве — id пользователя уникален по всей системе (одна запись = один
 * человек в одной конкретной компании: логин по телефону уникален глобально,
 * а сотрудник в другой компании — это отдельная запись со своим id), поэтому
 * им же скоупим ключи localStorage: два разных логина на одном браузере
 * физически не пересекаются в хранимых данных, даже без выхода из аккаунта
 * (краш вкладки, истёкший токен, общий компьютер на складе).
 *
 * Не используем React-контекст здесь специально — вызывается и из мест без
 * доступа к AuthContext (например при самом logout()). */
function currentUserId(): number | null {
  try {
    const raw = localStorage.getItem('user') ?? sessionStorage.getItem('user')
    if (!raw) return null
    const user = JSON.parse(raw) as { id?: number }
    return typeof user.id === 'number' ? user.id : null
  } catch {
    return null
  }
}

/** `'sale-draft'` → `'waysklad:u42:sale-draft'`. Без залогиненного пользователя
 * (id неизвестен) использует `'anon'` — этот сценарий не должен успеть что-то
 * сохранить до логина, но не должен и падать. */
export function scopedKey(baseKey: string): string {
  const userId = currentUserId()
  return `waysklad:u${userId ?? 'anon'}:${baseKey}`
}

/** Удаляет scoped-ключи данного baseKey для ЛЮБОГО пользователя, когда-либо
 * логинившегося на этом устройстве — используется при logout() как подчистка
 * (полагаться на неё как на единственную защиту не нужно: scopedKey уже
 * гарантирует изоляцию между аккаунтами сам по себе), плюс подчищает значения,
 * оставшиеся от версии кода без скоупинга (голый 'waysklad:sale-draft'). */
export function clearAllScoped(baseKey: string): void {
  try {
    localStorage.removeItem(`waysklad:${baseKey}`)
    const suffix = `:${baseKey}`
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('waysklad:u') && key.endsWith(suffix)) localStorage.removeItem(key)
    }
  } catch {
    // ignore
  }
}
