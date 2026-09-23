import { api } from '../../shared/api/client'

export type FeedbackTopic = 'question' | 'bug' | 'suggestion'

export const FEEDBACK_MAX_PHOTOS = 3
export const FEEDBACK_MAX_TEXT = 2000
export const FEEDBACK_MAX_PHOTO_BYTES = 5 * 1024 * 1024

export interface FeedbackResponse {
  id: number
  topic: FeedbackTopic
  text: string
  photos: string[]
  created_at: string | null
}

/**
 * Какая сборка открыта у человека: имя входного файла с хешем (index-BMpXCt5h.js).
 * Приложение кэшируется на телефоне — по нему видно, не старая ли версия.
 */
function currentBuildId(): string {
  // только файл сборки из /assets/: на dev-сервере первым идёт служебный /@vite/client
  const src = document.querySelector<HTMLScriptElement>('script[type="module"][src*="/assets/"]')?.src ?? ''
  return src.split('/').pop()?.replace(/\.js$/, '') ?? ''
}

export function sendFeedback(input: { topic: FeedbackTopic; text: string; photos: File[] }) {
  const form = new FormData()
  form.append('topic', input.topic)
  form.append('text', input.text)
  form.append('page', window.location.pathname + window.location.search)
  form.append('app_version', currentBuildId())
  for (const photo of input.photos) form.append('photos', photo)
  return api.postForm<FeedbackResponse>('/feedback', form)
}
