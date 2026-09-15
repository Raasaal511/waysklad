import type { ReactNode } from 'react'
import styles from './Avatar.module.css'

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

export interface AvatarProps {
  name?: string | null
  icon?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  variant?: 'accent' | 'muted'
  title?: string
  className?: string
}

/** Круглая плашка с инициалами (или переданной иконкой, если имени нет). */
export function Avatar({ name, icon, size = 'sm', variant = 'accent', title, className }: AvatarProps) {
  const classes = [styles.avatar, styles[`avatar-${size}`], styles[`avatar-${variant}`]]
  if (className) classes.push(className)
  return (
    <span className={classes.join(' ')} title={title}>
      {name ? initials(name) : icon}
    </span>
  )
}
