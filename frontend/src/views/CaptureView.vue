<script setup>
/** 智能录入：粘贴题干 / 上传截图 → AI 解析 → 核对表单 → 提交 */
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import MistakeForm from '../components/MistakeForm.vue'
import EnglishAnalysisPanel from '../components/EnglishAnalysisPanel.vue'
import { getClipboardImage } from '../utils/clipboard'
import { createMistakeDraft } from '../composables/mistakeDraft'
import { toast } from '../ui/toast'
import UiButton from '../ui/UiButton.vue'
import UiTabs from '../ui/UiTabs.vue'
import Icon from '../ui/Icon.vue'

const router = useRouter()
const activeTab = ref('text')
const text = ref('')
const textInstruction = ref('')
const imageInstruction = ref('')
const analyzing = ref(false)
const analyzingText = ref('')
const parsed = ref(null)
const formKey = ref(0)
const previewImage = ref('')
const imageBase64 = ref('')
const referenceImage = ref('')
const referenceBase64 = ref('')
const moreImages = ref([]) // 英语整篇多张原文/选项图（附加主图）
const pasteTarget = ref('main') // 下张粘贴目标：main=继续加主图 / reference=参考图
const ocrRawText = ref('')
const aiWarning = ref('')
const readerRef = ref(null)
const referenceReaderRef = ref(null)
let analysisRequestId = 0

async function analyze() {
  if (!text.value.trim()) {
    toast.warning('请先粘贴题干内容')
    return
  }
  const requestId = ++analysisRequestId
  analyzing.value = true
  analyzingText.value = '正在解析题干并生成答案与解析，约需 30-60 秒，请稍候…'
  try {
    const res = await request.post(
      '/ai/analyze',
      {
        text: text.value,
        instruction: textInstruction.value,
      },
      { silent: true },
    )
    if (requestId !== analysisRequestId) return
    parsed.value = res.data.data
    ocrRawText.value = ''
    aiWarning.value = ''
    formKey.value += 1
    toast.success('AI 解析完成，请核对后点击提交；保存后才会出现在错题列表')
  } catch (err) {
    // 请求已静默（silent），错误提示统一由下方 aiWarning 呈现，避免与全局 toast 重复
    if (requestId !== analysisRequestId) return
    const apiMessage = err?.response?.data?.message
    const isBadGateway = err?.status === 502 || err?.response?.status === 502
    aiWarning.value =
      isBadGateway
        ? `AI 服务暂不可用：${apiMessage || '上游请求失败'}，已切换到手动整理模式，可稍后重试。`
        : `AI 解析失败：${apiMessage || err?.message || '未知错误'}，已切换到手动整理模式。`
    parsed.value = createMistakeDraft(text.value)
    ocrRawText.value = ''
    formKey.value += 1
  } finally {
    if (requestId === analysisRequestId) {
      analyzing.value = false
      analyzingText.value = ''
    }
  }
}

function useManual() {
  analysisRequestId += 1
  analyzing.value = false
  analyzingText.value = ''
  parsed.value = createMistakeDraft(text.value)
  ocrRawText.value = ''
  formKey.value += 1
}

function useManualImage() {
  analysisRequestId += 1
  analyzing.value = false
  analyzingText.value = ''
  parsed.value = createMistakeDraft('')
  ocrRawText.value = ''
  moreImages.value = []
  formKey.value += 1
}

function onFileChange(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file) return
  handleImageFile(file)
}

function handleImageFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    toast.warning('剪贴板内容不是图片，请重新截图后粘贴')
    return
  }
  // 已有主图时，后续图片自动追加为英语整篇的原文/选项图
  if (previewImage.value) {
    addMoreImage(file)
    return
  }
  // 粘贴/选择后先暂存预览，等待用户补充要求或参考图片后再点击分析
  const requestId = ++analysisRequestId
  analyzing.value = false
  analyzingText.value = ''
  parsed.value = null
  ocrRawText.value = ''
  aiWarning.value = ''
  removeReference()
  const reader = new FileReader()
  readerRef.value = reader
  reader.onload = () => {
    if (requestId !== analysisRequestId) return
    previewImage.value = String(reader.result)
    imageBase64.value = String(reader.result).split(',')[1] || String(reader.result)
  }
  reader.onerror = () => {
    if (requestId !== analysisRequestId) return
    analyzing.value = false
    analyzingText.value = ''
    toast.error('图片读取失败，请重新截图后粘贴')
  }
  reader.readAsDataURL(file)
}

