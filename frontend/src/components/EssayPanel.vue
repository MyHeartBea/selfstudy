<script setup>
/**
 * 作文批改台：手写稿拍照（或粘贴文本），AI 按考研评分档批改。
 * 图片一律「先看图原样转录，再文本批改」，与全项目 AI 链路一致。
 */
import { ref } from 'vue'

import request from '../api/request'
import { compressImageFile } from '../utils/image'
import { toast } from '../ui/toast'
import EssayGradeResult from './EssayGradeResult.vue'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import Icon from '../ui/Icon.vue'
import Skeleton from '../ui/Skeleton.vue'
import { ESSAY_KINDS } from '../composables/essayKinds'

const emit = defineEmits(['graded'])

const kind = ref('e2_long')
const promptText = ref('')
const text = ref('')
const instruction = ref('')
const images = ref([]) // { preview, base64 }
const grading = ref(false)
const gradingText = ref('')
const result = ref(null)
const errorMsg = ref('')
const saving = ref(false)
let gradeRequestId = 0

const MAX_IMAGES = 5

async function addImageFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    toast.warning('请粘贴或选择作文图片')
    return false
  }
  if (images.value.length >= MAX_IMAGES) {
    toast.warning(`作文图片最多 ${MAX_IMAGES} 张`)
    return false
  }
  const compressed = await compressImageFile(file)
  if (!compressed) {
    toast.error('图片读取失败，请重新截图')
    return false
  }
  images.value.push({
    preview: compressed.dataUrl,
    base64: compressed.dataUrl.split(',')[1] || compressed.dataUrl,
  })
  return true
}

function removeImage(index) {
  images.value.splice(index, 1)
}

function onImagePicked(event) {
  const file = event.target.files[0]
  event.target.value = ''
  addImageFile(file)
}

function reset() {
  gradeRequestId += 1
  grading.value = false
  gradingText.value = ''
  result.value = null
  errorMsg.value = ''
  text.value = ''
  promptText.value = ''
  instruction.value = ''
  images.value = []
}

async function grade() {
  if (!text.value.trim() && !images.value.length) {
    toast.warning('请粘贴作文文本，或上传手写稿照片')
    return
  }
  const requestId = ++gradeRequestId
  grading.value = true
  errorMsg.value = ''
  gradingText.value = images.value.length
    ? '正在转录手写稿并按考研评分档批改，约需 40-120 秒…'
    : '正在按考研评分档批改，约需 30-60 秒…'
  try {
    const res = await request.post(
      '/essays/grade',
      {
        kind: kind.value,
        text: text.value,
        prompt_text: promptText.value,
        instruction: instruction.value,
        images: images.value.map((m) => m.base64),
      },
      { silent: true },
    )
    if (requestId !== gradeRequestId) return
    result.value = res.data.data
    emit('graded', result.value)
    toast.success(
      `批改完成：${result.value.score} / ${result.value.max_score}（${result.value.band}）`,
    )
  } catch (err) {
    if (requestId !== gradeRequestId) return
    const apiMessage = err?.response?.data?.message
    errorMsg.value = apiMessage || err?.message || '批改失败，请稍后重试'
    result.value = null
  } finally {
    if (requestId === gradeRequestId) {
      grading.value = false
      gradingText.value = ''
    }
  }
}

/** 批改结果转成一条错题：题干=作文题目，解析=总评+逐句改错，进复习轮转。 */
function buildMistakePayload(r) {
  const analysisParts = [
    r.overall ? `【总评】${r.overall}` : '',
    r.top_errors?.length ? `【高频错误】${r.top_errors.join('、')}` : '',
    r.weakness_advice ? `【下一步】${r.weakness_advice}` : '',
    (r.corrections || []).length
      ? `【逐句改错】\n${r.corrections
          .map(
            (c) =>
              `- ${c.original}${c.corrected ? ` 改为 ${c.corrected}` : ''}（${c.type || '错误'}：${c.note || ''}）`,
          )
          .join('\n')}`
      : '',
    r.model_version ? `【同题范文】\n${r.model_version}` : '',
  ].filter(Boolean)
  return {
    subject_id: null,
    sub_subject_id: null,
    question_type: 'solution',
    question: promptText.value.trim() || `${r.kind_name}（本次得分 ${r.score}/${r.max_score}）`,
    correct_answer: r.model_version || '',
    analysis: analysisParts.join('\n\n'),
    difficulty: 3,
    difficulty_points: (r.top_errors || []).join('、') || '英语写作',
    knowledge_tags: ['英语作文', ...(r.top_errors || [])].slice(0, 5),
    approach: `AI 批改 ${r.score}/${r.max_score}（${r.band}）`,
    source_type: 'other',
    source_year: '',
    source_name: '',
    images: images.value.map((m) => m.preview),
  }
}

async function saveToMistakes() {
  if (!result.value || saving.value) return
  saving.value = true
  try {
    const subs = await request.get('/subjects', { silent: true })
    const english = (subs.data.data || []).find((s) => String(s.name).includes('英语'))
    if (!english) {
      toast.error('没有找到「英语」科目，请先到科目页确认科目已建好')
      return
    }
    const subRes = await request.get('/sub_subjects', {
      params: { subject_id: english.id },
      silent: true,
    })
    const writing = (subRes.data.data || []).find(
      (s) => String(s.name).includes('写作') || String(s.name).includes('作文'),
    )
    await request.post(
      '/mistakes',
      {
        ...buildMistakePayload(result.value),
        subject_id: english.id,
        sub_subject_id: writing ? writing.id : null,
      },
      { silent: true },
    )
    toast.success('已存入错题库，会进入复习轮转')
  } catch (err) {
    toast.error(`存入失败：${err?.response?.data?.message || err?.message || '未知错误'}`)
  } finally {
    saving.value = false
  }
}

