import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../shared/ui/EmptyState'

/** Неизвестный адрес внутри кабинета (опечатка, старая ссылка) — раньше пустой экран. */
export function CabinetNotFoundPage() {
  const navigate = useNavigate()
  return (
    <EmptyState
      illustration="error-404-not-found"
      title="Такой страницы нет"
      description="Возможно, ссылка устарела или в адресе опечатка."
      actionLabel="К продажам"
      onAction={() => navigate('/')}
    />
  )
}
