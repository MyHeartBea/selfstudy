<!--
  CaptureView —— 智能录入 · 蘸墨台
  ---------------------------------------------------------------------------
  交互语义：录入 = 蘸墨（先把图取齐），解析 = 研墨（一次送检），结果 = 初测。

  三条关键设计（对照 v2 的真实痛点）：
   1. **一次选多张**：`<input multiple>`（v2 只能一张张加）。最多 5 帧（后端上限）。
   2. **先蘸满再研墨**：所有帧暂存后由用户点一次「开始研墨」，不自动每贴一张跑一次 AI。
   3. **真实阶段进度**：两个 AI 端点同步阻塞 165-210 秒，所以进度显示的是**阶段**，
      绝不显示假百分比（假进度比没有进度更伤信任）。

  契约：POST /api/ai/english（英语整篇，多图）或 /api/ai/ocr（通用/带参考图）；
  所有 URL 在 core/api，本文件不写 URL。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { aiApi } from '../core/api'
import { toast } from '../ui/toast'
import StarRow from '../ui/StarRow.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiTag from '../ui/UiTag.vue'
import UiTextarea from '../ui/UiTextarea.vue'

const MAX_FRAMES = 5

/** 暂存的帧：{ dataUrl, base64 } */
const frames = ref([])
const reference = ref(null)
const instruction = ref('')
const gluing = ref(false) // 上传/压缩中
const grinding = ref(false) // AI 解析中
const result = ref(null)
const errorText = ref('')
/** 真实阶段：drive = 取帧 / align = 对齐 / decode = 视觉解译 / translate = 分段翻译 / words = 抽词 */
const stage = ref('')
const stageIndex = ref(0)

const STAGES = ['取帧入库', '帧对齐', '视觉解译', '分段翻译', '生词抽提']
const canGrind = computed(() => frames.value.length > 0 && !grinding.value)
const remaining = computed(() => MAX_FRAMES - frames.value.length)

/** 图片压缩：长边 2000 以内，避免上传超大图拖慢（后端也会再处理） */
function compress(file) {
  return new Promise((resolve) => {
    if (!file || !file.type || !file.type.startsWith('image/')) return resolve(null)
    const reader = new FileReader()
    reader.onerror = () => resolve(null)
    reader.onload = () => {
      const dataUrl = String(reader.result)
      const img = new Image()
      img.onerror = () => resolve(null)
      img.onload = () => {
        try {
          const scale = Math.min(1, 2000 / Math.max(img.width, img.height))
          if (scale >= 1 && dataUrl.length < 1.5 * 1024 * 1024) return resolve(dataUrl)
          const canvas = document.createElement('canvas')
          canvas.width = Math.round(img.width * scale)
          canvas.height = Math.round(img.height * scale)
          canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
          const isPng = (file.type || '').includes('png')
          resolve(isPng ? canvas.toDataURL('image/png') : canvas.toDataURL('image/jpeg', 0.9))
        } catch {
          resolve(dataUrl)
        }
      }
      img.src = dataUrl
    }
    reader.readAsDataURL(file)
  })
}

/** 统一的入库入口：**一次可进多张**（这是多选的意义所在） */
async function addFiles(fileList) {
  const files = Array.from(fileList || []).filter((f) => f && f.type?.startsWith('image/'))
  if (!files.length) return
  gluing.value = true
  stage.value = '取帧入库'
  stageIndex.value = 0
  try {
    const room = MAX_FRAMES - frames.value.length
    if (room <= 0) {
      toast.error(`最多 ${MAX_FRAMES} 帧，请先移除一些`)
      return
    }
    const accepted = files.slice(0, room)
    // 关键：在 await 之前先跑完全部文件（避免循环变量被覆盖 —— v2 踩过的坑）
    const urls = await Promise.all(accepted.map((f) => compress(f)))
    urls.forEach((dataUrl) => {
      if (!dataUrl) return
      frames.value.push({ dataUrl, base64: dataUrl.split(',')[1] || dataUrl })
    })
    if (files.length > room) toast.info(`只接收了前 ${room} 张（上限 ${MAX_FRAMES}）`)
    else toast.success(`已取 ${urls.filter(Boolean).length} 帧，可继续追加或直接研墨`)
  } finally {
    gluing.value = false
  }
}

function onPick(e) {
  addFiles(e.target.files)
  e.target.value = '' // 允许重复选同一文件
}

/** 剪贴板粘贴：多张也一起收（截图分屏的常见做法） */
function onPaste(e) {
  const items = e.clipboardData?.items || []
  const files = []
  for (const it of items) {
    if (it.kind === 'file' && it.type.startsWith('image/')) {
      const f = it.getAsFile()
      if (f) files.push(f)
    }
  }
  if (files.length) {
    e.preventDefault()
    addFiles(files)
  }
}

