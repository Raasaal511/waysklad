import { IconX } from '@tabler/icons-react'
import { Button, type ButtonProps } from './Button'

/** Единая кнопка «Сбросить» для панелей фильтров — показывать только когда есть что сбрасывать. */
export function ResetFiltersButton({ className, children, ...rest }: ButtonProps) {
  return (
    <Button variant="secondary" className={`reset-filters-button${className ? ` ${className}` : ''}`} {...rest}>
      <IconX size={12} stroke={1.8} /> {children ?? 'Сбросить'}
    </Button>
  )
}
