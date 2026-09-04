/**
 * 错题表单的默认值单点。
 * 原先 MistakeForm.emptyForm() 与 CaptureView.buildManualDraft() 各维护一份，
 * 字段容易漂移；统一收敛到这里。
 *
 * @param {string} question 初始题干（图片/文本解析失败回退时使用）
 */
export function createMistakeDraft(question = '') {
  return {
    subject_id: null,
    sub_subject_id: null,
    question_type: 'choice',
    question,
    option_a: '',
    option_b: '',
    option_c: '',
    option_d: '',
    correct_answer: '',
    answer_aliases: [],
    analysis: '',
    difficulty: 3,
    difficulty_points: '',
    knowledge_tags: [],
    approach: '',
    source: '',
    source_type: 'other',
    source_year: '',
    source_name: '',
    images: [],
    // 英语整篇精读（可选）：挂在错题上的附加内容
    passage_text: '',
    passage_translation: '',
    english_sentences: [],
    english_phrases: [],
    english_words: [],
    english_questions: [],
  }
}
