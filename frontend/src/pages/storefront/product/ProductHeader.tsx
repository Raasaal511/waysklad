import { useEffect, useRef, useState } from 'react'
import { IconCopy, IconShare, IconBrandWhatsapp, IconBrandTelegram, IconLink } from '@tabler/icons-react'
import type { StorefrontProductDetail } from '../../../entities/storefront/api'
import { StarRating } from '../../../shared/ui/StarRating'
import { formatMoney, formatQuantity, plural } from '../../../shared/lib/format'
import { priceRange } from './productUtils'
import styles from './ProductPage.module.css'

interface ProductHeaderProps {
  product: StorefrontProductDetail
  selectedPrice: string | null
}

function useToast() {
  const [message, setMessage] = useState<{ text: string; link?: { href: string; label: string } } | null>(null)
  const timer = useRef<number | null>(null)

  function show(text: string, link?: { href: string; label: string }) {
    setMessage({ text, link })
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMessage(null), 2400)
  }

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current)
  }, [])

  return { message, show }
}

export function ProductHeader({ product, selectedPrice }: ProductHeaderProps) {
  const [sharing, setSharing] = useState(false)
  const shareRef = useRef<HTMLDivElement>(null)
  const { message, show } = useToast()

  useEffect(() => {
    if (!sharing) return
    function onDocClick(e: MouseEvent) {
      if (shareRef.current && !shareRef.current.contains(e.target as Node)) setSharing(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [sharing])

  const range = priceRange(product)
  const url = typeof window !== 'undefined' ? window.location.href : ''

  function copyLink() {
    navigator.clipboard?.writeText(url).then(() => show('Ссылка скопирована'))
    setSharing(false)
  }

  async function handleShare() {
    if (navigator.share) {
      try {
        await navigator.share({ title: product.name, url })
      } catch {
        // пользователь отменил — ничего не делаем
      }
      return
    }
    setSharing((v) => !v)
  }

  function copySku() {
    if (!product.sku) return
    navigator.clipboard?.writeText(product.sku).then(() => show('Артикул скопирован'))
  }

  const reviewsLabel =
    product.reviews_count > 0
      ? `${product.reviews_count} ${plural(product.reviews_count, ['отзыв', 'отзыва', 'отзывов'])}`
      : 'Нет отзывов'

  const priceNode = range.sameForAll ? (
    <p className={styles.headerPrice}>
      {formatMoney(selectedPrice ?? product.retail_price)} ₽
      <span className={styles.headerPriceUnit}>за {product.unit_label || 'шт'}</span>
    </p>
  ) : (
    <p className={styles.headerPrice}>
      {selectedPrice ? `${formatMoney(selectedPrice)} ₽` : `от ${formatMoney(range.min)} ₽`}
      <span className={styles.headerPriceUnit}>за {product.unit_label || 'шт'}</span>
    </p>
  )

  return (
    <div>
      {priceNode}
      <h1 className={styles.headerTitle}>{product.name}</h1>
      <div className={styles.headerMeta}>
        {product.reviews_count > 0 && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <StarRating value={product.average_rating} size={14} />
          </span>
        )}
        <a href="#reviews" className={styles.headerMetaLink}>
          {reviewsLabel}
        </a>
        {Number(product.sold_count ?? 0) > 0 && (
          <>
            <span className={styles.headerMetaSep}>·</span>
            <span>Продано {formatQuantity(product.sold_count!)}</span>
          </>
        )}
        {product.sku && (
          <>
            <span className={styles.headerMetaSep}>·</span>
            <button type="button" className={styles.headerSku} onClick={copySku} aria-label="Скопировать артикул">
              <IconCopy size={13} stroke={1.8} />
              арт. {product.sku}
            </button>
          </>
        )}
        <span className={styles.headerMetaSep}>·</span>
        <div style={{ position: 'relative' }} ref={shareRef}>
          <button type="button" className={styles.shareBtn} onClick={handleShare} aria-label="Поделиться">
            <IconShare size={14} stroke={1.8} />
            Поделиться
          </button>
          {sharing && (
            <div className={styles.sharePopover} role="menu">
              <button type="button" className={styles.sharePopoverItem} role="menuitem" onClick={copyLink}>
                <IconLink size={16} stroke={1.8} /> Скопировать ссылку
              </button>
              <a
                className={styles.sharePopoverItem}
                role="menuitem"
                href={`https://wa.me/?text=${encodeURIComponent(url)}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setSharing(false)}
              >
                <IconBrandWhatsapp size={16} stroke={1.8} /> WhatsApp
              </a>
              <a
                className={styles.sharePopoverItem}
                role="menuitem"
                href={`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(product.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setSharing(false)}
              >
                <IconBrandTelegram size={16} stroke={1.8} /> Telegram
              </a>
            </div>
          )}
        </div>
      </div>
      {message && (
        <div className={styles.toast} role="status">
          {message.text}
          {message.link && (
            <a className={styles.toastLink} href={message.link.href}>
              {message.link.label}
            </a>
          )}
        </div>
      )}
    </div>
  )
}
