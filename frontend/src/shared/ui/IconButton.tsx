import { forwardRef, type ButtonHTMLAttributes } from 'react'

export type IconButtonVariant = 'danger' | 'muted' | 'accent' | 'neutral'
export type IconButtonSize = 'md' | 'lg'

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: IconButtonVariant
  size?: IconButtonSize
  tooltip?: string
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { variant = 'danger', size = 'md', tooltip, className, type = 'button', ...rest },
  ref,
) {
  const classes = ['icon-button', `icon-button-${variant}`]
  if (size === 'lg') classes.push('icon-button-lg')
  if (tooltip) classes.push('has-hint')
  if (className) classes.push(className)

  return (
    <button
      ref={ref}
      type={type}
      className={classes.join(' ')}
      data-hint={tooltip}
      {...rest}
    />
  )
})
