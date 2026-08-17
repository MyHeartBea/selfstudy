<template>
  <div v-if="images && images.length" class="question-images">
    <figure
      v-for="(img, index) in images"
      :key="index"
      class="question-image"
    >
      <img :src="imageSrc(img)" alt="题干配图" loading="lazy" />
    </figure>
  </div>
</template>

<script setup>
const props = defineProps({
  images: { type: Array, default: () => [] },
  maxWidth: { type: Number, default: 360 },
})

function imageSrc(item) {
  if (!item) return ''
  // 新上传的 data URL 直接可用；已保存的是相对路径 images/xxx
  return item.startsWith('data:') ? item : '/images/' + item
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
}
.question-image img {
  display: block;
  max-width: v-bind(maxWidth + 'px');
  max-height: 240px;
  object-fit: contain;
}
</style>
