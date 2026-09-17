import test from 'node:test'
import assert from 'node:assert/strict'
import { previewResponse, mobilePreviewPlugin } from './mobilePreview.mjs'

test('preview exposes one-click layout without real providers', () => {
  const response = previewResponse('GET', '/api/v2/travel/capabilities')
  assert.equal(response.body.one_click.enabled, true)
  assert.equal(response.body.flight.enabled, false)
  assert.equal(previewResponse('GET', '/api/trip/history').body.items.length, 0)
})

test('preview rejects writes and unknown API requests instead of proxying', () => {
  for (const method of ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']) {
    assert.equal(previewResponse(method, '/api/v2/trips').status, 409)
  }
  assert.equal(previewResponse('POST', '/api/settings').status, 409)
  assert.equal(mobilePreviewPlugin().apply, 'serve')
})
