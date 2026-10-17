import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  avgRiskLabel,
  formatDuration,
  formatMiles,
  RISK_TEXT_COLOR,
  riskColor,
  toLocalInputValue,
} from './format.ts'

// WCAG 2.x contrast ratio between two #rrggbb colours.
function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(1 + 2 * i, 3 + 2 * i), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2)
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

test('formatMiles always shows one decimal, so small Severe distances stay visible', () => {
  assert.equal(formatMiles(0), '0.0')
  assert.equal(formatMiles(0.4), '0.4')
  assert.equal(formatMiles(794.44), '794.4')
  assert.equal(formatMiles(12), '12.0')
})

test('every risk colour has at least 4.5:1 contrast with its label text', () => {
  for (const level of [-1, 0, 1, 2, 3, 4]) {
    const ratio = contrast(riskColor(level), RISK_TEXT_COLOR)
    assert.ok(ratio >= 4.5, `level ${level}: ${riskColor(level)} on ${RISK_TEXT_COLOR} is ${ratio.toFixed(2)}`)
  }
})

test('white text on the primary button colour meets 4.5:1', () => {
  assert.ok(contrast('#ffffff', '#1f6feb') >= 4.5) // --accent-strong in index.css
})

test('riskColor falls back to the unknown colour', () => {
  assert.equal(riskColor(null), riskColor(-1))
  assert.equal(riskColor(undefined), riskColor(-1))
  assert.equal(riskColor(99), riskColor(-1))
})

test('formatDuration rounds to minutes and drops zero hours', () => {
  assert.equal(formatDuration(42 * 60), '42 min')
  assert.equal(formatDuration(11 * 3600 + 52 * 60), '11 h 52 min')
  assert.equal(formatDuration(3600), '1 h 0 min')
})

test('avgRiskLabel shows n/a for unknown and two decimals out of 4', () => {
  assert.equal(avgRiskLabel(null), 'n/a')
  assert.equal(avgRiskLabel(0), '0.00 / 4')
  assert.equal(avgRiskLabel(1.234), '1.23 / 4')
})

test('toLocalInputValue formats a local date for the datetime-local input', () => {
  assert.equal(toLocalInputValue(new Date(2026, 9, 18, 8, 5)), '2026-10-18T08:05')
})
