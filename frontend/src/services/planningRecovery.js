export function planningRecovery(pending = {}, chinese = true, current = {}) {
  const text = (zh, en) => chinese ? zh : en
  const edit = (target, zh, en) => ({ id: target, target, label: text(zh, en) })
  const dates = edit('dates', '调整出发日期或天数', 'Change dates or duration')
  const preferences = edit('preferences', '调整景点偏好与要求', 'Change interests and requirements')
  const hotel = edit('hotel', '调整住宿档次', 'Change hotel tier')
  let reason = pending.message || text('当前条件尚未通过核验，请调整后继续。', 'The current plan needs review before continuing.')
  let actions
  if (['landmark_unplaced', 'landmark_unverified'].includes(pending.code)) {
    const places = pending.diagnostics?.places || []
    actions = pending.code === 'landmark_unverified'
      ? [{ id: 'refresh', label: text('更新地点资料后继续', 'Refresh place evidence and continue') }, preferences]
      : [dates, preferences]
    if (places.length && !pending.diagnostics?.required?.length) actions.unshift({ id: 'skip_landmarks', places, label: text('本次跳过这些景点，继续', 'Skip these sights and continue') })
  } else if (pending.code === 'duplicate_must_visit') {
    actions = (pending.diagnostics?.places || []).slice(0, 2).map(name => ({ id: 'keep_place', value: name, places: pending.diagnostics.places, label: text(`只保留「${name}」`, `Keep only ${name}`) }))
    actions.push(preferences)
  } else if (pending.provider === 'model') {
    if (pending.code === 'supplier_uncertain') reason = text(
      '行程生成服务未返回可确认的结果，已停止自动重试。这不代表没有车，也不代表日期或预算不合适。具体是超时还是服务异常，目前无法确认。',
      'The planning service did not return a confirmed result. Automatic retries stopped. This does not mean trains are unavailable or your dates or budget are unsuitable. The exact service failure is not confirmed.')
    actions = [{ id: 'retry', label: text('保留条件，重新生成', 'Keep settings and regenerate') }, preferences]
  } else if (pending.code === 'over_budget') {
    const budget = Math.ceil(Number(current.budget) * 1.2 / 100) * 100
    actions = [Number.isFinite(budget) && budget > Number(current.budget) && budget <= 1000000
      ? { id: 'budget', value: budget, label: text(`总预算调整为 ¥${budget}，继续`, `Set total budget to CNY ${budget} and continue`) }
      : edit('budget', '调整总预算', 'Change total budget'), hotel, dates]
  } else if (['no_hotel', 'hotel_unavailable'].includes(pending.code)) {
    actions = ['economy', 'business', 'premium'].filter(tier => tier !== current.hotelTier).slice(0, 2).map(tier => ({
      id: 'hotel', value: tier,
      label: text(`改为${{ economy: '经济型', business: '舒适型', premium: '高档型' }[tier]}住宿，继续`, `Use ${tier} hotels and continue`),
    }))
    actions.push(dates)
  } else if (pending.provider === 'flight') {
    actions = [edit('transport', '调整交通方式（不会自动查询航班）', 'Change transport (no automatic flight query)'), dates]
  } else if (pending.code === 'no_transport' || ['late_arrival', 'early_return', 'time_conflict'].includes(pending.code)) {
    actions = [dates, edit('transport', '调整交通条件', 'Change transport settings')]
  } else if (['no_places', 'poi_unmatched', 'must_visit_unplaced', 'no_schedulable_places', 'invalid_selection', 'local_transfer_excessive'].includes(pending.code)) {
    actions = [preferences, pending.code === 'must_visit_unplaced' ? dates : hotel]
  } else {
    actions = [preferences, dates]
  }
  // Flight refresh stays behind the existing explicit paid-query consent.
  if (['train', 'hotel', 'amap'].includes(pending.provider) && actions.length < 3) {
    actions.unshift({ id: 'refresh', label: text('更新该项查询后继续', 'Refresh this query and continue') })
  }
  return { reason, actions }
}
