<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, toRef, watch } from 'vue'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import { baseData } from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import { useTagInput } from '../composables/useTagInput'
import RichText from './RichText.vue'

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
const {
  input: relatedTagInput,
  add: addRelatedTag,
  flush: flushRelatedTag,
  remove: removeRelatedTag,
} = useTagInput(form, 'related_tags')

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

async function onPickImage(file) {
  if (!file || !file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
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
    ElMessage.error(err.message || '图片读取失败')
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
    ElMessage.success('知识点草稿已生成，请核对后保存（AI 结果仅供参考）')
  } catch (err) {
    ElMessage.error(`图片分析失败：${err?.response?.data?.message || err?.message || '未知错误'}`)
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
    ElMessage.warning('请填写知识点名称')
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
      ElMessage.success('知识点已添加')
    } else {
      await request.patch(`/knowledge/${form.id}`, {
        summary: form.summary,
        subject_id: form.subject_id || null,
        sub_subject_id: form.sub_subject_id || null,
        related_tags: form.related_tags,
      })
      ElMessage.success('知识点已更新')
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
  <el-dialog
    v-model="visible"
    :title="isCreate ? '添加知识点' : '编辑知识点摘要'"
    width="640px"
    :close-on-click-modal="false"
  >
    <el-form label-width="90px">
      <!-- 图片粘贴分析（仅添加模式展示；编辑模式也可贴图补摘要） -->
      <el-form-item label="图片分析">
        <div class="img-analyze">
          <div class="img-analyze-row">
            <el-input
              v-model="analysisInstruction"
              placeholder="可选：告诉 AI 重点分析哪里、怎么分析（如：重点讲清公式推导和易错点）"
              clearable
              style="flex: 1"
            />
            <el-button type="primary" :loading="analyzing" @click="analysisImage && runAnalysis(analysisImage)">
              {{ analysisImage ? '重新分析' : '分析图片' }}
            </el-button>
            <el-button v-if="analysisImage" @click="clearAnalysisImage">清除</el-button>
          </div>
          <div class="img-analyze-tip">
            直接 <b>Ctrl + V 粘贴</b>知识点截图，AI 自动识别并生成知识点草稿（名称/摘要/关联标签）
          </div>
          <div v-if="analysisImage" class="img-preview">
            <img :src="analysisImage" alt="待分析图片" />
          </div>
          <el-upload
            :show-file-list="false"
            :auto-upload="false"
            accept="image/*"
            :on-change="(f) => onPickImage(f.raw)"
            style="display: inline-block"
          >
            <el-button size="small">选择图片</el-button>
          </el-upload>
        </div>
      </el-form-item>

      <el-form-item label="知识点名称">
        <el-input
          v-model="form.tag_name"
          :disabled="!isCreate"
          :placeholder="isCreate ? '如：等价无穷小、地址转换' : ''"
        />
      </el-form-item>
      <el-form-item label="所属科目">
        <el-select
          v-model="form.subject_id"
          clearable
          placeholder="通用"
          style="width: 100%"
          @change="onSubjectChange"
        >
          <el-option
            v-for="s in baseData.subjects"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="二级科目">
        <el-select
          v-model="form.sub_subject_id"
          clearable
          placeholder="全部"
          style="width: 100%"
          :disabled="!subSubjectOptions.length"
        >
          <el-option
            v-for="s in subSubjectOptions"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="摘要">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="8"
          placeholder="补充该知识点的讲解、易错点、扩展内容；支持 $...$ 公式、Markdown 表格和列表"
        />
      </el-form-item>
      <el-form-item label="关联知识点">
        <div class="tag-editor">
          <el-tag
            v-for="t in form.related_tags"
            :key="t"
            closable
            type="warning"
            class="tag-chip"
            @close="removeRelatedTag(t)"
          >
            {{ t }}
          </el-tag>
          <el-input
            v-model="relatedTagInput"
            placeholder="输入关联标签后按回车，如：地址转换"
            size="small"
            style="width: 260px"
            @keyup.enter="addRelatedTag"
            @blur="flushRelatedTag"
          />
        </div>
      </el-form-item>
      <div v-if="form.summary.trim()" class="knowledge-preview">
        <div class="section-label">预览</div>
        <RichText :text="form.summary" />
      </div>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">
        {{ isCreate ? '添加' : '保存' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.img-analyze {
  width: 100%;
}
.img-analyze-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.img-analyze-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.img-preview {
  margin-top: 8px;
}
.img-preview img {
  max-width: 100%;
  max-height: 220px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
}
</style>
