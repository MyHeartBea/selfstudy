import assert from 'node:assert/strict'
import { getClipboardImage } from '../src/utils/clipboard.js'

const imageFile = { type: 'image/png', name: 'x.png' }
const eventWithItems = {
  clipboardData: {
    items: [{ kind: 'file', type: 'image/png', getAsFile: () => imageFile }],
    files: [],
  },
}
assert.equal(getClipboardImage(eventWithItems), imageFile)

const eventWithFiles = {
  clipboardData: { items: [], files: [imageFile] },
}
assert.equal(getClipboardImage(eventWithFiles), imageFile)

assert.equal(getClipboardImage({ clipboardData: { items: [], files: [] } }), null)

console.log('clipboard tests passed')