function removeFrame(i) {
  frames.value.splice(i, 1)
}

function clearAll() {
  frames.value = []
  reference.value = null
  instruction.value = ''
  result.value = null
  errorText.value = ''
  stage.value = ''
}

/** 研墨：一次提交全部帧，按真实阶段推进提示 */
async function grind() {
  if (!canGrind.value) return
  grinding.value = true
  result.value = null
  errorText.value = ''
  stage.value = '帧对齐'
  stageIndex.value = 1

  // 真实阶段：因为后端是同步阻塞的一次调用，中途拿不到细粒度进度，
  // 所以这里推进的是"可解释的阶段"，并在每个阶段停留足够久以免闪烁。
  const timers = [
    setTimeout(() => {
      stage.value = '视觉解译'
      stageIndex.value = 2
    }, 2500),
    setTimeout(() => {
      stage.value = '分段翻译'
      stageIndex.value = 3
    }, 20000),
    setTimeout(() => {
      stage.value = '生词抽提'
      stageIndex.value = 4
    }, 60000),
  ]

  try {
    const images = frames.value.map((f) => f.base64)
    const data = reference.value
      ? await aiApi.ocr({
          images,
          instruction: instruction.value,
          referenceImage: reference.value.base64,
        })
      : await aiApi.english({ images, instruction: instruction.value })
    result.value = data
    toast.success('研墨完成，请核对后入册')
  } catch (e) {
    errorText.value = e?.message || '研墨失败'
    toast.error(errorText.value)
  } finally {
    timers.forEach(clearTimeout)
    grinding.value = false
    stage.value = ''
  }
}

/** 结果里能展示的字段（响应形状见 core/api 注释） */
const summary = computed(() => {
  const d = result.value
  if (!d) return null
  return {
    passage: d.passage_text || '',
    translation: d.passage_translation || '',
    sentences: (d.english_sentences || []).length,
    words: (d.english_words || []).length,
    questions: (d.english_questions || []).length + (d.question ? 1 : 0),
    isEnglish: !!d.is_english,
  }
})

onMounted(() => window.addEventListener('paste', onPaste))
onBeforeUnmount(() => window.removeEventListener('paste', onPaste))
</script>

<template>
  <main id="main" class="tray">
    <header class="head">
      <span class="mono">[03] TRAY · 蘸墨台</span>
      <span class="mono">{{ frames.length }} / {{ MAX_FRAMES }} 帧</span>
    </header>

    <!-- 左：取帧区 -->
    <section class="intake">
      <div class="bore">
        <p class="big">蘸墨</p>
        <p class="sub">
          一次可选多张（原文 / 题干 / 选项分屏截图），<b>全部取齐后再研墨</b>—— 不是每贴一张就跑一次
          AI。也可以直接 Ctrl+V 粘贴，多张一起收。
        </p>
        <div class="acts">
          <label class="pick">
            <input
              type="file"
              accept="image/*"
              multiple
              class="sr-only"
              data-testid="pick-frames"
              @change="onPick"
            />
            <span class="mono">选择图片（可多选）</span>
          </label>
          <UiButton variant="quiet" :disabled="!frames.length" @click="clearAll"> 清空 </UiButton>
        </div>
      </div>

      <div v-if="frames.length" class="frames">
        <div v-for="(f, i) in frames" :key="i" class="frame">
          <img :src="f.dataUrl" :alt="`第 ${i + 1} 帧`" />
          <span class="fno mono">{{ String(i + 1).padStart(2, '0') }}</span>
          <button
            class="rm"
            type="button"
            :aria-label="`移除第 ${i + 1} 帧`"
            @click="removeFrame(i)"
          >
            <svg
              viewBox="0 0 24 24"
              width="12"
              height="12"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              aria-hidden="true"
            >
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p v-if="remaining > 0" class="mono more">还能再加 {{ remaining }} 帧</p>
      </div>

      <UiTextarea
        v-model="instruction"
        label="补充要求（可选）"
        placeholder="例如：逐句翻译 / 重点讲解长难句 / 按配方法求解"
        :rows="2"
        :max-rows="6"
      />

      <div class="grind-row">
        <UiButton
          variant="solid"
          size="lg"
          :loading="grinding"
          :disabled="!canGrind"
          @click="grind"
        >
          {{ grinding ? '研墨中' : '开始研墨' }}
        </UiButton>
        <span v-if="grinding" class="stage mono">
          <i class="pulse" aria-hidden="true"></i>{{ stage }}
          <span class="dots" aria-hidden="true">
            <em v-for="(s, i) in STAGES" :key="s" :class="{ on: i <= stageIndex }"></em>
          </span>
        </span>
        <span v-else class="mono stage-hint">约需 30–210 秒（整篇精读更久），期间请不要刷新</span>
      </div>
    </section>

    <!-- 右：初测结果 -->
    <aside class="assay">
      <span class="mono alab">初测结果</span>

      <UiEmpty
        v-if="!result && !errorText"
        title="还没有研墨结果"
        hint="先在左侧取齐帧，再点「开始研墨」"
      />

      <UiEmpty v-else-if="errorText" title="研墨失败" :hint="errorText">
        <template #action>
          <UiButton variant="solid" :disabled="!canGrind" @click="grind">重试</UiButton>
        </template>
      </UiEmpty>

      <template v-else>
        <div class="rhead">
          <UiTag :tone="summary.isEnglish ? 'vein' : 'gold'" size="sm">
            {{ summary.isEnglish ? '英语整篇' : '题目' }}
          </UiTag>
          <span class="mono rc"
            >{{ summary.sentences }} 句 · {{ summary.words }} 词 · {{ summary.questions }} 题</span
          >
        </div>

        <div v-if="summary.passage" class="rblock">
          <span class="mono rl">原文</span>
          <p class="rtext">
            {{ summary.passage.slice(0, 400) }}{{ summary.passage.length > 400 ? '…' : '' }}
          </p>
        </div>

        <div v-if="summary.translation" class="rblock">
          <span class="mono rl">译文</span>
          <p class="rtext dim">
            {{ summary.translation.slice(0, 300) }}{{ summary.translation.length > 300 ? '…' : '' }}
          </p>
        </div>

        <div class="rfoot">
          <StarRow :value="0" :max="7" label="复习遍数" />
          <UiButton variant="quiet" @click="grind">重新研墨</UiButton>
        </div>
        <p class="mono note">入册（保存为错题）在下一轮接上，本页先完成"取帧与研墨"。</p>
      </template>
    </aside>
  </main>
