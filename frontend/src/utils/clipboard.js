export function getClipboardImage(event) {
  const items = event?.clipboardData?.items || []
  for (const item of items) {
    if (item.kind === 'file' && item.type && item.type.startsWith('image/')) {
      const file = typeof item.getAsFile === 'function' ? item.getAsFile() : null
      if (file) return file
    }
  }
  const files = event?.clipboardData?.files || []
  for (const file of files) {
    if (file.type && file.type.startsWith('image/')) return file
  }
  return null
}
