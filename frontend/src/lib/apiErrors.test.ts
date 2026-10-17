import assert from 'node:assert/strict'
import { test } from 'node:test'
import { describeValidation, messageForResponse } from './apiErrors.ts'

test('validation details become readable field messages', () => {
  assert.equal(
    describeValidation({ load_weight_lb: ['Ensure this value is less than or equal to 80000.'] }),
    'load weight lb: Ensure this value is less than or equal to 80000.',
  )
})

test('several field errors are joined, and several messages per field are combined', () => {
  assert.equal(
    describeValidation({ origin: ['Too short.', 'Required.'], departure_time: 'In the past.' }),
    'origin: Too short. Required. • departure time: In the past.',
  )
})

test('missing or non-object details fall back to a generic prompt', () => {
  assert.equal(describeValidation(undefined), 'Please check your input.')
  assert.equal(describeValidation(null), 'Please check your input.')
  assert.equal(describeValidation('oops'), 'Please check your input.')
})

test('400 uses the validation details', () => {
  assert.match(messageForResponse(400, { error: 'Invalid input.', details: { origin: ['Bad.'] } }), /^origin: Bad\./)
  assert.equal(messageForResponse(400, null), 'Please check your input.')
})

test('429 asks the user to wait, whatever the body says', () => {
  assert.match(messageForResponse(429, { detail: 'Request was throttled.' }), /Too many requests/)
  assert.match(messageForResponse(429, null), /wait a minute/)
})

test('502, 503 and 504 mean the server is waking up or unavailable', () => {
  for (const status of [502, 503, 504]) {
    assert.match(messageForResponse(status, null), /waking up or temporarily unavailable/, String(status))
  }
})

test('a 422 shows the server’s own explanation', () => {
  assert.equal(messageForResponse(422, { error: "No match found for 'zzz'." }), "No match found for 'zzz'.")
})

test('an unexplained error shows the status code', () => {
  assert.equal(messageForResponse(500, null), 'The server returned an error (500).')
  assert.equal(messageForResponse(500, { error: '   ' }), 'The server returned an error (500).')
  assert.equal(messageForResponse(418, { error: 42 }), 'The server returned an error (418).')
  assert.equal(messageForResponse(500, 'html page'), 'The server returned an error (500).')
})
