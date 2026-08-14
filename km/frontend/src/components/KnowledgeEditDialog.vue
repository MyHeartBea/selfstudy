<script setup>
import { computed, reactive, ref, toRef, watch } from 'vue'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import { baseData } from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import { useTagInput } from '../composables/useTagInput'
import RichText from './RichText.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  row: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const saving = ref(false)
const form = reactive({
  id: null,
  tag_name: '',
  subject_id: null,
  sub_subject_id: null,
  summary: '',
  related_tags: [],
})

const { subSubjectOptions } = useSubSubject(toRef(form, 'subject_id'))
const {
  input: relatedTagInput,
  add: addRelatedTag,
  flush: flushRelatedTag,
  remove: removeRelatedTag,
} = useTagInput(form, 'related_tags')

watch(
  () => props.row,
  (row) => {
    if (row) {
      form.id = row.id
      form.tag_name = row.tag_name
      form.subject_id = row.subject_id || null
      form.sub_subject_id = row.sub_subject_id || null
      form.summary = row.summary || ''
      form.related_tags = (row.related_tags || []).slice()
    }
  },
  { immediate: true },
)

function onSubjectChange() {
  form.sub_subject_id = null
}

async function save() {
  saving.value = true
  try {
    await request.patch(`/knowledge/${form.id}`, {
      summary: form.summary,
      subject_id: form.subject_id || null,
      sub_subject_id: form.sub_subject_id || null,
      related_tags: form.related_tags,
    })
    ElMessage.success('知识点已更新')
    emit('saved')
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="编辑知识点摘要" width="600px" :close-on-click-modal="false">
    <el-form label-width="90px">
      <el-form-item label="标签名">
        <el-input :model-value="form.tag_name" disabled />
      </el-form-item>
      <el-form-item label="所属科目">
        <el-select
          v-model="form.subject_id"
          clearable
          placeholder="通用"
          style="width: 100%"
          @change="onSubjectChange"
        >
          <el-option
            v-for="s in baseData.subjects"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="二级科目">
        <el-select
          v-model="form.sub_subject_id"
          clearable
          placeholder="全部"
          style="width: 100%"
          :disabled="!subSubjectOptions.length"
        >
          <el-option
            v-for="s in subSubjectOptions"
            :key="s.id"
            :label="s.name"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="摘要">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="8"
          placeholder="补充该知识点的讲解、易错点、扩展内容；支持 $...$ 公式、Markdown 表格和列表"
        />
      </el-form-item>
      <el-form-item label="关联知识点">
        <div class="tag-editor">
          <el-tag
            v-for="t in form.related_tags"
            :key="t"
            closable
            type="warning"
            class="tag-chip"
            @close="removeRelatedTag(t)"
          >
            {{ t }}
          </el-tag>
          <el-input
            v-model="relatedTagInput"
            placeholder="输入关联标签后按回车，如：地址转换"
            size="small"
            style="width: 260px"
            @keyup.enter="addRelatedTag"
            @blur="flushRelatedTag"
          />
        </div>
      </el-form-item>
      <div v-if="form.summary.trim()" class="knowledge-preview">
        <div class="section-label">预览</div>
        <RichText :text="form.summary" />
      </div>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>
