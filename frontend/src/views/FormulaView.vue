<script setup>
/** 公式背诵库：分类/搜索 + 卡片网格 + 详情/编辑 + 背诵模式 */
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import request from '../api/request'
import RichText from '../components/RichText.vue'
import { markdownToPlain } from '../utils/markdown'
import { formatTime } from '../composables/useBaseData'
import { useResourceList } from '../composables/useResourceList'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import FlipCard from '../ui/FlipCard.vue'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiLoadError from '../ui/UiLoadError.vue'
import UiModal from '../ui/UiModal.vue'
import Icon from '../ui/Icon.vue'

const categories = ['高等数学', '线性代数', '概率统计', '英语背诵', '政治背诵', '408背诵', '其他']

const route = useRoute()

// 公式是全量集合（后端返回裸数组），筛选与搜索在客户端做，所以只要 items + 两个状态位
const {
  items,
  loading,
  loadError,
  load: loadFormulas,
} = useResourceList(async () => {
  const res = await request.get('/formulas')
  return res.data.data
})

const filters = reactive({
  category: '',
  // 命令面板搜完整站后跳回这里时带 ?search=，否则用户落在"全都列出来"的页面上
  search: route.query.search ? String(route.query.search) : '',
})
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailItem = ref(null)
const memorizeVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = reactive({
  category: '高等数学',
  title: '',
  content: '',
})

const filteredItems = computed(() => {
  let list = items.value.slice()
  if (filters.category) {
    list = list.filter((item) => item.category === filters.category)
  }
  if (filters.search.trim()) {
    const keyword = filters.search.trim().toLowerCase()
    list = list.filter(
      (item) =>
        (item.title || '').toLowerCase().includes(keyword) ||
        (item.content || '').toLowerCase().includes(keyword),
    )
  }
  return list
})

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    category: '高等数学',
    title: '',
    content: '',
  })
  dialogVisible.value = true
}

function openDetail(item) {
  detailItem.value = item
  detailVisible.value = true
}

function plainPreview(item) {
  const line =
    String(item.content || '')
      .split('\n')
      .find(
        (value) => value.trim() && !value.trim().startsWith('#') && !value.trim().startsWith('|'),
      ) || ''
  // 同样剥掉行内标记（** / ` / 表格竖线），只留可读正文
  return markdownToPlain(line).slice(0, 80)
}

// 分类印章配色：按分类名稳定散列到五色
const CAT_COLORS = ['var(--accent)', 'var(--teal)', 'var(--gold)', 'var(--violet)', 'var(--blue)']
function catColor(category) {
  const name = String(category || '')
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  return CAT_COLORS[h % CAT_COLORS.length]
}

function openMemorize() {
  // 过卡循环：没记住的排到队尾，直到全部记住
  reciteQueue.value = filteredItems.value.slice()
  reciteKnown.value = 0
  reciteTotal.value = reciteQueue.value.length
  reciteRevealed.value = false
  memorizeVisible.value = true
}

const reciteQueue = ref([])
const reciteKnown = ref(0)
const reciteTotal = ref(0)
// 背诵模式当前卡是否已翻面（显示内容）。此前的实现漏了这个声明，
// 却在 openMemorize/markRecite/模板里以 .value 读写 -> 点「显示内容」直接抛错。
const reciteRevealed = ref(false)

function markRecite(known) {
  if (!reciteQueue.value.length) return
  if (known) {
    reciteQueue.value.shift()
    reciteKnown.value += 1
  } else {
    // 没记住：移到队尾，稍后再来
    reciteQueue.value.push(reciteQueue.value.shift())
  }
  reciteRevealed.value = false
}

// —— 翻牌背诵舞台（墨韵 3.4）：记住=右飞归档（墨光一闪），没记住=左飞回队尾 ——
const reciteFly = ref(null) // 'keep' | 'miss' | null

function flyRecite(known) {
  if (reciteFly.value || !reciteQueue.value.length) return
  reciteFly.value = known ? 'keep' : 'miss'
  setTimeout(() => {
    reciteFly.value = null
    markRecite(known)
  }, 260)
}

