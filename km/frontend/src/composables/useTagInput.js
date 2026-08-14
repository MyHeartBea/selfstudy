import { ref } from 'vue'

/**
 * 标签输入器：add / flush / remove 三件套，统一回车与失焦行为。
 * 原先该逻辑在 MistakeForm（知识点标签、可接受答案）、
 * KnowledgeEditDialog（关联知识点）、SubjectGuide（复习重点）中重复。
 *
 * @param {object} target reactive 表单对象
 * @param {string} key     标签数组所在的属性名（如 'knowledge_tags'）
 */
export function useTagInput(target, key) {
  const input = ref('')

  function add() {
    const tag = input.value.trim()
    if (tag && !target[key].includes(tag)) {
      target[key].push(tag)
    }
    input.value = ''
  }

  function flush() {
    if (input.value.trim()) add()
  }

  function remove(tag) {
    target[key] = target[key].filter((item) => item !== tag)
  }

  return { input, add, flush, remove }
}
