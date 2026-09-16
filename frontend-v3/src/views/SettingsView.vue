<!--
  SettingsView —— 设置与数据
  ---------------------------------------------------------------------------
  这一页的定位不是"功能罗列"，而是**把 v2/v3 并行期最要紧的两件事放上台面**：
    1. 数据导出（换库前自查、以及"数据一致"的第三方凭证）
    2. 当前前端来源（FRONTEND_DIST 指向哪一份）——让"我现在用的是 v2 还是 v3"可自查

  刻意不做的事：不在前端保存任何密钥、不做任何后端配置写入
  （单用户本地工具，配置改动应走 .env 与脚本，避免浏览器里出现"能改后端行为"的入口）。

  契约：
    GET /api/health - { status, version }
    GET /api/export - { exported_at, mistakes[], knowledge[] }
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import { dataApi } from '../core/api/extra'
import { __client } from '../core/api'
import { toast } from '../ui/toast'
import { usePageMotion } from '../design/usePageMotion'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiTag from '../ui/UiTag.vue'

const pageRoot = ref(null)
usePageMotion(pageRoot, { stagger: 55 })

const health = ref(null)
const healthError = ref('')
const exporting = ref(false)
const counts = ref(null)
const countsError = ref('')

/** 当前由哪一份前端提供页面：通过后端 SPA 回退时无法直接读取，
    这里用"构建期注入的常量"给出版本号（vite define）。 */
const buildInfo = computed(() => ({
  frontend: 'v3（夜航星图）',
  builtAt: __BUILD_TIME__,
}))

async function loadHealth() {
  healthError.value = ''
  try {
    health.value = await (async () => {
      const res = await __client.get('/health', { baseURL: '' })
      return res.data?.data || res.data
    })()
  } catch (e) {
    healthError.value = e?.message || '无法读取后端状态'
  }
}

/** 只取数量，不把整份导出读进内存展示（可能很大） */
async function loadCounts() {
  countsError.value = ''
  try {
    const data = await dataApi.exportAll()
    counts.value = {
      exportedAt: data?.exported_at || '',
      mistakes: (data?.mistakes || []).length,
      knowledge: (data?.knowledge || []).length,
    }
  } catch (e) {
    countsError.value = e?.message || '无法读取数据统计'
  }
}

async function downloadJson() {
  exporting.value = true
  try {
    await dataApi.downloadJson(`km-v2-export-${new Date().toISOString().slice(0, 10)}.json`)
    toast.success('导出已开始下载')
  } catch (e) {
    toast.error(e?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadHealth()
  loadCounts()
})
</script>

<template>
  <main id="main" ref="pageRoot" class="pad">
    <header class="head">
      <span class="mono">[09] SETTINGS · 设置与数据</span>
      <span class="mono">{{ buildInfo.builtAt }}</span>
    </header>

    <!-- 版本与来源：并行期最要紧的自查信息 -->
    <section class="leaf reveal" data-reveal>
      <h2 class="kh">版本与来源</h2>
      <div class="rows">
        <div class="row">
          <span class="k">当前前端</span>
          <span class="v">{{ buildInfo.frontend }}</span>
        </div>
        <div class="row">
          <span class="k">构建时间</span>
          <span class="v mono">{{ buildInfo.builtAt }}</span>
        </div>
        <div class="row">
          <span class="k">后端状态</span>
          <span class="v">
            <template v-if="health">
              <UiTag :tone="health.status === 'ok' ? 'vein' : 'red-shift'" size="sm" dot>
                {{ health.status }}
              </UiTag>
              <span class="mono dim">v{{ health.version }}</span>
            </template>
            <span v-else-if="healthError" class="mono err">{{ healthError }}</span>
            <span v-else class="mono dim">读取中</span>
          </span>
        </div>
      </div>
      <p class="hint mono">
        v2 与 v3 共用同一个后端与同一张数据库。切换前端的唯一入口是
        <code>scripts/serve_frontend.ps1</code>（改 FRONTEND_DIST），不要手改路径。
      </p>
    </section>

    <!-- 数据 -->
    <section class="leaf reveal" data-reveal>
      <h2 class="kh">数据</h2>
      <div v-if="counts" class="rows">
        <div class="row">
          <span class="k">错题</span>
          <span class="v mono">{{ counts.mistakes }} 条</span>
        </div>
        <div class="row">
          <span class="k">知识点</span>
          <span class="v mono">{{ counts.knowledge }} 条</span>
        </div>
        <div class="row">
          <span class="k">导出时间戳</span>
          <span class="v mono">{{ counts.exportedAt }}</span>
        </div>
      </div>
      <p v-else-if="countsError" class="mono err">{{ countsError }}</p>
      <UiEmpty v-else variant="skeleton" :rows="2" />

      <div class="acts">
        <UiButton variant="solid" :loading="exporting" @click="downloadJson">
          导出全部数据（JSON）
        </UiButton>
        <UiButton variant="quiet" @click="loadCounts">刷新统计</UiButton>
      </div>
      <p class="hint">
        导出走 <code>GET /api/export</code>，包含错题与知识点的完整字段。
        换库、迁移或核对数据一致性时，先用这份文件留底。
      </p>
    </section>

    <!-- 关于这一版 -->
    <section class="leaf reveal" data-reveal>
      <h2 class="kh">关于这一版</h2>
      <p class="about">
        夜航星图的隐喻：<b>未掌握的是暗，已掌握的是光</b>。一道错题就是一颗星，
        复习次数决定亮度，科目决定颜色，反复错的题会红移。
      </p>
      <ul class="facts">
        <li><span class="mono k">动效</span>六条原语：沉降 / 红移 / 描绘 / 扫描 / 聚焦 / 漂移</li>
        <li><span class="mono k">降级</span>系统开启「减少动态效果」时全部瞬时到位，信息不丢</li>
        <li><span class="mono k">图标</span>全部本地 Lucide SVG，零 emoji、零字符图标</li>
        <li><span class="mono k">可访问</span>键盘可达、焦点可见、错误用 aria 关联而非只变色</li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.pad {
  position: relative;
  z-index: var(--z-content);
  max-width: 880px;
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(8px, 2vh, 20px);
}
.leaf {
  padding: 20px 22px 22px;
  background: var(--sky-1);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.kh {
  font-size: var(--fs-h2);
  font-weight: 500;
  letter-spacing: -0.01em;
  margin-bottom: 14px;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 11px 14px;
  background: var(--sky-0);
  font-size: var(--fs-sm);
}
.k {
  color: var(--ink-2);
  min-width: 7em;
}
.v {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: var(--ink-0);
}
.dim {
  color: var(--ink-3);
}
.err {
  color: var(--redshift);
}
.acts {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.hint {
  margin-top: 12px;
  color: var(--ink-3);
  font-size: var(--fs-sm);
  line-height: 1.8;
}
.hint code,
.about code {
  font-family: var(--font-mono);
  color: var(--ink-1);
  background: var(--sky-2);
  padding: 1px 5px;
  border-radius: 2px;
}
.about {
  color: var(--ink-1);
  line-height: 1.9;
}
.about b {
  color: var(--ink-0);
  font-weight: 500;
}
.facts {
  list-style: none;
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.facts li {
  display: flex;
  gap: 12px;
  font-size: var(--fs-sm);
  color: var(--ink-1);
  line-height: 1.7;
}
.facts .k {
  min-width: 4em;
  color: var(--ink-3);
}
</style>
