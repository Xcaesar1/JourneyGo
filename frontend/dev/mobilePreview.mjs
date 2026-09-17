export function previewResponse(method, path) {
  if (method === 'GET' && path === '/api/v2/travel/capabilities') {
    return { status: 200, body: { one_click: { enabled: true }, train: { enabled: true }, hotel: { enabled: true }, flight: { enabled: false, paid: true } } }
  }
  if (method === 'GET' && path === '/api/settings') {
    return { status: 200, body: { success: true, data: { demo_mode: true, planner_engine: 'journey_graph', runtime_secret_updates_enabled: false } } }
  }
  if (method === 'GET' && path === '/api/trip/history') {
    return { status: 200, body: { items: [] } }
  }
  return { status: 409, body: { detail: '当前为手机样式预览，不执行生成、查询或保存。请到测试站验证真实流程。' } }
}

export function mobilePreviewPlugin() {
  return {
    name: 'mobile-style-preview',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const path = new URL(request.url || '/', 'http://localhost').pathname
        if (path !== '/api' && !path.startsWith('/api/')) return next()
        const result = previewResponse(request.method, path)
        response.statusCode = result.status
        response.setHeader('Content-Type', 'application/json; charset=utf-8')
        response.setHeader('Cache-Control', 'no-store')
        response.end(JSON.stringify(result.body))
      })
    },
    transformIndexHtml() {
      return [{ tag: 'div', attrs: { id: 'mobile-preview-notice', style: 'position:fixed;bottom:8px;left:50%;transform:translateX(-50%);z-index:99999;padding:5px 10px;border-radius:6px;background:#ffd58b;color:#172938;font:12px/1.4 sans-serif;white-space:nowrap;pointer-events:none' }, children: '本地实时预览 · 模拟数据 / Local preview', injectTo: 'body' }]
    },
  }
}
