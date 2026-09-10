<script setup>
/** 知识点编辑 / 新增弹窗：支持 Ctrl+V 粘贴（可多张）暂存 → 一次性 AI 生成草稿 */
import { computed, onUnmounted, reactive, ref, toRef, watch, watchEffect } from 'vue'

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
// 暂存待分析的图片：{id, dataUrl}。粘贴多张不立刻分析，攒够后一次性提交，
// 避免"粘一张就分析一张"把同一个知识点拆成好几条。
const stagedImages = ref([])
// 分析成功后再粘贴/删除图片 → 结果已过期，提示重新分析
const draftStale = ref(false)
let imageSeq = 0

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

function clearImages() {
  stagedImages.value = []
  analysisInstruction.value = ''
  draftStale.value = false
}

function resetAll() {
  resetForm()
  clearImages()
}

function loadRow(row) {
  resetForm()
  clearImages()
  if (!row) return
  form.id = row.id
  form.tag_name = row.tag_name
  form.subject_id = row.subject_id || null
  form.sub_subject_id = row.sub_subject_id || null
  form.summary = row.summary || ''
  form.related_tags = (row.related_tags || []).slice()
}

// 打开时加载（编辑）或清空（新增）
watch(
  () => props.row,
  (row) => {
    if (props.isCreate) resetAll()
    else loadRow(row)
  },
  { immediate: true },
)

// 修复「保存后再次添加，上一题内容还在」：
// 上面那个 watch 只在 row 引用变化时触发，而新增弹窗的 row 恒为 null，
// 保存后重新打开不会触发。这里在弹窗打开时按模式强制重置一次。
watch(visible, (open) => {
  if (!open) return
  if (props.isCreate) resetAll()
  else loadRow(props.row)
})

function onSubjectChange() {
  form.sub_subject_id = null
}

// —— 图片暂存 + 分析 ——
const MAX_IMAGES = 10
// 图片入库串行队列：保证连续粘贴/多选时顺序稳定、容量判断不互相覆盖
let stageQueue = Promise.resolve()

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

/** 把图片加入暂存区；不触发分析，等用户点「分析」。 */
function stageImage(dataUrl) {
  stagedImages.value.push({ id: ++imageSeq, dataUrl })
  if (form.summary.trim()) draftStale.value = true
}

/**
 * 粘贴：一次把剪贴板里所有图片都收集起来。
 * 旧实现遇到第一张图就 `return`，导致同时粘贴多张只留下第一张。
 * 这里把 addImageFiles 串行化：连续快速粘贴时不会因并发读取 FileReader
 * 而互相覆盖容量判断、丢图或打乱顺序。
 */
function handlePaste(event) {
  const files = Array.from(event.clipboardData?.files || []).filter((f) =>
    f.type.startsWith('image/'),
  )
  if (!files.length) return
  event.preventDefault()
  stageQueue = stageQueue.then(() => addImageFiles(files)).catch(() => {})
}

async function onPickImage(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  stageQueue = stageQueue.then(() => addImageFiles(files)).catch(() => {})
  await stageQueue
}

async function addImageFiles(files) {
  const images = files.filter((f) => f.type.startsWith('image/'))
  if (!images.length) {
    toast.warning('请选择图片文件')
    return
  }
  const room = MAX_IMAGES - stagedImages.value.length
  if (room <= 0) {
    toast.warning(`最多暂存 ${MAX_IMAGES} 张图片`)
    return
  }
  const accepted = images.slice(0, room)
  if (images.length > room) {
    toast.warning(`最多暂存 ${MAX_IMAGES} 张图片，已保留前 ${room} 张`)
  }
  try {
    // 注意：不要写成 for (const file of accepted) { stageImage(await fileToDataUrl(file)) }
    // —— for...of 的 const 在每次迭代复用同一个绑定，配合 await 会让所有回调
    // 都读到最后一个 file，结果粘贴多张只留下最后一张（实测踩过）。
    // Promise.all 的映射回调每次都是新的形参绑定，顺序也有保证。
    const dataUrls = await Promise.all(accepted.map((file) => fileToDataUrl(file)))
    dataUrls.forEach((dataUrl) => stageImage(dataUrl))
  } catch (err) {
    toast.error(err.message || '图片读取失败')
  }
}

function removeStagedImage(id) {
  stagedImages.value = stagedImages.value.filter((img) => img.id !== id)
  if (form.summary.trim()) draftStale.value = true
}

/** 清空图片与草稿（用户手动「清除」用；重置表单另走 resetAll）。 */
function clearAllImages() {
  clearImages()
  analysisInstruction.value = ''
}

