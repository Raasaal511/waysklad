import { useEffect, useRef, useState } from 'react'
import {
  BrowserMultiFormatReader,
  BarcodeFormat,
  DecodeHintType,
  NotFoundException,
} from '@zxing/library'
import { Button } from '../../shared/ui/Button'

function describeCameraError(err: unknown): string {
  if (err instanceof DOMException) {
    switch (err.name) {
      case 'NotFoundError':
      case 'OverconstrainedError':
        return 'На устройстве не найдена подходящая камера'
      case 'NotAllowedError':
      case 'SecurityError':
        return 'Доступ к камере запрещён — разрешите его в настройках браузера'
      case 'NotReadableError':
        return 'Камера занята другим приложением'
      default:
        return 'Нет доступа к камере'
    }
  }
  return 'Нет доступа к камере'
}

const hints = new Map()
hints.set(DecodeHintType.POSSIBLE_FORMATS, [
  BarcodeFormat.EAN_13,
  BarcodeFormat.EAN_8,
  BarcodeFormat.CODE_128,
  BarcodeFormat.CODE_39,
  BarcodeFormat.UPC_A,
  BarcodeFormat.UPC_E,
  BarcodeFormat.QR_CODE,
])

export function BarcodeScanner({
  onDetected,
  onClose,
}: {
  onDetected: (code: string) => void
  onClose: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stream: MediaStream | null = null
    let cancelled = false
    const reader = new BrowserMultiFormatReader(hints)

    async function start() {
      if (!window.isSecureContext) {
        setError('Камера доступна только по HTTPS — откройте сайт по защищённому адресу')
        return
      }

      if (!navigator.mediaDevices?.getUserMedia) {
        setError('Этот браузер не поддерживает доступ к камере')
        return
      }

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        if (!videoRef.current) return

        await reader.decodeFromStream(stream, videoRef.current, (result, err) => {
          if (cancelled) return
          if (result) {
            onDetected(result.getText())
            return
          }
          if (err && !(err instanceof NotFoundException)) {
            // NotFoundException — обычный "кадр без штрихкода", остальное логируем молча
          }
        })
      } catch (err) {
        setError(describeCameraError(err))
      }
    }

    start()

    return () => {
      cancelled = true
      reader.reset()
      stream?.getTracks().forEach((t) => t.stop())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="stack">
      {error ? (
        <p className="error">{error}</p>
      ) : (
        <video ref={videoRef} className="barcode-scanner-video" muted playsInline />
      )}
      <Button variant="secondary" onClick={onClose}>
        Отмена
      </Button>
    </div>
  )
}