function addMoreImage(file) {
  if (!file || !file.type.startsWith('image/')) {
    toast.warning('图片格式不正确，请重新选择')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    const preview = String(reader.result)
    moreImages.value.push({
      preview,
      base64: String(reader.result).split(',')[1] || String(reader.result),
    })
    toast.success('已添加图片，可继续追加或开始识别')
  }
  reader.onerror = () => toast.error('图片读取失败')
  reader.readAsDataURL(file)
}

function removeMoreImage(index) {
  moreImages.value.splice(index, 1)
}

function removeMainImage() {
  analysisRequestId += 1
  analyzing.value = false
  analyzingText.value = ''
  previewImage.value = ''
  imageBase64.value = ''
  moreImages.value = []
  parsed.value = null
  ocrRawText.value = ''
  aiWarning.value = ''
  removeReference()
  if (readerRef.value) {
    try {
      readerRef.value.abort()
    } catch (err) {
      // 忽略中止异常
    }
    readerRef.value = null
  }
}

function onReferenceFileChange(event) {
  const file = event.target.files[0]
  event.target.value = ''
  stageReferenceFile(file)
}

function stageReferenceFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    toast.warning('参考图片格式不正确，请重新选择')
    return
  }
  const reader = new FileReader()
  referenceReaderRef.value = reader
  reader.onload = () => {
    referenceImage.value = String(reader.result)
    referenceBase64.value = String(reader.result).split(',')[1] || String(reader.result)
  }
  reader.onerror = () => {
    toast.error('参考图片读取失败')
  }
  reader.readAsDataURL(file)
}

function removeReference() {
  referenceImage.value = ''
  referenceBase64.value = ''
  if (referenceReaderRef.value) {
    try {
      referenceReaderRef.value.abort()
    } catch (err) {
      // 忽略中止异常
    }
    referenceReaderRef.value = null
  }
}

function onPaste(event) {
  if (event.__pasteHandled) return
  event.__pasteHandled = true
  const file = getClipboardImage(event)
  if (!file) return
  event.preventDefault()
  activeTab.value = 'image'
  // 主图未就绪 → 作为主图；已就绪时按当前「粘贴目标」分流：主图(继续追加)或参考图
  if (!previewImage.value) {
    handleImageFile(file)
  } else if (pasteTarget.value === 'reference' && !referenceBase64.value) {
    stageReferenceFile(file)
    toast.success('已添加为参考图片（按图中思路解题）')
  } else {
    addMoreImage(file)
    toast.success('已添加为第 ' + (moreImages.value.length + 1) + ' 张图片，可继续追加')
  }
}

function setPasteTarget(target) {
  pasteTarget.value = target
  toast.info(target === 'reference' ? '下一张粘贴将作为参考图' : '下一张粘贴将作为主图')
}

