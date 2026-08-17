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
    <el-image-viewer
      v-if="viewerVisible"
      :url-list="previewList"
      :initial-index="viewerIndex"
      @close="closePreview"
    />
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'

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
  // 锁定页面滚动，避免图片预览时滚轮同时滚动页面
  savedOverflow.value = document.body.style.overflow
  document.body.style.overflow = 'hidden'
}

function closePreview() {
  viewerVisible.value = false
  document.body.style.overflow = savedOverflow.value
}

onUnmounted(() => {
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
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
  background: var(--el-bg-color, #fff);
  cursor: zoom-in;
}
.question-image img {
  display: block;
  max-width: v-bind(maxWidth + 'px');
  max-height: 280px;
  object-fit: contain;
}
</style>
