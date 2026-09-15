export type InstallmentPeriod = 'month' | 'two_weeks' | 'week'

export const INSTALLMENT_PERIOD_OPTIONS: { value: InstallmentPeriod; label: string }[] = [
  { value: 'month', label: 'Раз в месяц' },
  { value: 'two_weeks', label: 'Раз в 2 недели' },
  { value: 'week', label: 'Раз в неделю' },
]

export function addPeriod(date: Date, period: InstallmentPeriod, i: number): Date {
  const result = new Date(date)
  if (period === 'month') result.setMonth(result.getMonth() + i)
  else if (period === 'two_weeks') result.setDate(result.getDate() + i * 14)
  else result.setDate(result.getDate() + i * 7)
  return result
}

const MIN_PARTS = 2
// Технический потолок против зацикливания при абсурдных вводах — не бизнес-лимit,
// реальные графики (например год раз в неделю = 52 платежа) должны в него помещаться.
const MAX_PARTS = 60

// Сколько платежей с выбранной периодичностью уложится между первым платежом
// и сроком «Долг до» — чтобы график заканчивался примерно к дедлайну, а не
// растягивался/схлопывался относительно него.
export function estimatePartsCount(
  firstDate: string,
  dueDate: string,
  period: InstallmentPeriod,
): number {
  const first = new Date(firstDate)
  const due = new Date(dueDate)
  if (Number.isNaN(first.getTime()) || Number.isNaN(due.getTime()) || due <= first) return MIN_PARTS

  let count = 1
  while (count < MAX_PARTS && addPeriod(first, period, count) <= due) {
    count += 1
  }
  return Math.min(Math.max(count, MIN_PARTS), MAX_PARTS)
}

// Делим сумму на равные копеечные доли без потери суммы — последний платёж
// забирает остаток от деления, чтобы сумма графика сходилась с исходной день в
// день (backend строго проверяет total == сумма, копейка мимо — отказ).
export function splitEvenly(totalRub: string, parts: number): string[] {
  const totalCents = Math.round(Number(totalRub) * 100)
  const baseCents = Math.floor(totalCents / parts)
  const remainder = totalCents - baseCents * parts
  return Array.from({ length: parts }, (_, i) => {
    const cents = baseCents + (i === parts - 1 ? remainder : 0)
    return (cents / 100).toFixed(2)
  })
}

export function buildInstallmentSchedule(
  totalRub: string,
  parts: number,
  firstDate: string,
  period: InstallmentPeriod,
): { due_date: string; amount: string }[] {
  const amounts = splitEvenly(totalRub, parts)
  return amounts.map((amount, i) => ({
    due_date: addPeriod(new Date(firstDate), period, i).toISOString().slice(0, 10),
    amount,
  }))
}
