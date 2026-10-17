function row(label: string, value: string): HTMLElement {
  const div = document.createElement('div')
  const strong = document.createElement('strong')
  strong.textContent = `${label}: `
  div.append(strong, value)
  return div
}

/** Popup content for a checkpoint. Built from text nodes only, so nothing is parsed as HTML. */
export function checkpointPopup(p: Record<string, unknown>): HTMLElement {
  const root = document.createElement('div')
  root.className = 'cp-popup'

  const title = document.createElement('div')
  title.className = 'cp-title'
  title.textContent = `${String(p.routeLabel)} · mile ${Number(p.mile).toFixed(0)}`

  const badge = document.createElement('span')
  badge.className = 'cp-badge'
  badge.style.background = String(p.color)
  badge.style.color = String(p.textColor ?? '#ffffff')
  badge.textContent = String(p.risk)
  const risk = document.createElement('div')
  risk.append(badge)

  const reasons = document.createElement('ul')
  for (const text of String(p.reasons ?? '').split('|').filter(Boolean)) {
    const item = document.createElement('li')
    item.textContent = text
    reasons.append(item)
  }

  root.append(
    title,
    row('ETA', String(p.eta)),
    row('Wind', String(p.wind)),
    row('Rain', String(p.rain)),
    row('Snow', String(p.snow)),
    risk,
    reasons,
  )
  return root
}