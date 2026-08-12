<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import MistakeForm from '../components/MistakeForm.vue'

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

async function analyze() {
  if (!text.value.trim()) {
    ElMessage.warning('请先粘贴题干内容')
    return
  }
  analyzing.value = true
  analyzingText.value = '正在解析题干并生成答案与解析，约需 30-60 秒，请稍候…'
  try {
    const res = await request.post('/ai/analyze', { text: text.value })
    parsed.value = res.data.data
    ocrRawText.value = ''
    formKey.value += 1
    ElMessage.success('AI 解析完成，请核对后点击提交；保存后才会出现在错题列表')
  } catch (err) {
    // 未配置 AI 时提示后，用户可手动整理
  } finally {
    analyzing.value = false
    analyzingText.value = ''
  }
}

function useManual() {
  parsed.value = {
    question: text.value,
    option_a: '',
    option_b: '',
    option_c: '',
    option_d: '',
    correct_answer: 'A',
    analysis: '',
    difficulty: 3,
    knowledge_tags: [],
    approach: '',
    source: '',
  }
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
  const reader = new FileReader()
  reader.onload = async () => {
    previewImage.value = String(reader.result)
    imageBase64.value = String(reader.result).split(',')[1] || String(reader.result)
    await runOcr()
  }
  reader.readAsDataURL(file)
}

async function onPaste(event) {
  const items = event.clipboardData?.items || []
  let imageItem = null
  for (const item of items) {
    if (item.type && item.type.startsWith('image/')) {
      imageItem = item
      break
    }
  }
  if (!imageItem) return

  const file = imageItem.getAsFile()
  if (!file) return
  event.preventDefault()
  activeTab.value = 'image'
  handleImageFile(file)
}

async function runOcr() {
  if (!imageBase64.value) return
  analyzing.value = true
  analyzingText.value = '正在识别图片并生成解析，约需 30-60 秒，请稍候…'
  try {
    const res = await request.post('/ai/ocr', { image_base64: imageBase64.value })
    parsed.value = res.data.data
    ocrRawText.value =
      parsed.value.method === 'local' ? parsed.value.raw_text || '' : ''
    formKey.value += 1
    ElMessage.success('图片识别完成，请核对后点击提交；保存后才会出现在错题列表')
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    analyzing.value = false
    analyzingText.value = ''
  }
}

function onSubmitted() {
  router.push('/mistakes')
}

onMounted(() => {
  window.addEventListener('paste', onPaste)
})

onUnmounted(() => {
  window.removeEventListener('paste', onPaste)
})
</script>

<template>
  <div class="page" @paste="onPaste">
    <div class="page-header">
      <h2>智能录入</h2>
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
          <input
            ref="imageInput"
            type="file"
            accept="image/*"
            style="display: none"
            @change="onFileChange"
          >
          <el-button
            type="primary"
            :loading="analyzing"
            @click="$refs.imageInput.click()"
          >
            选择题目图片
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
      title="本地 OCR 识别完成，复杂公式可能识别不准；请对照下面的识别原文核对，配置免费视觉模型（如智谱 GLM-4V-Flash）可大幅提高准确率。"
    >
      <pre class="ocr-raw">{{ ocrRawText }}</pre>
    </el-alert>

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
