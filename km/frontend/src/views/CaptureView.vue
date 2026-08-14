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
const analyzing = ref(false)
const analyzingText = ref('')
const parsed = ref(null)
const formKey = ref(0)
const previewImage = ref('')
const imageBase64 = ref('')
const ocrRawText = ref('')
const aiWarning = ref('')
const readerRef = ref(null)
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
    const res = await request.post('/ai/analyze', { text: text.value })
    if (requestId !== analysisRequestId) return
    parsed.value = res.data.data
    ocrRawText.value = ''
    aiWarning.value = ''
    formKey.value += 1
    ElMessage.success('AI 解析完成，请核对后点击提交；保存后才会出现在错题列表')
  } catch (err) {
    // 未配置 AI 时提示后，用户可手动整理
    if (requestId !== analysisRequestId) return
    aiWarning.value =
      err?.status === 502
        ? 'AI 服务暂不可用（未配置或上游失败），已切换到手动整理模式，可稍后重试。'
        : ''
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
  const requestId = ++analysisRequestId
  analyzing.value = true
  analyzingText.value = '已读取到图片，正在调用视觉模型识别并解题，约需 30-60 秒，请稍候…'
  parsed.value = null
  ocrRawText.value = ''
  const reader = new FileReader()
  readerRef.value = reader
  reader.onload = async () => {
    if (requestId !== analysisRequestId) return
    previewImage.value = String(reader.result)
    imageBase64.value = String(reader.result).split(',')[1] || String(reader.result)
    await runOcr(requestId)
  }
  reader.onerror = () => {
    if (requestId !== analysisRequestId) return
    analyzing.value = false
    analyzingText.value = ''
    ElMessage.error('图片读取失败，请重新截图后粘贴')
  }
  reader.readAsDataURL(file)
}

function onPaste(event) {
  if (event.__pasteHandled) return
  event.__pasteHandled = true
  const file = getClipboardImage(event)
  if (!file) return
  event.preventDefault()
  activeTab.value = 'image'
  handleImageFile(file)
}

async function runOcr(requestId) {
  if (!imageBase64.value) return
  analyzing.value = true
  analyzingText.value = '正在调用视觉模型识别图片并生成解析，约需 30-60 秒，请稍候…'
  try {
    const res = await request.post('/ai/ocr', { image_base64: imageBase64.value })
    if (requestId !== analysisRequestId) return
    parsed.value = res.data.data
    ocrRawText.value =
      parsed.value.method === 'local' ? parsed.value.raw_text || '' : ''
    aiWarning.value = ''
    formKey.value += 1
    ElMessage.success('图片识别完成，请核对后点击提交；保存后才会出现在错题列表')
  } catch (err) {
    // 错误提示由请求拦截器统一处理
    if (requestId !== analysisRequestId) return
    aiWarning.value =
      err?.status === 502
        ? 'AI 服务暂不可用（未配置或上游失败），已切换到手动整理模式，可稍后重试。'
        : ''
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
})

</script>

<template>
  <div class="page" @paste="onPaste">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Smart Capture</div>
        <h2>智能录入</h2>
        <p class="view-desc">粘贴题干或上传图片，AI 自动整理成完整错题。</p>
      </div>
    </div>

    <el-alert
      title="支持粘贴题干或上传题目图片，AI 会自动识别并整理选项、答案、解析和知识点，保存前可再核对修改。"
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
          <label for="capture-image-input" class="el-button el-button--primary">
            <el-icon v-if="analyzing" class="is-loading"><Loading /></el-icon>
            选择题目图片
          </label>
          <input
            id="capture-image-input"
            type="file"
            accept="image/*"
            class="visually-hidden"
            @change="onFileChange"
          >
          <el-button @click="useManualImage">
            手动整理
          </el-button>
          <span class="paste-hint">或直接 Ctrl+V 粘贴截图，粘贴后自动分析</span>
          <div v-if="previewImage" class="image-preview">
            <img :src="previewImage" alt="题目图片">
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
