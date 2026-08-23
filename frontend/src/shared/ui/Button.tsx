import { forwardRef, type ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ink' | 'accent-outline'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  active?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', active, className, type = 'button', ...rest },
  ref,
) {
  // 'btn' — маркерный класс без собственных стилей (базовые стили кнопки
  // заданы глобально для тега <button> в index.css), оставлен как есть.
  const classes = ['btn', styles[`btn-${variant}`]]
  if (active) classes.push(styles['btn-active'])
  if (className) classes.push(className)

  return <button ref={ref} type={type} className={classes.join(' ')} {...rest} />
})
