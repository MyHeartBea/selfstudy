<!--
  SubjectsView —— 科目指南（学科志）
  ---------------------------------------------------------------------------
  语义：科目 = 星区；画像是这一区的观测笔记。

  契约（基线实测）：
    GET /api/subjects            - [{ id, name, kind }]
    GET /api/subjects/{id}/profile - { id, subject_id, focus_areas, review_tips, updated_at }
    GET /api/approaches          - **[字符串数组]**（裸数组）
    GET /api/stats               - by_subject 用于显示每个科目的错题量

  设计取舍：左侧科目列表（可点），右侧画像。原因：科目只有几个，
  用左右分栏比"卡片墙 + 点开弹层"更快，也更像"翻一本志书"。
-->
<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { baseApi, statsApi } from '../core/api'
import { subjectProfileApi } from '../core/api/extra'
import { usePageMotion } from '../design/usePageMotion'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiTag from '../ui/UiTag.vue'

const pageRoot = ref(null)
usePageMotion(pageRoot, { stagger: 55 })

const loading = ref(true)
const errorText = ref('')
const subjects = ref([])
const counts = ref(new Map()) // subject_id -> 错题数
const activeId = ref(null)

const profileLoading = ref(false)
const profile = ref(null)
const profileError = ref('')
const approaches = ref([])

const active = computed(() => subjects.value.find((s) => s.id === activeId.value) || null)

/** 画像里的 focus_areas / review_tips 是**文本**，按行拆成条目渲染 */
function lines(text) {
  return String(text || '')
    .split('\n')
    .map((l) => l.replace(/^[-*·\s]+/, '').trim())
    .filter(Boolean)
}

async function loadSubjects() {
  loading.value = true
  errorText.value = ''
  try {
    const [subs, stats] = await Promise.allSettled([baseApi.subjects(), statsApi.overview()])
    subjects.value = subs.status === 'fulfilled' ? subs.value || [] : []
    if (stats.status === 'fulfilled') {
      const m = new Map()
      ;(stats.value?.by_subject || []).forEach((s) => m.set(s.subject_id, s.count || 0))
      counts.value = m
    }
    if (subjects.value.length && !activeId.value) activeId.value = subjects.value[0].id
  } catch (e) {
    errorText.value = e?.message || '无法载入科目'
  } finally {
    loading.value = false
  }
}

async function loadProfile() {
  if (!activeId.value) return
  profileLoading.value = true
  profileError.value = ''
  profile.value = null
  try {
    profile.value = await subjectProfileApi.get(activeId.value)
  } catch (e) {
    // 画像可能尚未生成 —— 这不是错误，给空态而不是报错
    profileError.value = e?.status === 404 ? '' : e?.message || '无法载入画像'
  } finally {
    profileLoading.value = false
  }
}

async function loadApproaches() {
  try {
    approaches.value = (await subjectProfileApi.approaches()) || []
  } catch {
    approaches.value = []
  }
}

watch(activeId, loadProfile)
onMounted(() => {
  loadSubjects()
  loadApproaches()
})
</script>

