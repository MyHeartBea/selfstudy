<script setup>
/** 知识点编辑 / 新增弹窗：支持 Ctrl+V 粘贴图片 → AI 生成草稿 */
import { computed, onUnmounted, reactive, ref, toRef, watch } from 'vue'

import request from '../api/request'
import { baseData } from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import { toast } from '../ui/toast'
import UiModal from '../ui/UiModal.vue'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import TagInput from './TagInput.vue'
import RichText from './RichText.vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  row: { type: Object, default: null },
  // true = 添加模式（tag_name 可编辑、POST 创建）；false = 编辑模式（PATCH）
  isCreate: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const saving = ref(false)
const analyzing = ref(false)
const analysisInstruction = ref('')
const analysisImage = ref('') // data URL，分析来源图预览

const form = reactive({
  id: null,
  tag_name: '',
  subject_id: null,
  sub_subject_id: null,
  summary: '',
  related_tags: [],
})

const { subSubjectOptions } = useSubSubject(toRef(form, 'subject_id'))

function resetForm() {
  form.id = null
  form.tag_name = ''
  form.subject_id = null
  form.sub_subject_id = null
  form.summary = ''
  form.related_tags = []
}

watch(
  () => props.row,
  (row) => {
    if (props.isCreate) {
      resetForm()
    } else if (row) {
      form.id = row.id
      form.tag_name = row.tag_name
      form.subject_id = row.subject_id || null
      form.sub_subject_id = row.sub_subject_id || null
      form.summary = row.summary || ''
      form.related_tags = (row.related_tags || []).slice()
    }
  },
  { immediate: true },
)

function onSubjectChange() {
  form.sub_subject_id = null
}

// —— 图片粘贴分析 ——
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

function handlePaste(event) {
  const items = event.clipboardData?.items || []
  for (const item of items) {
    if (item.type && item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) {
        event.preventDefault()
        analyzeImageFile(file)
        return
      }
    }
  }
}

async function onPickImage(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file || !file.type.startsWith('image/')) {
    toast.warning('请选择图片文件')
    return
  }
  analyzeImageFile(file)
}

async function analyzeImageFile(file) {
  try {
    const dataUrl = await fileToDataUrl(file)
    analysisImage.value = dataUrl
    await runAnalysis(dataUrl)
  } catch (err) {
    toast.error(err.message || '图片读取失败')
  }
}

async function runAnalysis(dataUrl) {
  analyzing.value = true
  try {
    const base64 = dataUrl.split(',')[1] || dataUrl
    const res = await request.post(
      '/ai/knowledge-from-image',
      {
        image_base64: base64,
        instruction: analysisInstruction.value,
      },
      { silent: true },
    )
    const draft = res.data.data
    if (draft.tag_name) form.tag_name = draft.tag_name
    if (draft.summary) form.summary = draft.summary
    if (Array.isArray(draft.related_tags)) form.related_tags = draft.related_tags.slice()
    toast.success('知识点草稿已生成，请核对后保存（AI 结果仅供参考）')
  } catch (err) {
    toast.error(`图片分析失败：${err?.response?.data?.message || err?.message || '未知错误'}`)
  } finally {
    analyzing.value = false
  }
}

function clearAnalysisImage() {
  analysisImage.value = ''
  analysisInstruction.value = ''
}

// 对话框打开时监听 Ctrl+V 粘贴图片
watch(visible, (open) => {
  if (open) window.addEventListener('paste', handlePaste, true)
  else window.removeEventListener('paste', handlePaste, true)
})
onUnmounted(() => window.removeEventListener('paste', handlePaste, true))

