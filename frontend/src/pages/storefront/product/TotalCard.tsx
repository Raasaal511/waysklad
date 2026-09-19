import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconCheck, IconMessageCircle, IconBrandWhatsapp, IconBrandTelegram, IconPhone } from '@tabler/icons-react'
import { Button } from '../../../shared/ui/Button'
import { formatMoney, plural } from '../../../shared/lib/format'
import type { StorefrontProfileContacts } from '../../../entities/storefront/api'
import pageStyles from './ProductPage.module.css'
import styles from './ProductAside.module.css'

interface TotalCardProps {
  slug: string
  total: number
  linesCount: number
  totalQty: number
  inStock: boolean
  added: boolean
  onAdd: () => void
  cartQtyInShop: number
  contacts?: StorefrontProfileContacts
  productName: string
}

/**
 * «Итого» — покупатель формирует заказ (кнопка «В корзину», затем «Оформить заказ» в корзине).
 * Термин «заявка» здесь сознательно не используется — это внутреннее название механики
 * для владельца магазина, для покупателя это обычный заказ, как на маркетплейсах.
 */
export function TotalCard({
  slug,
  total,
  linesCount,
  totalQty,
  inStock,
  added,
  onAdd,
  cartQtyInShop,
  contacts,
  productName,
}: TotalCardProps) {
  const [contactOpen, setContactOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!contactOpen) return
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setContactOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [contactOpen])

  const hasContacts = contacts && (contacts.phone || contacts.whatsapp || contacts.telegram)
  const pageUrl = typeof window !== 'undefined' ? window.location.href : ''
  const messageText = `Здравствуйте! Вопрос по товару ${productName} ${pageUrl}`

  return (
    <div className={pageStyles.card}>
      <p className={styles.totalLabel}>Итого:</p>
      <p className={styles.totalValue}>{formatMoney(total.toFixed(2))} ₽</p>
      {linesCount > 0 && (
        <p className={styles.totalCount}>
          {totalQty} {plural(totalQty, ['товар', 'товара', 'товаров'])}
        </p>
      )}

      <div className={styles.actions}>
        <Button className={styles.addBtn} onClick={onAdd} disabled={!inStock}>
          {!inStock ? (
            'Нет в наличии'
          ) : added ? (
            <>
              <IconCheck size={18} stroke={2} /> Добавлено
            </>
          ) : (
            'В корзину'
          )}
        </Button>

        {hasContacts && (
          <div className={styles.contactWrap} ref={wrapRef}>
            <button
              type="button"
              className={styles.contactBtn}
              onClick={() => setContactOpen((v) => !v)}
              aria-expanded={contactOpen}
            >
              <IconMessageCircle size={18} stroke={1.8} />
              Написать
            </button>
            {contactOpen && (
              <div className={styles.contactSheet} role="menu">
                {contacts?.whatsapp && (
                  <a
                    className={styles.contactSheetItem}
                    role="menuitem"
                    href={`https://wa.me/${contacts.whatsapp.replace(/\D/g, '')}?text=${encodeURIComponent(messageText)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <IconBrandWhatsapp size={18} stroke={1.8} /> WhatsApp
                  </a>
                )}
                {contacts?.telegram && (
                  <a
                    className={styles.contactSheetItem}
                    role="menuitem"
                    href={`https://t.me/${contacts.telegram}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <IconBrandTelegram size={18} stroke={1.8} /> Telegram
                  </a>
                )}
                {contacts?.phone && (
                  <a className={styles.contactSheetItem} role="menuitem" href={`tel:${contacts.phone}`}>
                    <IconPhone size={18} stroke={1.8} /> Позвонить
                  </a>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {cartQtyInShop > 0 && (
        <p className={styles.inCartRow}>
          В корзине: {cartQtyInShop} шт
          <Link to={`/store/${slug}/cart`} className={styles.inCartLink}>
            Перейти
          </Link>
        </p>
      )}

      <p className={styles.deliveryHint}>Самовывоз или доставка магазина</p>
    </div>
  )
}