<template>
  <main id="main" ref="pageRoot" class="pad">
    <header class="head">
      <span class="mono">[10] REGIONS · 科目指南</span>
      <span class="mono">{{ subjects.length }} 个科目 · {{ approaches.length }} 条套路</span>
    </header>

    <UiEmpty v-if="loading" variant="skeleton" :rows="3" />
    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action><UiButton variant="solid" @click="loadSubjects">重试</UiButton></template>
    </UiEmpty>

    <div v-else class="split">
      <!-- 左：科目列表 -->
      <nav class="col reveal" data-reveal aria-label="科目列表">
        <button
          v-for="s in subjects"
          :key="s.id"
          type="button"
          class="sbtn"
          :class="{ on: s.id === activeId }"
          :aria-current="s.id === activeId ? 'true' : undefined"
          @click="activeId = s.id"
        >
          <span class="sname">{{ s.name }}</span>
          <span class="mono sc">{{ counts.get(s.id) || 0 }}</span>
        </button>
      </nav>

      <!-- 右：画像 -->
      <section class="col main reveal" data-reveal>
        <template v-if="active">
          <div class="mhead">
            <h1 class="title">{{ active.name }}</h1>
            <UiTag tone="vein" size="sm"> 错题 {{ counts.get(active.id) || 0 }} 条 </UiTag>
          </div>

          <UiEmpty v-if="profileLoading" variant="skeleton" :rows="3" />
          <UiEmpty v-else-if="profileError" title="画像载入失败" :hint="profileError">
            <template #action
              ><UiButton variant="solid" @click="loadProfile">重试</UiButton></template
            >
          </UiEmpty>

          <template v-else>
            <div v-if="lines(profile?.focus_areas).length" class="block">
              <span class="mono lab">重点范围</span>
              <ul class="ul">
                <li v-for="(l, i) in lines(profile.focus_areas)" :key="i">{{ l }}</li>
              </ul>
            </div>
            <div v-if="lines(profile?.review_tips).length" class="block">
              <span class="mono lab">复习建议</span>
              <ul class="ul">
                <li v-for="(l, i) in lines(profile.review_tips)" :key="i">{{ l }}</li>
              </ul>
            </div>

            <UiEmpty
              v-if="!lines(profile?.focus_areas).length && !lines(profile?.review_tips).length"
              title="这个科目还没有画像"
              hint="录入错题并复习一段时间后，画像会自动积累"
            />
            <p v-if="profile?.updated_at" class="mono upd">更新于 {{ profile.updated_at }}</p>
          </template>
        </template>
        <UiEmpty v-else title="没有科目" hint="先在数据库里创建科目" />
      </section>
    </div>

    <!-- 解题套路：裸字符串数组 -->
    <section v-if="approaches.length" class="block wide reveal" data-reveal>
      <span class="mono lab">解题套路（自主练习模板）</span>
      <div class="chips">
        <UiTag v-for="(a, i) in approaches" :key="i" tone="gold" size="sm">{{ a }}</UiTag>
      </div>
    </section>
  </main>
</template>

<style scoped>
.pad {
  position: relative;
  z-index: var(--z-content);
  max-width: var(--col);
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(16px, 3vh, 30px);
}
.split {
  display: grid;
  grid-template-columns: minmax(150px, 210px) minmax(0, 1fr);
  gap: clamp(16px, 2.6vw, 34px);
  align-items: start;
}
.col {
  display: flex;
  flex-direction: column;
}
nav.col {
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.sbtn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 11px 14px;
  background: var(--sky-1);
  text-align: left;
  font-size: var(--fs-sm);
  color: var(--ink-1);
  transition:
    background 0.2s var(--e-settle),
    color 0.2s var(--e-settle);
}
.sbtn:hover {
  background: var(--sky-2);
  color: var(--ink-0);
}
.sbtn.on {
  background: var(--sky-3);
  color: var(--ink-0);
  box-shadow: inset 2px 0 0 var(--redshift);
}
.sc {
  color: var(--ink-3);
}
.main {
  gap: 16px;
}
.mhead {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}
.title {
  font-size: var(--fs-h1);
  font-weight: 500;
  letter-spacing: -0.02em;
}
.block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.block.wide {
  margin-top: clamp(24px, 5vh, 50px);
}
.lab {
  color: var(--ink-3);
}
.ul {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.ul li {
  position: relative;
  padding-left: 15px;
  line-height: 1.8;
  color: var(--ink-1);
  font-size: var(--fs-sm);
}
.ul li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.72em;
  width: 5px;
  height: 1px;
  background: var(--vein);
}
.upd {
  color: var(--ink-3);
}
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
@media (max-width: 820px) {
  .split {
    grid-template-columns: 1fr;
  }
}
</style>
