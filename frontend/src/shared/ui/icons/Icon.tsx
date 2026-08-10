import type { ReactElement, SVGProps } from 'react'

export type IconName =
  | 'sale'
  | 'products'
  | 'stock'
  | 'orders'
  | 'debts'
  | 'clients'
  | 'employees'
  | 'analytics'
  | 'barcode'
  | 'settings'
  | 'close'
  | 'check'
  | 'filter'
  | 'chevronLeft'
  | 'chevronRight'
  | 'chevronDown'
  | 'plus'
  | 'calendar'

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName
  size?: number
}

const PATHS: Record<IconName, ReactElement> = {
  sale: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a4 4 0 0 1 8 0v2" />
      <path d="M3 11h18" />
    </>
  ),
  products: (
    <>
      <path d="M21 8 12 3 3 8l9 5 9-5Z" />
      <path d="M3 8v8l9 5 9-5V8" />
      <path d="M12 13v8" />
    </>
  ),
  stock: (
    <>
      <path d="M3 9 12 4l9 5v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1Z" />
    </>
  ),
  orders: (
    <>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M9 3v3h6V3" />
      <path d="M8 11h8M8 15h5" />
    </>
  ),
  debts: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v10M15 9.5c0-1.4-1.3-2.5-3-2.5s-3 1-3 2.3c0 3.2 6 1.6 6 4.7 0 1.4-1.3 2.5-3 2.5s-3-1.1-3-2.5" />
    </>
  ),
  clients: (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 20c0-3.3 2.6-6 6-6h0c1.6 0 3.1.6 4.2 1.8" />
      <circle cx="17" cy="9.5" r="2.6" />
      <path d="M14.5 14c2.9.3 5 2.6 5 5.6" />
    </>
  ),
  employees: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <circle cx="9" cy="11" r="2.1" />
      <path d="M5.5 16.5c0-1.9 1.6-3 3.5-3s3.5 1.1 3.5 3" />
      <path d="M14.5 9.5h4M14.5 13h4" />
    </>
  ),
  analytics: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </>
  ),
  barcode: (
    <>
      <path d="M4 5v14M8 5v14M11 5v14M13 5v14M16 5v14M20 5v14" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 13.5a1.7 1.7 0 0 0 .34 1.87l.06.06a2.05 2.05 0 1 1-2.9 2.9l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V19.6a2.05 2.05 0 1 1-4.1 0v-.1a1.7 1.7 0 0 0-1.1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2.05 2.05 0 1 1-2.9-2.9l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H4.4a2.05 2.05 0 1 1 0-4.1h.1a1.7 1.7 0 0 0 1.55-1.1 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2.05 2.05 0 1 1 2.9-2.9l.06.06a1.7 1.7 0 0 0 1.87.34h.06A1.7 1.7 0 0 0 11.5 4.4V4.3a2.05 2.05 0 1 1 4.1 0v.1a1.7 1.7 0 0 0 1 1.55h.06a1.7 1.7 0 0 0 1.87-.34l.06-.06a2.05 2.05 0 1 1 2.9 2.9l-.06.06a1.7 1.7 0 0 0-.34 1.87v.06a1.7 1.7 0 0 0 1.55 1h.1a2.05 2.05 0 1 1 0 4.1h-.1a1.7 1.7 0 0 0-1.55 1Z" />
    </>
  ),
  close: (
    <>
      <path d="M6 6l12 12M18 6 6 18" />
    </>
  ),
  check: (
    <>
      <path d="M5 12.5 10 17 19 7" />
    </>
  ),
  filter: (
    <>
      <path d="M4 5h16M7 12h10M10 19h4" />
    </>
  ),
  chevronLeft: (
    <>
      <path d="M15 6l-6 6 6 6" />
    </>
  ),
  chevronRight: (
    <>
      <path d="M9 6l6 6-6 6" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  chevronDown: (
    <>
      <path d="M6 9l6 6 6-6" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </>
  ),
}

export function Icon({ name, size = 20, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  )
}
