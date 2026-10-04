// Без 0/O, 1/l/I: пароль диктуют по телефону и переписывают с экрана.
const ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'

/** Пароль сотрудника вида «k7mx-p2qa»: 8 случайных символов (~40 бит) —
 *  достаточно для входа в кабинет и легко продиктовать. */
export function generatePassword(): string {
  const bytes = new Uint32Array(8)
  crypto.getRandomValues(bytes)
  const chars = Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length])
  return `${chars.slice(0, 4).join('')}-${chars.slice(4).join('')}`
}
