<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import MistakeForm from '../components/MistakeForm.vue'
import { getClipboardImage } from '../utils/clipboard'
import { createMistakeDraft } from '../composables/mistakeDraft'

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
const ocrRawText = ref('')
const aiWarning = ref('')
const readerRef = ref(null)
const referenceReaderRef = ref(null)
let analysisRequestId = 0

async function analyze() {
  if (!text.value.trim()) {
    ElMessage.warning('请先粘贴题干内容')
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
    ElMessage.success('AI 解析完成，请核对后点击提交；保存后才会出现在错题列表')
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
    ElMessage.warning('剪贴板内容不是图片，请重新截图后粘贴')
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
    ElMessage.error('图片读取失败，请重新截图后粘贴')
  }
  reader.readAsDataURL(file)
}

function removeMainImage() {
  analysisRequestId += 1
  analyzing.value = false
  analyzingText.value = ''
  previewImage.value = ''
  imageBase64.value = ''
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
    ElMessage.warning('参考图片格式不正确，请重新选择')
    return
  }
  const reader = new FileReader()
  referenceReaderRef.value = reader
  reader.onload = () => {
    referenceImage.value = String(reader.result)
    referenceBase64.value = String(reader.result).split(',')[1] || String(reader.result)
  }
  reader.onerror = () => {
    ElMessage.error('参考图片读取失败')
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
  // 主图已就绪时，再次粘贴的图片自动作为参考图（按图中思路解题）
  if (previewImage.value) {
    stageReferenceFile(file)
    ElMessage.success('已添加为参考图片（按图中思路解题）')
  } else {
    handleImageFile(file)
  }
}

async function analyzeImage() {
  if (!imageBase64.value) {
    ElMessage.warning('请先粘贴或选择题目图片')
    return
  }
  const requestId = ++analysisRequestId
  analyzing.value = true
  analyzingText.value = '正在调用视觉模型识别图片并生成解析，约需 30-60 秒，请稍候…'
  try {
    const res = await request.post(
      '/ai/ocr',
      {
        image_base64: imageBase64.value,
        instruction: imageInstruction.value,
        reference_image_base64: referenceBase64.value,
      },
      { silent: true },
    )
    if (requestId !== analysisRequestId) return
    parsed.value = res.data.data
    // 识别成功后保留原图（拓扑图/电路图等图形题题干需要展示原图）
    if (
      previewImage.value &&
      !(parsed.value.images && parsed.value.images.length)
    ) {
      parsed.value.images = [previewImage.value]
    }
    ocrRawText.value =
      parsed.value.method === 'local' ? parsed.value.raw_text || '' : ''
    // 后端降级消息（如“本地 OCR 识别完成（视觉模型失败：…）”或纯“本地 OCR 识别完成”）：
    // 走到本地 OCR 时展示后端返回的具体原因，方便定位是哪个视觉通道失败。
    const ocrMessage = String(res.data?.message || '')
    aiWarning.value =
      parsed.value.method === 'local' && ocrMessage
        ? ocrMessage
        : ''
    formKey.value += 1
    ElMessage.success('图片识别完成，请核对后点击提交；保存后才会出现在错题列表')
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

    <el-alert
      title="支持粘贴题干或上传题目图片；粘贴主图后可补充文字解题要求（如「按配方法求解、某步写详细」），再 Ctrl+V 粘贴第二张图作为参考（按图中思路解题），最后点击「开始识别并解析」，保存前可再核对修改。"
      type="info"
      :closable="false"
      show-icon
      class="capture-alert"
    />

    <el-card shadow="never" class="filter-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="粘贴题干" name="text">
          <el-input
            v-model="text"
            type="textarea"
            :rows="8"
            placeholder="把题目原文粘贴到这里，包含题干和 A/B/C/D 选项"
          />
          <el-input
            v-model="textInstruction"
            type="textarea"
            :rows="3"
            class="capture-instruction"
            placeholder="可选：补充解题要求或思路，例如「按配方法求解，正交变换步骤写详细」「用导数定义法证明」"
          />
          <div class="capture-actions">
            <el-button
              type="primary"
              :loading="analyzing"
              @click="analyze"
            >
              AI 解析
            </el-button>
            <el-button :disabled="!text.trim()" @click="useManual">
              手动整理
            </el-button>
          </div>
        </el-tab-pane>
        <el-tab-pane label="上传图片" name="image">
          <div class="capture-actions">
            <label for="capture-image-input" class="el-button el-button--primary">
              <el-icon v-if="analyzing" class="is-loading"><Loading /></el-icon>
              选择/粘贴题目图片
            </label>
            <el-button v-if="previewImage" @click="removeMainImage">
              移除图片
            </el-button>
            <el-button @click="useManualImage">
              手动整理
            </el-button>
          </div>
          <input
            id="capture-image-input"
            type="file"
            accept="image/*"
            class="visually-hidden"
            @change="onFileChange"
          >
          <span class="paste-hint">先 Ctrl+V 粘贴或选择题目图片；主图就绪后再 Ctrl+V，第二张图自动作为参考图片</span>

          <div v-if="previewImage" class="image-preview">
            <img :src="previewImage" alt="题目图片">
          </div>

          <el-input
            v-if="previewImage"
            v-model="imageInstruction"
            type="textarea"
            :rows="3"
            class="capture-instruction"
            placeholder="可选：补充解题要求或思路，例如「按配方法求解，正交变换步骤写详细」「这题用数形结合讲解」"
          />

          <div v-if="previewImage" class="reference-section">
            <label for="capture-reference-input" class="el-button">
              选择参考图片（按图中思路解题）
            </label>
            <input
              id="capture-reference-input"
              type="file"
              accept="image/*"
              class="visually-hidden"
              @change="onReferenceFileChange"
            >
            <span v-if="referenceImage" class="reference-preview">
              <img :src="referenceImage" alt="参考图片">
              <el-button size="small" text type="danger" @click="removeReference">
                移除参考图
              </el-button>
            </span>
          </div>

          <div v-if="previewImage" class="capture-actions">
            <el-button
              type="primary"
              :loading="analyzing"
              :disabled="!imageBase64"
              @click="analyzeImage"
            >
              开始识别并解析
            </el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-alert
      v-if="analyzing"
      type="info"
      :closable="false"
      show-icon
      class="capture-alert"
      :title="analyzingText"
    />

    <el-alert
      v-if="ocrRawText"
      type="warning"
      :closable="false"
      show-icon
      class="capture-alert"
      title="本地 OCR 识别完成，复杂公式可能识别不准；请对照下面的识别原文核对。若已配置视觉模型仍走本地 OCR，请重启后端后重试。"
    >
      <pre class="ocr-raw">{{ ocrRawText }}</pre>
    </el-alert>

    <el-alert
      v-if="aiWarning"
      type="warning"
      :closable="true"
      class="capture-alert"
      :title="aiWarning"
      @close="aiWarning = ''"
    />

    <el-card v-if="parsed" shadow="never" class="form-card">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">确认并完善题目信息</span>
      </template>
      <MistakeForm
        :key="formKey"
        :initial="parsed"
        @submitted="onSubmitted"
      />
    </el-card>
  </div>
</template>
