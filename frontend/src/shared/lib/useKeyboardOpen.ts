import { useEffect } from 'react'

/** Типы input, для которых телефон не показывает текстовую клавиатуру. */
const NO_KEYBOARD_TYPES = new Set([
  'checkbox',
  'radio',
  'range',
  'file',
  'color',
  'button',
  'submit',
  'reset',
  'image',
])

/** Клавиатура заметно ниже этого порога не бывает, а панель адреса браузера — меньше его. */
const KEYBOARD_MIN_HEIGHT = 120

function isTextField(el: Element | null): boolean {
  if (el instanceof HTMLTextAreaElement) return !el.readOnly
  if (el instanceof HTMLInputElement) return !el.readOnly && !NO_KEYBOARD_TYPES.has(el.type)
  return el instanceof HTMLElement && el.isContentEditable
}

/**
 * Ставит `<html data-keyboard="open">`, пока на телефоне открыта экранная клавиатура:
 * фокус в текстовом поле и видимая высота заметно меньше полной. Ловит оба поведения
 * браузеров — когда клавиатура сжимает окно (WebView, в т.ч. Telegram, Firefox) и когда
 * только перекрывает его (Chrome, Safari). По флагу CSS убирает прилипшие к низу нижнее
 * меню и панель продажи — иначе на сжатом окне они закрывают поле ввода.
 */
export function useKeyboardOpen(): void {
  useEffect(() => {
    const root = document.documentElement
    const vv = window.visualViewport
    let width = window.innerWidth
    let fullHeight = window.innerHeight
    let frame = 0

    function update() {
      frame = 0
      // Поворот экрана меняет «полную» высоту — меряем заново.
      if (window.innerWidth !== width) {
        width = window.innerWidth
        fullHeight = window.innerHeight
      }
      fullHeight = Math.max(fullHeight, window.innerHeight)
      // height × scale — чтобы увеличение щипком не принималось за клавиатуру.
      const visible = Math.min(window.innerHeight, vv ? vv.height * vv.scale : window.innerHeight)
      const open = isTextField(document.activeElement) && fullHeight - visible > KEYBOARD_MIN_HEIGHT
      if (open) root.dataset.keyboard = 'open'
      else delete root.dataset.keyboard
    }

    // focusout приходит до смены activeElement — проверяем на следующем кадре.
    function schedule() {
      if (!frame) frame = requestAnimationFrame(update)
    }

    window.addEventListener('resize', schedule)
    vv?.addEventListener('resize', schedule)
    document.addEventListener('focusin', schedule)
    document.addEventListener('focusout', schedule)
    return () => {
      if (frame) cancelAnimationFrame(frame)
      window.removeEventListener('resize', schedule)
      vv?.removeEventListener('resize', schedule)
      document.removeEventListener('focusin', schedule)
      document.removeEventListener('focusout', schedule)
      delete root.dataset.keyboard
    }
  }, [])
}
