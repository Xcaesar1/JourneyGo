import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const exports = {}
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('./mapCoordinates.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports })
const { toRoutePoint } = exports

test('map rejects missing, non-finite and out-of-range coordinates', () => {
  for (const value of [null, 'bad', {}, [], [null, null], ['', ' '], [true, false], [0, 0],
    [NaN, 34], [109, Infinity], [181, 34], [109, -91], { longitude: 'bad', latitude: 34 }]) {
    assert.equal(toRoutePoint(value), null)
  }
})

test('map accepts saved locations, SDK points and valid zero axes', () => {
  for (const value of [[109, 34], { longitude: 109, latitude: 34 }, { lng: '109', lat: '34' },
    { getLng: () => 109, getLat: () => 34 }]) {
    assert.equal(JSON.stringify(toRoutePoint(value)), '[109,34]')
  }
  assert.equal(JSON.stringify(toRoutePoint([0, 34])), '[0,34]')
})
