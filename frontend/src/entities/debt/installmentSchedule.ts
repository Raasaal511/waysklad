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
