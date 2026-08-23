import { useState, type FormEvent, type ReactNode } from 'react'
import { createClient, type Client } from '../../entities/counterparty/api'
import { ApiError } from '../api/client'
import { Button } from './Button'
import { InlinePopover } from './InlinePopover'
import { PhoneInput } from './PhoneInput'

export function QuickNewClientForm({
  open,
  onOpenChange,
  trigger,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  trigger: ReactNode
  onCreated: (client: Client) => void
}) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    e.stopPropagation()
    setError(null)
    setSaving(true)
    try {
      const client = await createClient({ name, phone })
      setName('')
      setPhone('')
      onCreated(client)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить клиента')
    } finally {
      setSaving(false)
    }
  }

  return (
    <InlinePopover title="Новый клиент" trigger={trigger} open={open} onOpenChange={onOpenChange}>
      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          Имя
          <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        </label>
        <label className="field">
          Телефон
          <PhoneInput value={phone} onChange={setPhone} />
        </label>
        {error && <p className="error">{error}</p>}
        <Button type="submit" disabled={saving || !name.trim()}>
          {saving ? 'Сохранение…' : 'Добавить и выбрать'}
        </Button>
      </form>
    </InlinePopover>
  )
}
