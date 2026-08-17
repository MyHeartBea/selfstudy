<template>
  <div v-if="images && images.length" class="question-images">
    <figure
      v-for="(img, index) in images"
      :key="index"
      class="question-image"
      :title="'点击放大（' + (index + 1) + '/' + images.length + '）'"
    >
      <el-image
        :src="imageSrc(img)"
        :preview-src-list="previewList"
        :initial-index="index"
        fit="contain"
        preview-teleported
        loading="lazy"
        class="question-image-el"
      />
    </figure>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  images: { type: Array, default: () => [] },
  maxWidth: { type: Number, default: 520 },
})

const previewList = computed(() =>
  (props.images || []).map((item) => imageSrc(item)),
)

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
.question-image-el {
  display: block;
  max-width: v-bind(maxWidth + 'px');
  max-height: 300px;
}
.question-image-el :deep(img) {
  width: auto;
  max-width: 100%;
  max-height: 300px;
  object-fit: contain;
}
</style>
