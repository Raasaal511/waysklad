import { forwardRef, type ButtonHTMLAttributes } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ink' | 'accent-outline'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  active?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', active, className, type = 'button', ...rest },
  ref,
) {
  const classes = ['btn', `btn-${variant}`]
  if (active) classes.push('btn-active')
  if (className) classes.push(className)

  return <button ref={ref} type={type} className={classes.join(' ')} {...rest} />
})