async function analyzeImage() {
  if (!imageBase64.value) {
    toast.warning('请先粘贴或选择题目图片')
    return
  }
  const requestId = ++analysisRequestId
  analyzing.value = true
  analyzingText.value = '正在识别图片并解析，约需 30-90 秒，请稍候…'
  try {
    let res
    if (referenceBase64.value) {
      // 有参考图：走通用 OCR（按图中思路解题）
      res = await request.post(
        '/ai/ocr',
        {
          image_base64: imageBase64.value,
          instruction: imageInstruction.value,
          reference_image_base64: referenceBase64.value,
        },
        { silent: true },
      )
    } else {
      // 单图/多图都走自动检测：英语整篇→精读，数学等→回落标准
      const images = [imageBase64.value, ...moreImages.value.map((m) => m.base64)]
      res = await request.post(
        '/ai/english',
        {
          images,
          instruction: imageInstruction.value,
        },
        { silent: true },
      )
    }
    if (requestId !== analysisRequestId) return
    parsed.value = res.data.data
    // 识别成功后保留全部原图（长题多张截图都保留，列表/详情才能看到完整题目）
    if (previewImage.value && !(parsed.value.images && parsed.value.images.length)) {
      parsed.value.images = [
        previewImage.value,
        ...moreImages.value.map((m) => m.preview),
      ]
    }
    ocrRawText.value =
      parsed.value.method === 'local' ? parsed.value.raw_text || '' : ''
    // 后端降级消息（如"本地 OCR 识别完成（视觉模型失败：…）"）：
    // 走到本地 OCR 时展示后端返回的具体原因，方便定位是哪个视觉通道失败。
    const ocrMessage = String(res.data?.message || '')
    aiWarning.value =
      parsed.value.method === 'local' && ocrMessage
        ? ocrMessage
        : ''
    formKey.value += 1
    toast.success(
      parsed.value.is_english
        ? '英语整篇已解析：可点词查义、勾选生词入生词本，确认后保存'
        : '图片识别完成，请核对后点击提交；保存后才会出现在错题列表',
    )
  } catch (err) {
    // 请求已静默（silent），错误提示统一由下方 aiWarning 呈现
    if (requestId !== analysisRequestId) return
    const apiMessage = err?.response?.data?.message
    const isBadGateway = err?.status === 502 || err?.response?.status === 502
    aiWarning.value =
      isBadGateway
        ? `AI 服务暂不可用：${apiMessage || '上游请求失败'}，已切换到手动整理模式，可稍后重试。`
        : `图片识别失败：${apiMessage || err?.message || '未知错误'}，已切换到手动整理模式。`
    parsed.value = createMistakeDraft('')
    ocrRawText.value = ''
    formKey.value += 1
  } finally {
    if (requestId === analysisRequestId) {
      analyzing.value = false
      analyzingText.value = ''
    }
  }
}

function onSubmitted() {
  router.push('/mistakes')
}

// 英语整篇录入成功后跳转错题列表
function onEnglishSaved() {
  router.push('/mistakes')
}

// 英语多题：把某一题移为当前保存题（从多题池移除，保留整篇附加内容）
function onSaveQuestion(qIndex) {
  const cur = parsed.value
  if (!cur) return
  const qs = cur.english_questions || []
  // 面板 questions 里 index>=1 的来自 english_questions[qIndex-1]
  const srcIndex = qIndex >= 1 ? qIndex - 1 : -1
  if (srcIndex < 0 || srcIndex >= qs.length) return
  const q = qs.splice(srcIndex, 1)[0]
  const merged = {
    ...cur,
    ...q,
    english_questions: qs,
    is_english: true,
  }
  parsed.value = merged
  formKey.value += 1
  toast.success(`已切换到第 ${qIndex + 1} 题，请在下方核对后保存`)
}

onMounted(() => {
  window.addEventListener('paste', onPaste, true)
})