// —— 保存 ——
async function save() {
  if (!form.tag_name.trim()) {
    toast.warning('请填写知识点名称')
    return
  }
  saving.value = true
  try {
    if (props.isCreate) {
      await request.post('/knowledge', {
        tag_name: form.tag_name,
        subject_id: form.subject_id || null,
        sub_subject_id: form.sub_subject_id || null,
        summary: form.summary,
        related_tags: form.related_tags,
      })
      toast.success('知识点已添加')
    } else {
      await request.patch(`/knowledge/${form.id}`, {
        summary: form.summary,
        subject_id: form.subject_id || null,
        sub_subject_id: form.sub_subject_id || null,
        related_tags: form.related_tags,
      })
      toast.success('知识点已更新')
    }
    emit('saved')
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UiModal v-model="visible" :title="isCreate ? '添加知识点' : '编辑知识点摘要'" size="md">
    <div class="kform">
      <!-- 图片粘贴分析 -->
      <div class="field">
        <label class="field-label">图片分析</label>
        <div class="img-analyze">
          <div class="img-analyze-row">
            <input
              v-model="analysisInstruction"
              class="field-input"
              placeholder="可选：告诉 AI 重点分析哪里、怎么分析（如：重点讲清公式推导和易错点）"
            />
            <UiButton variant="primary" :loading="analyzing" @click="analysisImage && runAnalysis(analysisImage)">
              {{ analysisImage ? '重新分析' : '分析图片' }}
            </UiButton>
            <UiButton v-if="analysisImage" variant="ghost" @click="clearAnalysisImage">清除</UiButton>
          </div>
          <p class="field-hint">
            直接 <b>Ctrl + V 粘贴</b>知识点截图，AI 自动识别并生成知识点草稿（名称/摘要/关联标签）
          </p>
          <div v-if="analysisImage" class="img-preview">
            <img :src="analysisImage" alt="待分析图片" />
          </div>
          <label class="pick-image">
            <Icon name="image" :size="14" />
            选择图片
            <input type="file" accept="image/*" class="visually-hidden" @change="onPickImage" />
          </label>
        </div>
      </div>

      <div class="field">
        <label class="field-label required">知识点名称</label>
        <input
          v-model="form.tag_name"
          class="field-input"
          :disabled="!isCreate"
          :placeholder="isCreate ? '如：等价无穷小、地址转换' : ''"
        />
      </div>

      <div class="field-grid">
        <div class="field">
          <label class="field-label">所属科目</label>
          <UiSelect
            v-model="form.subject_id"
            :options="baseData.subjects.map((s) => ({ label: s.name, value: s.id }))"
            placeholder="通用"
            clearable
            @change="onSubjectChange"
          />
        </div>
        <div class="field">
          <label class="field-label">二级科目</label>
          <UiSelect
            v-model="form.sub_subject_id"
            :options="subSubjectOptions.map((s) => ({ label: s.name, value: s.id }))"
            placeholder="全部"
            clearable
            :disabled="!subSubjectOptions.length"
          />
        </div>
      </div>

      <div class="field">
        <label class="field-label">摘要</label>
        <textarea
          v-model="form.summary"
          class="field-input"
          rows="8"
          placeholder="补充该知识点的讲解、易错点、扩展内容；支持 $...$ 公式、Markdown 表格和列表"
        ></textarea>
      </div>

      <div class="field">
        <label class="field-label">关联知识点</label>
        <TagInput v-model="form.related_tags" color="#a16207" placeholder="输入关联标签后按回车，如：地址转换" />
      </div>

      <div v-if="form.summary.trim()" class="knowledge-preview">
        <div class="section-label">预览</div>
        <RichText :text="form.summary" />
      </div>
    </div>

    <template #footer>
      <UiButton variant="ghost" @click="visible = false">取消</UiButton>
      <UiButton variant="primary" :loading="saving" @click="save">
        {{ isCreate ? '添加' : '保存' }}
      </UiButton>
    </template>
  </UiModal>
</template>

<style scoped>
.kform { display: flex; flex-direction: column; gap: 15px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 560px) { .field-grid { grid-template-columns: 1fr; } }
.field-label { font-size: 12.5px; font-weight: 700; color: var(--ink-2); }
.required::after { content: ' *'; color: var(--accent); }
.field-hint { font-size: 12px; color: var(--ink-3); margin: 0; }

.img-analyze { display: flex; flex-direction: column; gap: 8px; }
.img-analyze-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.img-preview img {
  max-width: 100%;
  max-height: 220px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.pick-image {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  align-self: flex-start;
  border: 1px dashed var(--line-strong);
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
}
.pick-image:hover { border-color: var(--accent); color: var(--accent-ink); }

.knowledge-preview {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 12px 14px;
  background: var(--surface-2);
}
</style>
