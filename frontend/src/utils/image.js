/**
 * 上传前图片压缩：长边超过 MAX_EDGE 才等比缩小（只降分辨率、不放大）。
 * PNG 截图保持 PNG 无损输出，题干文字清晰度不受影响；其它格式转 JPEG 0.9。
 * 小于 SMALL_SIZE 的图片原样返回，避免重复编码损失。
 */
const MAX_EDGE = 2000
const SMALL_SIZE = 1.5 * 1024 * 1024 // dataURL 长度阈值（约 1.1MB 原图）

export function compressImageFile(file) {
  return new Promise((resolve) => {
    if (!file || !file.type || !file.type.startsWith('image/')) {
      resolve(null)
      return
    }
    const reader = new FileReader()
    reader.onerror = () => resolve(null)
    reader.onload = () => {
      const dataUrl = String(reader.result)
      const img = new Image()
      img.onerror = () => resolve(null)
      img.onload = () => {
        try {
          const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height))
          if (scale >= 1 && dataUrl.length < SMALL_SIZE) {
            resolve({ dataUrl, file })
            return
          }
          const canvas = document.createElement('canvas')
          canvas.width = Math.max(1, Math.round(img.width * scale))
          canvas.height = Math.max(1, Math.round(img.height * scale))
          canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
          const isPng = (file.type || '').includes('png')
          const out = isPng
            ? canvas.toDataURL('image/png')
            : canvas.toDataURL('image/jpeg', 0.9)
          resolve({ dataUrl: out, file })
        } catch (err) {
          // 压缩失败（如跨域/内存不足）时退回原图，不阻塞录入
          resolve({ dataUrl, file })
        }
      }
      img.src = dataUrl
    }
    reader.readAsDataURL(file)
  })
}