onUnmounted(() => {
  window.removeEventListener('paste', onPaste, true)
  analysisRequestId += 1
  if (readerRef.value) {
    try {
      readerRef.value.abort()
    } catch (err) {
      // 忽略中止异常
    }
    readerRef.value = null
  }
  if (referenceReaderRef.value) {
    try {
      referenceReaderRef.value.abort()
    } catch (err) {
      // 忽略中止异常
    }
    referenceReaderRef.value = null
  }
})
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Smart Capture</div>
        <h2>智能录入</h2>
        <p class="view-desc">粘贴题干或上传图片，可附加解题要求与参考图，AI 按你的思路整理成完整错题。</p>
      </div>
    </div>

    <div class="notice card">
      <Icon name="sparkles" :size="17" class="notice-icon" />
      <p>
        支持粘贴题干或上传题目图片；粘贴主图后可补充文字解题要求（如「按配方法求解、某步写详细」），
        再 Ctrl+V 粘贴第二张图作为参考（按图中思路解题），最后点击「开始识别并解析」，保存前可再核对修改。
      </p>
    </div>

    <div class="card card-pad capture-panel">
      <UiTabs
        v-model="activeTab"
        :tabs="[
          { name: 'text', label: '粘贴题干' },
          { name: 'image', label: '上传图片' },
        ]"
      />

      <div v-if="activeTab === 'text'" class="tab-body">
        <textarea
          v-model="text"
          class="field-input"
          rows="8"
          placeholder="把题目原文粘贴到这里，包含题干和 A/B/C/D 选项"
        ></textarea>
        <textarea
          v-model="textInstruction"
          class="field-input"
          rows="3"
          placeholder="可选：补充解题要求或思路，例如「按配方法求解，正交变换步骤写详细」「用导数定义法证明」"
        ></textarea>
        <div class="capture-actions">
          <UiButton variant="primary" :loading="analyzing" @click="analyze">AI 解析</UiButton>
          <UiButton variant="outline" :disabled="!text.trim()" @click="useManual">手动整理</UiButton>
        </div>
      </div>

      <div v-else class="tab-body">
        <div class="capture-actions">
          <label class="btn btn-primary btn-md pick-label">
            <Icon v-if="analyzing" name="refresh" :size="15" class="spin" />
            <Icon v-else name="image" :size="15" />
            选择/粘贴题目图片
            <input type="file" accept="image/*" class="visually-hidden" @change="onFileChange" />
          </label>
          <UiButton v-if="previewImage" variant="outline" @click="removeMainImage">移除图片</UiButton>
          <UiButton variant="outline" @click="useManualImage">手动整理</UiButton>
        </div>
        <p class="paste-hint">先 Ctrl+V 粘贴/选择第一张图；主图就绪后，用下面「粘贴目标」决定下一张是继续加主图，还是作为参考图</p>

        <div v-if="previewImage" class="paste-target-row">
          <span class="pt-label">下一张粘贴为：</span>
          <button type="button" class="pt-btn" :class="{ active: pasteTarget === 'main' }" @click="setPasteTarget('main')">主图（英语整篇多图）</button>
          <button type="button" class="pt-btn" :class="{ active: pasteTarget === 'reference' }" @click="setPasteTarget('reference')">参考图（按图中思路解）</button>
        </div>

        <div v-if="previewImage" class="image-preview">
          <img :src="previewImage" alt="题目图片" />
        </div>

        <div v-if="moreImages.length" class="more-images">
          <div v-for="(m, i) in moreImages" :key="i" class="more-image-item">
            <img :src="m.preview" alt="附加图片" />
            <button type="button" class="more-image-remove" aria-label="移除图片" @click="removeMoreImage(i)">
              <Icon name="x" :size="12" />
            </button>
          </div>
          <label class="pick-label btn btn-outline btn-md" style="align-self: center">
            <Icon name="plus-circle" :size="14" />
            继续添加图片
            <input type="file" accept="image/*" class="visually-hidden" @change="onFileChange" />
          </label>
        </div>

        <textarea
          v-if="previewImage"
          v-model="imageInstruction"
          class="field-input"
          rows="3"
          placeholder="可选：补充要求，如「逐句翻译」「重点讲解长难句」「按配方法求解」"
        ></textarea>

        <div v-if="previewImage" class="reference-section">
          <label class="pick-label btn btn-outline btn-md">
            <Icon name="copy" :size="14" />
            选择参考图片（按图中思路解题）
            <input type="file" accept="image/*" class="visually-hidden" @change="onReferenceFileChange" />
          </label>
          <span v-if="referenceImage" class="reference-preview">
            <img :src="referenceImage" alt="参考图片" />
            <UiButton size="sm" variant="danger" @click="removeReference">移除参考图</UiButton>
          </span>
        </div>

        <div v-if="previewImage" class="capture-actions">
          <UiButton variant="primary" :loading="analyzing" :disabled="!imageBase64" @click="analyzeImage">
            开始识别并解析
          </UiButton>
        </div>
      </div>
    </div>

    <div v-if="analyzing" class="notice card analyzing">
      <span class="spinner"></span>
      <p>{{ analyzingText }}</p>
    </div>

    <div v-if="ocrRawText" class="notice card warn">
      <Icon name="alert" :size="17" class="notice-icon" />
      <div>
        <p>本地 OCR 识别完成，复杂公式可能识别不准；请对照下面的识别原文核对。若已配置视觉模型仍走本地 OCR，请重启后端后重试。</p>
        <pre class="ocr-raw">{{ ocrRawText }}</pre>
      </div>
    </div>

    <div v-if="aiWarning" class="notice card warn dismissible">
      <Icon name="alert" :size="17" class="notice-icon" />
      <p>{{ aiWarning }}</p>
      <button type="button" class="notice-close" aria-label="关闭提醒" @click="aiWarning = ''">
        <Icon name="x" :size="13" />
      </button>
    </div>

    <div v-if="parsed" class="card card-pad form-card">
      <div v-if="parsed.is_english" class="card card-pad english-learn">
        <h3 class="panel-title">英语整篇精读</h3>
        <EnglishAnalysisPanel :parsed="parsed" @save-question="onSaveQuestion" @saved="onEnglishSaved" />
      </div>

      <h3 class="panel-title">确认并完善题目信息</h3>
      <MistakeForm :key="formKey" :initial="parsed" @submitted="onSubmitted" />
    </div>
  </div>
