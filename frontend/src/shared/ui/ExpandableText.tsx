import { useEffect, useRef, useState, type ReactNode } from 'react'
import styles from './ExpandableText.module.css'

const URL_RE = /(https?:\/\/[^\s]+)/g

/** Разбивает текст на фрагменты, оборачивая http(s)-ссылки в <a> — без dangerouslySetInnerHTML. */
function linkify(text: string): ReactNode[] {
  const parts = text.split(URL_RE)
  return parts.map((part, i) => {
    if (part.match(URL_RE)) {
      return (
        <a key={i} href={part} target="_blank" rel="noopener nofollow">
          {part}
        </a>
      )
    }
    return part
  })
}

interface ExpandableTextProps {
  title?: string
  text: string
  extra?: ReactNode
  titleAs?: 'h2' | 'h3'
  boldFirstLine?: boolean
}

/**
 * Общий компонент «О товаре» / «Гарантии»: заголовок секции, текст с переносами и
 * кликабельными ссылками, обрезка до 3 строк с «Читать полностью» / «Свернуть» —
 * кнопка показывается, только если текст реально обрезан (scrollHeight > clientHeight).
 */
export function ExpandableText({ title, text, extra, titleAs = 'h2', boldFirstLine }: ExpandableTextProps) {
  const [expanded, setExpanded] = useState(false)
  const [clampable, setClampable] = useState(false)
  const textRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    function check() {
      const el = textRef.current
      if (!el) return
      // временно снимаем clamp, чтобы измерить полную высоту
      const wasClamped = el.classList.contains(styles.clamped)
      if (wasClamped) el.classList.remove(styles.clamped)
      const full = el.scrollHeight
      if (wasClamped) el.classList.add(styles.clamped)
      const clampedHeight = el.clientHeight
      setClampable(!expanded && full > clampedHeight + 1)
    }
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [text, expanded])

  const Title = titleAs

  let body: ReactNode
  if (boldFirstLine) {
    const newlineIndex = text.indexOf('\n')
    const firstLine = newlineIndex === -1 ? text : text.slice(0, newlineIndex)
    const rest = newlineIndex === -1 ? '' : text.slice(newlineIndex)
    body = (
      <>
        <strong>{linkify(firstLine)}</strong>
        {linkify(rest)}
      </>
    )
  } else {
    body = linkify(text)
  }

  return (
    <div>
      {title && <Title className={styles.title}>{title}</Title>}
      <p ref={textRef} className={expanded ? styles.text : `${styles.text} ${styles.clamped}`}>
        {body}
      </p>
      {(clampable || expanded) && (
        <button type="button" className={styles.toggle} onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Свернуть' : 'Читать полностью'}
        </button>
      )}
      {extra}
    </div>
  )
}
