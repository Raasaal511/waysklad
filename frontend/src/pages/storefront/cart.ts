const CART_KEY = 'waysklad:storefront-cart'

export interface StorefrontCartItem {
  product_id: number
  name: string
  retail_price: string
  photo: string
  quantity: string
  variant_id: number | null
  variant_label?: string
  /** Минимум и шаг заказа товара — степпер корзины считает по тем же правилам,
   *  что страница товара и сервер. У старых строк корзины их нет: тогда ±1. */
  min_order_qty?: string | null
  order_step_qty?: string | null
}

export function loadCart(slug: string): StorefrontCartItem[] {
  try {
    const raw = localStorage.getItem(`${CART_KEY}:${slug}`)
    return raw ? (JSON.parse(raw) as StorefrontCartItem[]) : []
  } catch {
    return []
  }
}

export function saveCart(slug: string, items: StorefrontCartItem[]) {
  localStorage.setItem(`${CART_KEY}:${slug}`, JSON.stringify(items))
  window.dispatchEvent(new Event('waysklad:storefront-cart'))
}

export function cartCount(items: StorefrontCartItem[]) {
  return items.reduce((sum, i) => sum + Number(i.quantity || 0), 0)
}

export function addToCart(slug: string, item: StorefrontCartItem) {
  const cart = loadCart(slug)
  const idx = cart.findIndex(
    (c) => c.product_id === item.product_id && c.variant_id === item.variant_id,
  )
  if (idx >= 0) {
    cart[idx] = {
      ...cart[idx],
      min_order_qty: item.min_order_qty ?? cart[idx].min_order_qty,
      order_step_qty: item.order_step_qty ?? cart[idx].order_step_qty,
      quantity: String(Number(cart[idx].quantity) + Number(item.quantity)),
    }
  } else {
    cart.push(item)
  }
  saveCart(slug, cart)
  return cart
}