</template>

<style scoped>
.notice {
  display: flex;
  gap: 11px;
  padding: 13px 16px;
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--ink-2);
  align-items: flex-start;
}
.notice p { margin: 0; line-height: 1.7; }
.notice-icon { color: var(--blue); margin-top: 2px; }
.notice.warn .notice-icon { color: var(--gold); }
.notice.warn { border-color: color-mix(in srgb, var(--gold) 35%, var(--line)); background: var(--gold-soft); }
.dismissible { position: relative; }
.notice-close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  padding: 2px;
}
.ocr-raw {
  margin: 10px 0 0;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 12px;
  white-space: pre-wrap;
  max-height: 220px;
  overflow-y: auto;
  color: var(--ink-2);
}

.capture-panel { display: flex; flex-direction: column; gap: 16px; }
.tab-body { display: flex; flex-direction: column; gap: 12px; }

.capture-actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.pick-label { cursor: pointer; }

.paste-hint { font-size: 12.5px; color: var(--ink-3); margin: 0; }

.paste-target-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pt-label { font-size: 12.5px; color: var(--ink-2); font-weight: 600; }
.pt-btn {
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.13s;
}
.pt-btn:hover { border-color: var(--accent); color: var(--accent-ink); }
.pt-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.pt-btn.active[data] { color: #fff; }

.image-preview {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 10px;
  background: var(--surface-2);
  display: flex;
  justify-content: center;
}
.image-preview img { max-width: 100%; max-height: 360px; object-fit: contain; }

.more-images { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.more-image-item {
  position: relative;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.more-image-item img { display: block; max-width: 150px; max-height: 100px; object-fit: contain; }
.more-image-remove {
  position: absolute;
  top: 3px; right: 3px;
  width: 20px; height: 20px;
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: 50%;
  background: rgba(0, 0, 0, 0.55); color: #fff; cursor: pointer; padding: 0;
}
.english-learn { margin-bottom: 4px; }

.reference-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.reference-preview { display: inline-flex; align-items: center; gap: 10px; }
.reference-preview img {
  max-width: 180px;
  max-height: 110px;
  border: 1px solid var(--line);
  border-radius: 8px;
  object-fit: contain;
}

.analyzing { align-items: center; }
.spinner {
  flex: none;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  animation: spin 0.7s linear infinite;
}
.spin { animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.form-card { margin-top: 4px; }
.panel-title {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}
</style>