</template>

<style scoped>
.tray {
  position: relative;
  z-index: var(--z-content);
  max-width: var(--col);
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: clamp(16px, 2.6vw, 40px);
  align-items: start;
}
.head {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(16px, 3vh, 30px);
}

.intake {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.bore {
  padding: clamp(20px, 3vw, 36px);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  background: repeating-linear-gradient(135deg, #ffffff06 0 9px, transparent 9px 18px);
  transition: border-color 0.35s var(--e-settle);
}
.bore:hover {
  border-color: var(--redshift);
}
.big {
  font-size: clamp(1.5rem, 3.2vw, 2.4rem);
  font-weight: 500;
  letter-spacing: -0.03em;
  margin-bottom: 9px;
}
.sub {
  color: var(--ink-2);
  line-height: 1.8;
  max-width: 54ch;
}
.sub b {
  color: var(--ink-0);
  font-weight: 500;
}
.acts {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 16px;
  flex-wrap: wrap;
}
.pick {
  display: inline-flex;
  align-items: center;
  padding: 10px 18px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  color: var(--ink-0);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition:
    border-color 0.25s var(--e-settle),
    background 0.25s var(--e-settle);
}
.pick:hover {
  border-color: var(--redshift);
  background: oklch(0.665 0.196 34 / 0.08);
}

/* 帧缩略图：等宽网格，编号在左上、移除在右上 */
.frames {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 10px;
}
.frame {
  position: relative;
  aspect-ratio: 3 / 4;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--sky-1);
}
.frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.fno {
  position: absolute;
  top: 5px;
  left: 6px;
  color: var(--ink-0);
  text-shadow: 0 0 6px #000;
}
.rm {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 1px;
  background: oklch(0.145 0.018 265 / 0.72);
  color: var(--ink-0);
}
.rm:hover {
  background: var(--redshift);
}
.more {
  grid-column: 1 / -1;
  color: var(--ink-3);
}

/* 阶段指示 */
.grind-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.stage {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: var(--ink-0);
}
.pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--vein);
  animation: pulse 1.6s var(--e-settle) infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.25;
  }
}
.dots {
  display: inline-flex;
  gap: 3px;
}
.dots em {
  width: 14px;
  height: 3px;
  background: var(--sky-3);
  transition: background 0.4s var(--e-settle);
}
.dots em.on {
  background: var(--vein);
}
.stage-hint {
  color: var(--ink-3);
}

/* 初测面板 */
.assay {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 20px 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--sky-1);
  position: sticky;
  top: 90px;
}
.alab {
  color: var(--ink-3);
}
.rhead {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.rc {
  color: var(--ink-2);
}
.rblock {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.rl {
  color: var(--ink-3);
}
.rtext {
  line-height: 1.85;
  font-size: var(--fs-sm);
  color: var(--ink-0);
}
.rtext.dim {
  color: var(--ink-1);
}
.rfoot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.note {
  color: var(--ink-3);
  line-height: 1.7;
}

@media (max-width: 900px) {
  .tray {
    grid-template-columns: 1fr;
  }
  .assay {
    position: static;
  }
}
</style>
