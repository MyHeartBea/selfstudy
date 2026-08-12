<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import { sourceTypeColor, subjectColor } from '../composables/useBaseData'

const loading = ref(false)
const router = useRouter()
const stats = ref({
  total_mistakes: 0,
  today_new: 0,
  by_subject: [],
  by_sub_subject: [],
  by_question_type: [],
  by_source_type: [],
})
const reviewStats = ref({
  due_today: 0,
  reviewed_today: 0,
  accuracy_today: 0,
  total_accuracy: 0,
  avg_mastery: 0,
  total_reviews: 0,
  streak_days: 0,
  mastery_distribution: [],
  weakest_tags: [],
  last_7_days: [],
  by_subject: [],
})

const dayList = computed(() => reviewStats.value.last_7_days || [])
const maxDayCount = computed(() =>
  Math.max(1, ...dayList.value.map((item) => item.count)),
)

function barHeight(count) {
  return Math.max(4, Math.round((count / maxDayCount.value) * 120))
}

async function loadStats() {
  loading.value = true
  try {
    const [res, reviewRes] = await Promise.all([
      request.get('/stats'),
      request.get('/reviews/stats'),
    ])
    stats.value = res.data.data
    reviewStats.value = reviewRes.data.data
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function percentOf(count) {
  const max = Math.max(1, ...(stats.value.by_subject || []).map((item) => item.count))
  return Math.round((count / max) * 100)
}

function practiceTag(tag) {
  router.push({
    path: '/review',
    query: { mode: 'curve', count: 10, tag },
  })
}

onMounted(loadStats)
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Learning Analytics</div>
        <h2>学习统计</h2>
        <p class="view-desc">用数据看复习节奏，找到下一轮该攻克的薄弱点。</p>
      </div>
    </div>

    <div class="stats-cards" data-reveal>
      <div class="stat-card total">
        <el-icon class="stat-icon"><DataAnalysis /></el-icon>
        <div>
          <div class="stat-value">{{ stats.total_mistakes }}</div>
          <div class="stat-label">总错题数</div>
        </div>
      </div>
      <div class="stat-card today">
        <el-icon class="stat-icon"><DocumentAdd /></el-icon>
        <div>
          <div class="stat-value">{{ stats.today_new }}</div>
          <div class="stat-label">今日新增</div>
        </div>
      </div>
    </div>

    <div class="stats-cards" data-reveal>
      <div class="stat-card due">
        <el-icon class="stat-icon"><RefreshLeft /></el-icon>
        <div>
          <div class="stat-value">{{ reviewStats.due_today }}</div>
          <div class="stat-label">今日待复习</div>
        </div>
      </div>
      <div class="stat-card done">
        <el-icon class="stat-icon"><CircleCheck /></el-icon>
        <div>
          <div class="stat-value">{{ reviewStats.reviewed_today }}</div>
          <div class="stat-label">今日已复习</div>
        </div>
      </div>
      <div class="stat-card accuracy">
        <el-icon class="stat-icon"><TrendCharts /></el-icon>
        <div>
          <div class="stat-value">{{ reviewStats.accuracy_today }}%</div>
          <div class="stat-label">今日正确率</div>
        </div>
      </div>
      <div class="stat-card mastery">
        <el-icon class="stat-icon"><Star /></el-icon>
        <div>
          <div class="stat-value">{{ reviewStats.avg_mastery }}</div>
          <div class="stat-label">平均掌握度</div>
        </div>
      </div>
      <div class="stat-card totalacc">
        <el-icon class="stat-icon"><Medal /></el-icon>
        <div>
          <div class="stat-value">{{ reviewStats.total_accuracy }}%</div>
          <div class="stat-label">累计正确率</div>
        </div>
      </div>
      <div class="stat-card streak">
        <el-icon class="stat-icon"><Calendar /></el-icon>
        <div>
          <div class="stat-value">{{ reviewStats.streak_days }} 天</div>
          <div class="stat-label">连续复习</div>
        </div>
      </div>
    </div>

    <el-card shadow="never" class="subject-stats" data-reveal>
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">掌握度分布</span>
      </template>
      <div class="mastery-grid">
        <div v-for="item in reviewStats.mastery_distribution" :key="item.mastery" class="mastery-item">
          <div class="mastery-level">
            {{ item.mastery === 0 ? '新题' : `${item.mastery} 级` }}
          </div>
          <div class="mastery-count">{{ item.count }}</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="subject-stats">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">题型分布</span>
      </template>
      <div class="mastery-grid">
        <div v-for="item in stats.by_question_type" :key="item.question_type" class="mastery-item">
          <div class="mastery-level">{{ item.name }}</div>
          <div class="mastery-count">{{ item.count }}</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="subject-stats">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">题目来源分布</span>
      </template>
      <div
        v-for="s in stats.by_source_type"
        :key="s.source_type"
        class="subject-stat-row"
      >
        <div class="subject-name">{{ s.name }}</div>
        <el-progress
          :percentage="percentOf(s.count)"
          :stroke-width="14"
          :show-text="false"
          :color="sourceTypeColor(s.source_type)"
        />
        <div class="subject-nums">
          <span>{{ s.count }} 题</span>
        </div>
      </div>
      <el-empty
        v-if="!stats.by_source_type || !stats.by_source_type.length"
        description="暂无题目来源数据"
        :image-size="80"
      />
    </el-card>

    <el-card shadow="never" class="subject-stats">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">近 7 天复习趋势</span>
      </template>
      <div v-if="dayList.length" class="day-bars">
        <div v-for="d in dayList" :key="d.day" class="day-bar-item">
          <div class="day-bar" :style="{ height: barHeight(d.count) + 'px' }"></div>
          <span class="day-label">{{ d.day.slice(5) }}</span>
          <span class="day-count">{{ d.count }}</span>
        </div>
      </div>
      <el-empty v-else description="近 7 天暂无复习记录" />
    </el-card>

    <el-card shadow="never" class="subject-stats">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">薄弱知识点</span>
      </template>
      <el-table v-if="reviewStats.weakest_tags.length" :data="reviewStats.weakest_tags" stripe>
        <el-table-column prop="tag_name" label="知识点" min-width="180" />
        <el-table-column prop="wrong_count" label="累计答错次数" width="150" />
        <el-table-column prop="mistake_count" label="关联错题数" width="150" />
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="practiceTag(row.tag_name)">
              练这组题
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else
        description="暂无薄弱知识点"
        :image-size="80"
      />
    </el-card>

    <el-card shadow="never" class="subject-stats">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">各科目统计</span>
      </template>
      <div
        v-for="s in stats.by_subject"
        :key="s.subject_id"
        class="subject-stat-row"
      >
        <div class="subject-name">{{ s.name }}</div>
        <el-progress
          :percentage="percentOf(s.count)"
          :stroke-width="14"
          :show-text="false"
          :color="subjectColor(s.subject_id)"
        />
        <div class="subject-nums">
          <span>{{ s.count }} 题</span>
          <span class="avg">平均难度 {{ Number(s.avg_difficulty).toFixed(1) }}</span>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="subject-stats">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">各二级科目统计</span>
      </template>
      <div
        v-for="s in stats.by_sub_subject"
        :key="s.sub_subject_id"
        class="subject-stat-row"
      >
        <div class="subject-name">
          {{ s.subject_name }} · {{ s.name }}
        </div>
        <el-progress
          :percentage="percentOf(s.count)"
          :stroke-width="14"
          :show-text="false"
          :color="subjectColor(s.subject_id)"
        />
        <div class="subject-nums">
          <span>{{ s.count }} 题</span>
          <span class="avg">平均难度 {{ Number(s.avg_difficulty).toFixed(1) }}</span>
        </div>
      </div>
      <el-empty
        v-if="!stats.by_sub_subject || !stats.by_sub_subject.length"
        description="暂无二级科目数据"
        :image-size="80"
      />
    </el-card>

    <el-card shadow="never" class="subject-stats">
      <template #header>
        <span style="font-weight: 700; color: #1d3a5f">各科目复习情况</span>
      </template>
      <el-table :data="reviewStats.by_subject" stripe>
        <el-table-column prop="name" label="科目" min-width="180" />
        <el-table-column prop="mistake_count" label="错题数" width="120" />
        <el-table-column prop="review_count" label="复习次数" width="120" />
        <el-table-column label="正确率" width="180">
          <template #default="{ row }">{{ row.accuracy }}%</template>
        </el-table-column>
        <el-table-column prop="wrong_count" label="累计答错" width="120" />
      </el-table>
    </el-card>
  </div>
</template>