defineExpose({ addImageFile, grading })
</script>

<template>
  <div class="ep">
    <div class="ep-row">
      <UiSelect v-model="kind" :options="ESSAY_KINDS" compact />
      <span class="ep-hint">
        <Icon name="alert" :size="13" />
        手写稿请拍清晰、一张一页；AI 只原样转录你写的内容，不会替你把错词改对再批改
      </span>
    </div>

    <textarea
      v-model="promptText"
      class="field-input"
      rows="3"
      placeholder="作文题目/要求（强烈建议填）：把试卷上的 Directions 与题目原文粘贴进来，AI 会按「要点是否覆盖」定档"
    ></textarea>

    <textarea
      v-model="text"
      class="field-input"
      rows="9"
      placeholder="直接粘贴你写的英文作文（或保留下方图片让 AI 转录）"
    ></textarea>

    <div class="ep-images">
      <label class="btn btn-outline btn-md pick-label">
        <Icon name="image" :size="14" />
        上传手写稿照片
        <input
          type="file"
          accept="image/*"
          class="visually-hidden"
          data-testid="pick-essay-image"
          @change="onImagePicked"
        />
      </label>
      <span class="ep-hint">也可以直接 Ctrl+V 粘贴照片（最多 {{ MAX_IMAGES }} 张）</span>
      <div v-for="(m, i) in images" :key="i" class="ep-thumb">
        <img :src="m.preview" alt="作文图片" />
        <button type="button" aria-label="移除图片" @click="removeImage(i)">
          <Icon name="x" :size="11" />
        </button>
      </div>
    </div>

    <textarea
      v-model="instruction"
      class="field-input"
      rows="2"
      placeholder="可选：额外要求，例如「这次重点看主谓一致和连接词」「按英语一评分标准从严批改」"
    ></textarea>

    <div class="ep-actions">
      <UiButton variant="primary" :loading="grading" @click="grade">开始批改</UiButton>
      <UiButton variant="outline" :disabled="grading || !result" @click="reset">清空重来</UiButton>
    </div>

    <div v-if="grading" class="ep-loading">
      <span class="spinner"></span>
      <div class="ep-loading-body">
        <p>{{ gradingText }}</p>
        <Skeleton variant="text" :width="'48%'" />
        <Skeleton variant="text" :count="2" />
        <Skeleton variant="rect" :height="58" :radius="12" />
      </div>
    </div>

    <div v-if="errorMsg" class="ep-error">
      <Icon name="alert" :size="15" />
      <p>{{ errorMsg }}</p>
      <UiButton size="sm" variant="outline" @click="grade">重试</UiButton>
    </div>

    <div v-if="result" class="ep-result">
      <div class="ep-result-bar">
        <UiTag color="accent">已存档到作文档案</UiTag>
        <span class="ep-result-actions">
          <UiButton size="sm" variant="outline" :loading="saving" @click="saveToMistakes">
            存入错题库
          </UiButton>
          <RouterLink to="/essays" class="ep-link">看全部作文记录</RouterLink>
        </span>
      </div>
      <EssayGradeResult :result="result" :transcript="result.raw_transcript || text" />
    </div>
  </div>
</template>

<style scoped>
.ep {
  display: grid;
  gap: 12px;
}
.ep-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.ep-hint {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--ink-3);
}
.ep-images {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.ep-thumb {
  position: relative;
  width: 62px;
  height: 62px;
  border-radius: var(--r-sm);
  overflow: hidden;
  border: 1px solid var(--line);
  background: var(--surface-2);
}
.ep-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ep-thumb button {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border: none;
  border-radius: 50%;
  background: rgba(20, 18, 16, 0.68);
  color: #fff;
  cursor: pointer;
}
.ep-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.ep-loading {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.ep-loading-body {
  display: grid;
  gap: 8px;
  flex: 1;
}
.ep-loading-body p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-2);
}
.spinner {
  flex: none;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  border-radius: 50%;
  border: 2px solid var(--line-strong);
  border-top-color: var(--accent);
  animation: ep-spin 0.8s linear infinite;
}
@keyframes ep-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 1s;
  }
}
.ep-error {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 14px;
  border-radius: var(--r-md);
  border: 1px solid color-mix(in srgb, var(--red) 35%, transparent);
  background: color-mix(in srgb, var(--red) 8%, var(--surface));
  color: var(--red);
  font-size: 13px;
}
.ep-error p {
  margin: 0;
  flex: 1;
  line-height: 1.6;
}
.ep-result {
  display: grid;
  gap: 12px;
  padding-top: 4px;
  border-top: 1px dashed var(--line-strong);
}
.ep-result-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.ep-result-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}
.ep-link {
  font-size: 12.5px;
  color: var(--accent-ink);
  text-decoration: none;
  border-bottom: 1px dashed var(--accent-ring);
}
.ep-link:hover {
  border-bottom-style: solid;
}
</style>
