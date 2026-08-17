import { IconPhoto } from '@tabler/icons-react'

export function ProductPhoto({ src, size = 40 }: { src: string; size?: number }) {
  if (!src) {
    return (
      <div className="product-tile-photo product-tile-photo-empty">
        <IconPhoto size={size} stroke={1.5} />
      </div>
    )
  }
  return <img src={src} alt="" className="product-tile-photo" loading="lazy" />
}
