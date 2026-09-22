/** Событие смены сессии покупателя — шапка/счётчики и страницы витрины слушают его. */
export function notifyCustomerAuthChanged() {
  window.dispatchEvent(new Event('waysklad:customer-auth'))
}