async function runAnalysis() {
  if (!stagedImages.value.length) {
    toast.warning('请先粘贴或选择图片')
    return
  }
  analyzing.value = true
  try {
    // 一次提交全部暂存图片：后端按顺序逐张提文字后合并再整理成一个知识点
    const images = stagedImages.value.map((img) => img.dataUrl.split(',')[1] || img.dataUrl)
    const res = await request.post(
      '/ai/knowledge-from-image',
      {
        images,
        instruction: analysisInstruction.value,
      },
      { silent: true },
    )
    const draft = res.data.data
    if (draft.tag_name) form.tag_name = draft.tag_name
    if (draft.summary) form.summary = draft.summary
    if (Array.isArray(draft.related_tags)) form.related_tags = draft.related_tags.slice()
    draftStale.value = false
    toast.success('知识点草稿已生成，请核对后保存（AI 结果仅供参考）')
  } catch (err) {
    toast.error(`图片分析失败：${err?.response?.data?.message || err?.message || '未知错误'}`)
  } finally {
    analyzing.value = false
  }
}

// 弹窗打开期间监听 Ctrl+V 粘贴图片。
// 用 watchEffect 按「当前是否打开」同步监听器，而不是只在 false→true 的那一次
// watch 回调里挂载：否则组件若以 modelValue=true 挂载（父组件提前置真），
// watch 不会触发，粘贴会静默失效。
watchEffect(() => {
  if (visible.value) window.addEventListener('paste', handlePaste, true)
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
      <!-- 图片暂存 + 分析 -->
      <div class="field">
        <label class="field-label">图片分析</label>
        <div class="img-analyze">
          <div class="img-analyze-row">
            <input
              v-model="analysisInstruction"
              class="field-input"
              placeholder="可选：告诉 AI 重点分析哪里、怎么分析（如：重点讲清公式推导和易错点）"
            />
            <UiButton
              variant="primary"
              :loading="analyzing"
              :disabled="!stagedImages.length"
              @click="runAnalysis"
            >
              {{ analyzing ? '分析中…' : draftStale ? '重新分析' : '分析图片' }}
            </UiButton>
            <UiButton v-if="stagedImages.length" variant="ghost" @click="clearAllImages">清除</UiButton>
          </div>
          <p class="field-hint">
            直接 <b>Ctrl + V 粘贴</b>（可连续粘贴多张，也可一次多选），图片先暂存在下面，
            点 <b>分析图片</b> 时再一起交给 AI —— 多张属于同一个知识点时会合并成一条草稿
          </p>

          <div v-if="stagedImages.length" class="img-tray">
            <div v-for="(img, idx) in stagedImages" :key="img.id" class="img-thumb">
              <img :src="img.dataUrl" :alt="`待分析图片 ${idx + 1}`" />
              <span class="img-idx num">{{ idx + 1 }}</span>
              <button
                type="button"
                class="img-del"
                :title="`移除第 ${idx + 1} 张`"
                :aria-label="`移除第 ${idx + 1} 张`"
                @click="removeStagedImage(img.id)"
              >
                ×
              </button>
            </div>
            <label class="img-thumb img-add">
              <Icon name="plus-circle" :size="16" />
              <span>添加</span>
              <input
                type="file"
                accept="image/*"
                multiple
                class="visually-hidden"
                @change="onPickImage"
              />
            </label>
          </div>

          <div class="img-meta">
            <span v-if="stagedImages.length" class="count-tip">
              已暂存 {{ stagedImages.length }} 张{{ analyzing ? ' · 分析中…' : '' }}
            </span>
            <span v-if="draftStale" class="stale-tip">图片已变动，建议点「重新分析」刷新草稿</span>
            <label v-if="!stagedImages.length" class="pick-image">
              <Icon name="image" :size="14" />
              选择图片（可多选）
              <input type="file" accept="image/*" multiple class="visually-hidden" @change="onPickImage" />
            </label>
          </div>
        </div>
      </div>

      <div class="field">
        <label class="field-label required">知识点名称</label>
        <input
          v-model="form.tag_name"
          name="knowledge_tag_name"
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

/* 暂存图片缩略图条 */
.img-tray {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.img-thumb {
  position: relative;
  width: 88px;
  height: 66px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--line);
  background: var(--surface);
}
.img-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.img-idx {
  position: absolute;
  left: 4px;
  bottom: 3px;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 700;
  color: #fff;
  background: rgba(0, 0, 0, 0.55);
}
.img-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  color: #fff;
  background: rgba(0, 0, 0, 0.55);
  transition: background 0.14s var(--ease);
}
.img-del:hover { background: var(--red); }
.img-add {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border-style: dashed;
  color: var(--ink-3);
  font-size: 11.5px;
  cursor: pointer;
  transition: border-color 0.14s var(--ease), color 0.14s var(--ease);
}
.img-add:hover { border-color: var(--accent); color: var(--accent-ink); }

.img-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.count-tip { font-size: 12px; color: var(--ink-3); }
.stale-tip { font-size: 12px; font-weight: 600; color: var(--gold); }
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