const reciteCardStyle = computed(() => {
  if (reciteFly.value === 'keep')
    return { transform: 'translateX(560px) rotate(10deg)', opacity: 0 }
  if (reciteFly.value === 'miss')
    return { transform: 'translateX(-560px) rotate(-10deg)', opacity: 0 }
  return { transform: 'translateX(0) rotate(0deg)', opacity: 1 }
})

// 背诵键盘流：空格翻面，右方向键=记住，左方向键=没记住（输入框聚焦时不拦）
function onReciteKey(event) {
  if (!memorizeVisible.value || !reciteQueue.value.length) return
  const tag = event.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return
  if (event.key === ' ') {
    event.preventDefault()
    reciteRevealed.value = !reciteRevealed.value
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    if (reciteRevealed.value) flyRecite(true)
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    flyRecite(false)
  }
}
onMounted(() => window.addEventListener('keydown', onReciteKey))
onUnmounted(() => window.removeEventListener('keydown', onReciteKey))

function openEdit(item) {
  editingId.value = item.id
  Object.assign(form, {
    category: item.category || '高等数学',
    title: item.title || '',
    content: item.content || '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.title.trim()) {
    toast.warning('请填写公式标题')
    return
  }
  if (!form.content.trim()) {
    toast.warning('请填写公式内容')
    return
  }
  saving.value = true
  try {
    const payload = {
      category: form.category,
      title: form.title.trim(),
      content: form.content.trim(),
    }
    if (editingId.value) {
      await request.put(`/formulas/${editingId.value}`, payload)
      toast.success('公式已更新')
    } else {
      await request.post('/formulas', payload)
      toast.success('公式已添加')
    }
    dialogVisible.value = false
    loadFormulas()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    saving.value = false
  }
}

async function remove(item) {
  const ok = await confirmDialog({
    title: '删除确认',
    message: `确定删除“${item.title}”吗？`,
    danger: true,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await request.delete(`/formulas/${item.id}`)
    toast.success('公式已删除')
    loadFormulas()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  }
}

onMounted(loadFormulas)
</script>

<template>
  <div class="page km-editorial">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Formula Deck</div>
        <h2>公式背诵库</h2>
        <p class="view-desc">常用公式集中管理、检索与背诵。</p>
      </div>
      <div class="header-actions">
        <UiButton v-if="filteredItems.length" variant="outline" @click="openMemorize">
          背诵模式
        </UiButton>
        <UiButton variant="primary" @click="openCreate">新增公式</UiButton>
      </div>
    </div>

    <div class="card card-pad filter-bar">
      <UiSelect
        v-model="filters.category"
        :options="categories"
        placeholder="全部分类"
        clearable
        compact
      />
      <input
        v-model="filters.search"
        class="field-input search-input"
        placeholder="搜索标题或公式"
      />
      <span class="count-tip">共 {{ filteredItems.length }} 条</span>
    </div>

    <UiLoadError v-if="loadError" text="公式加载失败" @retry="loadFormulas" />
    <UiEmpty
      v-else-if="!filteredItems.length && !loading"
      seal="式"
      text="暂无公式，点击右上角新增"
      icon="sigma"
    />
    <div v-else class="formula-grid">
      <article
        v-for="(item, i) in filteredItems"
        :key="item.id"
        class="formula-card km-card card"
        role="button"
        tabindex="0"
        :aria-label="`查看公式 ${item.title}`"
        :style="{
          '--enter-delay': `calc(${Math.min(i, 11)} * var(--stagger-1))`,
          '--fcol': catColor(item.category),
        }"
        @click="openDetail(item)"
        @keydown.enter.prevent="openDetail(item)"
        @keydown.space.prevent="openDetail(item)"
      >
        <span class="f-mark" aria-hidden="true">∑</span>
        <div class="formula-head">
          <span class="cat-seal">{{ item.category }}</span>
          <span class="formula-title">{{ item.title }}</span>
        </div>
        <div class="formula-preview">{{ plainPreview(item) }}</div>
        <div class="formula-foot">
          <span class="muted">{{ formatTime(item.updated_at || item.created_at) }}</span>
          <!-- 操作按钮阻止冒泡：点它们不会顺带打开详情 -->
          <div class="formula-actions">
            <button class="op-link" @click.stop="openDetail(item)">查看</button>
            <button class="op-link" @click.stop="openEdit(item)">编辑</button>
            <button class="op-link danger" @click.stop="remove(item)">删除</button>
          </div>
        </div>
      </article>
    </div>

    <!-- 背诵模式（翻牌过卡循环） -->
    <UiModal v-model="memorizeVisible" title="背诵模式 · 过卡循环" size="lg">
      <div v-if="reciteQueue.length">
        <div class="memorize-head">
          <UiTag size="sm">{{ reciteQueue[0].category }}</UiTag>
          <span class="count-tip">
            剩余 {{ reciteQueue.length }} / {{ reciteTotal }} · 已记住 {{ reciteKnown }}
          </span>
        </div>
        <div class="recite-progress">
          <div
            class="recite-progress-inner"
            :style="{ width: (reciteKnown / Math.max(1, reciteTotal)) * 100 + '%' }"
          ></div>
        </div>
        <div class="recite-stage" :style="reciteCardStyle">
          <FlipCard
            v-if="reciteQueue[0]"
            :key="reciteQueue[0].id"
            :flipped="reciteRevealed"
            class="recite-flip"
          >
            <template #front>
              <span
                class="recite-cat serif"
                :style="{ color: catColor(reciteQueue[0].category) }"
                >{{ reciteQueue[0].category }}</span
              >
              <h3 class="memorize-title serif">{{ reciteQueue[0].title }}</h3>
              <span class="recite-hint">空格翻面 · 右方向键 记住 / 左方向键 待会再来</span>
            </template>
            <template #back>
              <div class="knowledge-preview">
                <RichText :text="reciteQueue[0].content" />
              </div>
            </template>
          </FlipCard>
        </div>
      </div>
      <div v-else class="recite-complete">
        <Icon name="check" :size="34" />
        <h3>全部记住！</h3>
        <p class="muted">本轮 {{ reciteTotal }} 条公式已全部过完。</p>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="memorizeVisible = false">退出</UiButton>
        <template v-if="reciteQueue.length">
          <UiButton variant="outline" @click="flyRecite(false)">没记住，待会再来</UiButton>
          <UiButton v-if="reciteRevealed" variant="primary" @click="flyRecite(true)"
            >记住了</UiButton
          >
        </template>
      </template>
    </UiModal>

    <!-- 详情 -->
    <UiModal v-model="detailVisible" :title="detailItem ? detailItem.title : ''" size="lg">
      <div v-if="detailItem">
        <UiTag size="sm" style="margin-bottom: 12px">{{ detailItem.category }}</UiTag>
        <RichText :text="detailItem.content" />
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="detailVisible = false">关闭</UiButton>
      </template>
    </UiModal>

    <!-- 新增/编辑 -->
    <UiModal v-model="dialogVisible" :title="editingId ? '编辑公式' : '新增公式'" size="md">
      <div class="f-form">
        <div class="field">
          <label class="field-label">分类</label>
          <UiSelect v-model="form.category" :options="categories" />
        </div>
        <div class="field">
          <label class="field-label">标题</label>
          <input v-model="form.title" class="field-input" placeholder="如：基本积分表" />
        </div>
        <div class="field">
          <label class="field-label">内容</label>
          <textarea
            v-model="form.content"
            class="field-input"
            rows="10"
            placeholder="支持 $...$ 公式、Markdown 表格和列表"
          ></textarea>
        </div>
        <div v-if="form.content.trim()" class="knowledge-preview">
          <div class="section-label">预览</div>
          <RichText :text="form.content" />
        </div>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="dialogVisible = false">取消</UiButton>
        <UiButton variant="primary" :loading="saving" @click="save">保存</UiButton>
      </template>
    </UiModal>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.search-input {
  width: 240px;
}

.formula-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.formula-card {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 16px 14px 20px;
  cursor: pointer;
  transition:
    border-color 0.2s var(--ease),
    box-shadow 0.3s var(--ease);
  animation: fcard-in var(--dur-4) var(--ease-enter) both;
  animation-delay: var(--enter-delay, 0ms);
}
@keyframes fcard-in {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.formula-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 4px;
  border-radius: 0 4px 4px 0;
  background: linear-gradient(
    180deg,
    var(--fcol),
    color-mix(in srgb, var(--fcol) 30%, transparent)
  );
  opacity: 0.8;
  transition: width 0.25s var(--spring);
  /* 左侧色条是纯装饰：不参与命中测试，避免盖住整卡点击层 */
  pointer-events: none;
}
.formula-card:hover {
  border-color: color-mix(in srgb, var(--fcol) 45%, var(--line));
  box-shadow: var(--shadow-2);
}
.formula-card:hover::before {
  width: 6px;
}
/* 同知识点卡片：hover 不做位移，避免鼠标停在边缘时抖动 */
.formula-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
/* 水墨 ∑ 水印是纯装饰（已有 pointer-events:none），不参与命中测试 */
/* 水墨 ∑ 水印 */
.f-mark {
  position: absolute;
  right: 10px;
  bottom: -14px;
  font-family: var(--font-display);
  font-size: 74px;
  line-height: 1;
  color: var(--fcol);
  opacity: 0.07;
  transform: rotate(-8deg);
  pointer-events: none;
  user-select: none;
}

.formula-head {
  display: flex;
  align-items: center;
  gap: 9px;
}
/* 分类印章：悬停轻叩一记（thud），像盖章时的手感 */
.cat-seal {
  flex: none;
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 7px;
  background: color-mix(in srgb, var(--fcol) 13%, transparent);
  color: var(--fcol);
  border: 1px solid color-mix(in srgb, var(--fcol) 28%, transparent);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  transform: rotate(-2deg);
  white-space: nowrap;
}
@media (prefers-reduced-motion: no-preference) {
  .formula-card:hover .cat-seal {
    animation: seal-thud 0.32s var(--ease);
  }
}
@keyframes seal-thud {
  0% {
    transform: rotate(-2deg) scale(1);
  }
  45% {
    transform: rotate(-3deg) scale(1.08);
  }
  100% {
    transform: rotate(-2deg) scale(1);
  }
}
.formula-title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14.5px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.formula-card:hover .formula-title {
  color: var(--accent-ink);
}

.formula-preview {
  font-size: 12.5px;
  color: var(--ink-3);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 40px;
}

.formula-foot {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
.formula-actions {
  display: flex;
  gap: 2px;
}
.op-link {
  border: none;
  background: transparent;
  color: var(--accent-ink);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 3px 7px;
  border-radius: 6px;
}
.op-link:hover {
  background: var(--accent-soft);
}
.op-link.danger {
  color: var(--red);
}
.op-link.danger:hover {
  background: var(--red-soft);
}

.memorize-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.recite-progress {
  height: 6px;
  border-radius: 999px;
  background: var(--bg-soft);
  overflow: hidden;
  margin-bottom: 14px;
}
.recite-progress-inner {
  height: 100%;
  border-radius: 999px;
  background: var(--green);
  transition: width 0.4s var(--ease-enter);
}
/* 翻牌舞台：飞出（记住=右 / 没记住=左）由 reciteCardStyle 驱动 */
.recite-stage {
  transition:
    transform 0.28s var(--ease-move),
    opacity 0.28s var(--ease-move);
}
.recite-flip {
  --flip-h: 300px;
}
.recite-flip :deep(.flip-front) {
  gap: 6px;
  background: linear-gradient(180deg, var(--surface), var(--surface-2));
}
.recite-cat {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.2em;
}
.recite-hint {
  font-size: 12px;
  color: var(--ink-3);
}
.recite-complete {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--green);
  text-align: center;
}
.recite-complete h3 {
  font-family: var(--font-display);
  color: var(--ink);
}
.memorize-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  margin: 6px 0 12px;
}
.knowledge-preview {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 14px 16px;
  background: var(--surface-2);
  width: 100%;
  max-height: 230px;
  overflow-y: auto;
  text-align: left;
}

.f-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--ink-2);
}
</style>
