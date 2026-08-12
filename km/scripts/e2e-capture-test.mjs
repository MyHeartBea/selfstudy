import { spawn } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'

const EDGE =
  process.env.EDGE_PATH ||
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const PORT = 9223
const APP_URL = process.env.APP_URL || 'http://127.0.0.1:8000/capture'
const PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

const profile = mkdtempSync(path.join(tmpdir(), 'edge-capture-'))
const proc = spawn(
  EDGE,
  [
    '--headless',
    '--disable-gpu',
    '--no-sandbox',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    'about:blank',
  ],
  { stdio: 'ignore' },
)

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function getTarget() {
  for (let i = 0; i < 50; i += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${PORT}/json`)
      const targets = await response.json()
      const page = targets.find((item) => item.type === 'page')
      if (page) return page
    } catch (err) {
      // 等待 Edge 启动
    }
    await sleep(200)
  }
  throw new Error('CDP target not found')
}

const target = await getTarget()
const ws = new WebSocket(target.webSocketDebuggerUrl)
let nextId = 0
const pending = new Map()
const events = []

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message)
    pending.delete(message.id)
  }
  if (
    message.method === 'Runtime.exceptionThrown' ||
    message.method === 'Runtime.consoleAPICalled'
  ) {
    events.push(message)
  }
}

await new Promise((resolve, reject) => {
  ws.onopen = resolve
  ws.onerror = reject
})

function send(method, params = {}) {
  return new Promise((resolve) => {
    const id = ++nextId
    pending.set(id, resolve)
    ws.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const response = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
  })
  return response.result?.result?.value
}

await send('Page.enable')
await send('Runtime.enable')
await send('Browser.grantPermissions', {
  origin: 'http://127.0.0.1:8000',
  permissions: ['clipboardReadWrite', 'clipboardSanitizedWrite'],
})
await send('Page.navigate', { url: APP_URL })
await sleep(4000)

const step1 = await evaluate(`(() => {
  const textarea = document.querySelector('textarea')
  if (!textarea) return 'no-textarea'
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    'value',
  ).set
  setter.call(textarea, '1+1=?')
  textarea.dispatchEvent(new Event('input', { bubbles: true }))
  const button = [...document.querySelectorAll('button')].find((item) =>
    item.textContent.includes('AI 解析'),
  )
  if (!button) return 'no-button'
  button.click()
  return 'clicked'
})()`)

console.log('step1=', step1)
await sleep(12000)

const step2 = await evaluate(`JSON.stringify({
  hasForm: !!document.querySelector('.form-card'),
  hasSave: document.body.innerText.includes('提交错题'),
  loading: document.body.innerText.includes('正在解析题干'),
  body: document.body.innerText.slice(0, 400)
})`)

console.log('step2=', step2)

await send('Page.navigate', { url: APP_URL })
await sleep(3000)

await send('Page.bringToFront')
const focused = await evaluate(
  'window.focus(); document.body.focus(); document.hasFocus()',
)
console.log('focused=', focused)

const pasteStep = await evaluate(`(async () => {
  const bytes = Uint8Array.from(atob(${JSON.stringify(PNG_BASE64)}), (c) => c.charCodeAt(0))
  await navigator.clipboard.write([
    new ClipboardItem({ 'image/png': new Blob([bytes], { type: 'image/png' }) })
  ])
  return 'clipboard-written'
})()`)
console.log('paste_step=', pasteStep)
await send('Input.dispatchKeyEvent', {
  type: 'keyDown',
  key: 'v',
  code: 'KeyV',
  windowsVirtualKeyCode: 86,
  nativeVirtualKeyCode: 86,
  modifiers: 2,
})
await send('Input.dispatchKeyEvent', {
  type: 'keyUp',
  key: 'v',
  code: 'KeyV',
  windowsVirtualKeyCode: 86,
  nativeVirtualKeyCode: 86,
  modifiers: 2,
})
await sleep(2500)

const needsFallback = await evaluate(
  `!document.querySelector('.image-preview img') && !document.body.innerText.includes('正在调用视觉模型')`,
)
if (needsFallback) {
  const synth = await evaluate(`(() => {
    const bytes = Uint8Array.from(atob(${JSON.stringify(PNG_BASE64)}), (c) => c.charCodeAt(0))
    const transfer = new DataTransfer()
    transfer.items.add(new File([bytes], 'paste.png', { type: 'image/png' }))
    const event = new Event('paste', { bubbles: true })
    Object.defineProperty(event, 'clipboardData', { value: transfer })
    const page = document.querySelector('.page')
    if (!page) return 'no-page'
    page.dispatchEvent(event)
    return 'dispatched'
  })()`)
  console.log('synthetic_fallback=', synth)
  await sleep(2500)
}

const pasteCheck = await evaluate(`JSON.stringify({
  hasPreview: !!document.querySelector('.image-preview img'),
  analyzing: document.body.innerText.includes('正在调用视觉模型'),
  reading: document.body.innerText.includes('已读取到图片')
})`)
console.log('paste_check=', pasteCheck)
await sleep(25000)

const pasteFinal = await evaluate(`JSON.stringify({
  hasForm: !!document.querySelector('.form-card'),
  hasSave: document.body.innerText.includes('提交错题'),
  analyzing: document.body.innerText.includes('正在调用视觉模型'),
  body: document.body.innerText.slice(0, 400)
})`)
console.log('paste_final=', pasteFinal)
console.log('errors=', JSON.stringify(events).slice(0, 3000))

ws.close()
proc.kill()
await sleep(1500)
try {
  rmSync(profile, { recursive: true, force: true })
} catch (err) {
  console.log('cleanup_warning=', err.code)
}
