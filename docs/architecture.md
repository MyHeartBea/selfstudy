# 架构说明

## 总体分层

```text
浏览器（Vue 3 + Element Plus）
        │ axios（/api）
        ▼
FastAPI 路由层 routers/
        │
        ▼
业务服务层 services/
        │
        ▼
SQLite（sqlite3 + 表结构 models/）
```

## 后端

- `config.py`：集中管理端口、数据库路径、前端构建产物路径。
- `models/tables.py`：SQLite 表结构 DDL 与错题字段常量，保证表结构可维护。
- `database.py`：连接管理、建表、种子数据初始化、行转字典与标签规范化。
- `schemas.py`：Pydantic 请求模型，接口文档自动生成。
- `services/`：错题、知识点、统计等业务逻辑，不直接依赖 HTTP 层。
- `routers/`：路由与参数解析，统一返回 `{code, data, message}`。
- `main.py`：应用装配，CORS、参数校验异常包装、静态资源挂载。

## 前端

- `api/request.js`：axios 实例与统一错误提示（支持 `silent` 选项抑制全局 toast）。
- `composables/`：useBaseData（科目数据单例）、useMistakeFilters、useBulkActions、
  useImportExport、useSubSubject、useTagInput、mistakeDraft 等逻辑复用单元。
- `router/`：错题列表、智能录入、今日复习、自主练习、知识点库、公式背诵、
  科目指南、学习统计、错题编辑（共 9 个路由，全部懒加载，嵌套在 Layout 下）。
- `components/`：错题卡片、详情对话框、录入表单、三种题型作答组件、知识点编辑对话框、
  公式/表格渲染（MathText/RichText）等 13 个组件。
- `views/`：10 个页面级组件（Layout、MistakeList、CaptureView、ReviewView、PracticeView、
  KnowledgeBase、FormulaView、SubjectGuide、Stats、MistakeCreate）。

## 关键联动

1. 录入错题时，后端遍历 `knowledge_tags`，缺失标签自动写入 `knowledge_base`，
   并同步维护 `mistake_tag_map` 关联表（按标签检索走索引，避免全表扫描）。
2. 错题详情接口返回 `knowledge_extra`（第一个标签的摘要）与
   `related_mistakes`（同标签其他错题，最多 5 条）。
3. 统计接口按科目聚合，包含零错题科目，便于前端展示完整进度。
4. 导出生成完整 JSON；导入时逐条校验并复用自动建标签逻辑。
5. 启动时自动备份数据库到 `data/backups/`（保留最近 20 份）；
   数据库结构升级通过 `app_meta.migration_version` 门控（当前 v3）。
6. AI 端点带每分钟限流；设置 `API_TOKEN` 后所有接口需鉴权（可选）。
