import type { Meal } from '@/types'

export function mealPriceText(meal: Meal, chinese = true): string {
  if (meal.price_reference?.amount_cents && meal.price_reference.source === 'amap') {
    const price = (meal.price_reference.amount_cents / 100).toFixed(2)
    return chinese ? `高德参考人均 ¥${price}，实际以店内为准` : `AMap reference ¥${price}/person; confirm in store`
  }
  if ((meal.estimated_cost ?? 0) > 0) return chinese
    ? `历史估算 ¥${meal.estimated_cost}，实际以店内为准`
    : `Historical estimate ¥${meal.estimated_cost}; confirm in store`
  return chinese ? '以店内为准（未计入费用）' : 'Confirm in store (not included)'
}

export function costScope(category: string, summary: Record<string, any>, chinese = true) {
  const pending = chinese ? '待确认' : 'To confirm'
  const date = (value: unknown) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : ''
  if (category === 'outbound' || category === 'return') {
    const start = date(summary[category]?.departure)
    return { scopeLabel: start || pending, sortDate: start }
  }
  if (category === 'hotel') {
    const start = date(summary.hotel?.check_in)
    const end = date(summary.hotel?.check_out)
    const nights = start && end ? Math.round((Date.parse(end) - Date.parse(start)) / 86400000) : 0
    return { scopeLabel: start && end && nights > 0 ? `${start} ~ ${end} · ${nights}${chinese ? '晚' : ' nights'}` : pending, sortDate: start }
  }
  if (category === 'local_transport' && summary.driving_fallback_days?.length) {
    return { scopeLabel: chinese ? '仅非驾车兜底日' : 'Excludes driving-fallback days', sortDate: '' }
  }
  return { scopeLabel: chinese ? '全程' : 'Whole trip', sortDate: '' }
}

export function compareCostDates(a: string, b: string, descending = false) {
  if (!a || !b) return a ? -1 : b ? 1 : 0
  return a.localeCompare(b) * (descending ? -1 : 1)
}
