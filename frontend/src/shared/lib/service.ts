/** «40 мин», «1 ч», «1 ч 30 мин»; пусто — длительность не указана.
 *  То же правило, что ServiceDetails.duration_label на бэкенде. */
export function formatDuration(minutes: number): string {
  if (!minutes || minutes <= 0) return ''
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return `${rest} мин`
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`
}

/** Единицы услуги в виде «за что платят» — так понятнее, чем «шт/час». */
export const SERVICE_UNIT_LABELS: Record<string, string> = {
  service: 'за услугу',
  hour: 'за час',
  visit: 'за выезд',
  day: 'за день',
}

export const SERVICE_UNITS = Object.keys(SERVICE_UNIT_LABELS)

// витрина знает единицу по названию («услуга»), а не по коду
const PHRASE_BY_NAME: Record<string, string> = {
  услуга: 'за услугу',
  час: 'за час',
  выезд: 'за выезд',
  день: 'за день',
}

/** «за услугу» вместо «за услуга»; незнакомая единица — как есть. */
export function serviceUnitPhrase(unitName: string): string {
  return PHRASE_BY_NAME[unitName.trim().toLowerCase()] ?? `за ${unitName}`
}
