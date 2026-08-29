<script setup>
/** 题干配图缩略图 + 点击放大灯箱 */
import { computed, onUnmounted, ref } from 'vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  images: { type: Array, default: () => [] },
  maxWidth: { type: Number, default: 520 },
})

const viewerVisible = ref(false)
const viewerIndex = ref(0)
const savedOverflow = ref('')

const previewList = computed(() =>
  (props.images || []).map((item) => imageSrc(item)),
)

function openPreview(index) {
  viewerIndex.value = index
  viewerVisible.value = true
  savedOverflow.value = document.body.style.overflow
  document.body.style.overflow = 'hidden'
}

function closePreview() {
  viewerVisible.value = false
  document.body.style.overflow = savedOverflow.value
}

function step(delta) {
  const total = previewList.value.length
  viewerIndex.value = (viewerIndex.value + delta + total) % total
}

function onKey(event) {
  if (!viewerVisible.value) return
  if (event.key === 'Escape') closePreview()
  if (event.key === 'ArrowLeft') step(-1)
  if (event.key === 'ArrowRight') step(1)
}

if (typeof window !== 'undefined') {
  window.addEventListener('keydown', onKey)
}

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  if (viewerVisible.value) {
    document.body.style.overflow = savedOverflow.value
  }
})

function imageSrc(item) {
  if (!item) return ''
  // 新上传的 data URL 直接可用；已保存的是相对路径 images/xxx.png
  if (item.startsWith('data:')) return item
  const name = item.startsWith('images/') ? item.slice('images/'.length) : item
  return '/images/' + name
}
</script>

<template>
  <div v-if="images && images.length" class="question-images">
    <figure
      v-for="(img, index) in images"
      :key="index"
      class="question-image"
      :title="'点击放大（' + (index + 1) + '/' + images.length + '）'"
      @click="openPreview(index)"
    >
      <img :src="imageSrc(img)" alt="题干配图" loading="lazy" />
    </figure>

    <Teleport to="body">
      <Transition name="lightbox">
        <div v-if="viewerVisible" class="lightbox" @click.self="closePreview">
          <button class="lb-close" aria-label="关闭" @click="closePreview"><Icon name="x" :size="18" /></button>
          <button v-if="previewList.length > 1" class="lb-nav lb-prev" aria-label="上一张" @click.stop="step(-1)"><Icon name="chevron-left" :size="20" /></button>
          <img :src="previewList[viewerIndex]" alt="预览" class="lb-img" @click.stop />
          <button v-if="previewList.length > 1" class="lb-nav lb-next" aria-label="下一张" @click.stop="step(1)"><Icon name="chevron-right" :size="20" /></button>
          <div v-if="previewList.length > 1" class="lb-count">{{ viewerIndex + 1 }} / {{ previewList.length }}</div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.question-images {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 8px 0;
}
.question-image {
  margin: 0;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  cursor: zoom-in;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.question-image:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-1);
}
.question-image img {
  display: block;
  max-width: v-bind(maxWidth + 'px');
  max-height: 280px;
  object-fit: contain;
}

.lightbox {
  position: fixed;
  inset: 0;
  z-index: 1400;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(12, 10, 8, 0.86);
  backdrop-filter: blur(4px);
}
.lb-img {
  max-width: min(1100px, 88vw);
  max-height: 86vh;
  object-fit: contain;
  border-radius: 10px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
}
.lb-close, .lb-nav {
  position: absolute;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.lb-close:hover, .lb-nav:hover { background: rgba(255, 255, 255, 0.24); }
.lb-close { top: 20px; right: 20px; }
.lb-prev { left: 20px; top: 50%; transform: translateY(-50%); }
.lb-next { right: 20px; top: 50%; transform: translateY(-50%); }
.lb-count {
  position: absolute;
  bottom: 22px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.8);
  font-size: 12.5px;
  letter-spacing: 0.08em;
}
.lightbox-enter-active, .lightbox-leave-active { transition: opacity 0.18s; }
.lightbox-enter-from, .lightbox-leave-to { opacity: 0; }
</style>
