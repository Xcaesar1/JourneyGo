import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const monitor = source.slice(source.indexOf('const watchTripPlanTask ='), source.indexOf('export async function generateTripPlan('))
function fixture(records) {
  let socket, reads = 0
  class FakeSocket {
    constructor() { socket = this }
    close() { this.onclose?.() }
  }
  class Failure extends Error {
    constructor(message, taskId, traceId, code) { super(message); Object.assign(this, { taskId, traceId, code }) }
  }
  const context = { WebSocket: FakeSocket, TripTaskFailure: Failure, t: key => key,
    getWsBaseUrl: () => 'ws://local', window: { setTimeout: fn => setTimeout(fn, 0) },
    getTripTask: async () => { const value = records[Math.min(reads++, records.length-1)]; if(value instanceof Error) throw value; return value },
  }
  vm.createContext(context)
  vm.runInContext(ts.transpileModule(monitor + '\nglobalThis.watch = watchTripPlanTask', {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
  }).outputText, context)
  const promise = context.watch({ task_id:'local-task', trace_id:'local-trace', ws_url:'/ws' })
  return { promise, socket: () => socket, reads: () => reads }
}
const ready = { task_id:'local-task', trip_id:'local-trip', status:'awaiting_approval', stage:'awaiting_approval', progress:90,
  result:{success:true,data:{city:'test'}},review:{status:'pending'} }

test('mobile socket close recovers the existing draft through GET without resubmission', async () => {
  const f = fixture([ready]); f.socket().onclose(); f.socket().onerror();
  const result = await f.promise
  assert.equal(result.review.status,'pending');assert.equal(result.task_id,'local-task');assert.equal(f.reads(),1)
})
test('polling continues while the existing task runs and preserves actual failures', async () => {
  const f=fixture([{...ready,status:'processing',result:null}, {...ready,status:'failed',error:{code:'provider_error',message:'Provider failed'}}])
  f.socket().onerror()
  await assert.rejects(f.promise,error=>error.code==='provider_error');assert.equal(f.reads(),2)
})
test('unreachable status is a connection problem, not a failed generation', async () => {
  const f=fixture([new Error('offline')]);f.socket().onclose()
  await assert.rejects(f.promise,error=>error.code==='status_connection_lost');assert.equal(f.reads(),3)
})
test('successful socket messages do not start fallback polling', async () => {
  const f=fixture([]);f.socket().onmessage({data:JSON.stringify(ready)})
  assert.equal((await f.promise).success,true);assert.equal(f.reads(),0)
})
test('completion notification without payload fetches the durable result instead of failing', async () => {
  const f=fixture([ready]);f.socket().onmessage({data:JSON.stringify({...ready,result:null})})
  assert.equal((await f.promise).success,true);assert.equal(f.reads(),1)
})
test('landing does not announce completion before result navigation and separates connection issues', () => {
  const landing=readFileSync(new URL('../views/Landing.vue',import.meta.url),'utf8')
  assert.doesNotMatch(landing,/loadingProgress.value = 100/)
  assert.match(landing,/await router.push/)
  assert.match(landing,/home.failure.connectionTitle/)
  assert.match(landing,/home.failure.checkStatus/)
})
