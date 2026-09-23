import { Link } from 'react-router-dom'
import { PersonalDataNotice } from '../../shared/ui/PersonalDataNotice'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { useEffect } from 'react'
import styles from '../auth/LoginPage.module.css'

/** Публичная страница: обработка телефона (152-ФЗ). */
export function PrivacyPage() {
  useEffect(() => {
    setPageMeta({ title: 'Обработка персональных данных — ВайСклад' })
    return () => resetPageMeta()
  }, [])

  return (
    <div className={styles['auth-screen']}>
      <div className={styles['auth-card']} style={{ maxWidth: 560, textAlign: 'left' }}>
        <h1 className={styles['auth-title']} style={{ fontSize: 22 }}>
          Обработка персональных данных
        </h1>
        <p className={styles['auth-subtitle']}>Телефон при регистрации в ВайСклад</p>
        <div style={{ marginTop: 16, lineHeight: 1.5, color: 'var(--text-muted)' }}>
          <PersonalDataNotice />
        </div>
        <p style={{ marginTop: 24 }}>
          <Link to="/login" className={styles['auth-back-link']}>
            ← Назад ко входу
          </Link>
        </p>
      </div>
    </div>
  )
}
