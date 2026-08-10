import { forwardRef, type ButtonHTMLAttributes } from 'react'

export type IconButtonVariant = 'danger' | 'muted' | 'accent'

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: IconButtonVariant
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { variant = 'danger', className, type = 'button', ...rest },
  ref,
) {
  const classes = ['icon-button', `icon-button-${variant}`]
  if (className) classes.push(className)

  return <button ref={ref} type={type} className={classes.join(' ')} {...rest} />
})
