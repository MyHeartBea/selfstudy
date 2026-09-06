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

## 前端（墨韵 2.0，2026-09 重构）

设计系统「墨韵 2.0」：宣纸 · 松烟墨 · 朱砂印 · 洒金；令牌集中在 `styles/tokens.css`
（v1 变量名沿用，深浅主题 = `[data-theme='dark']` 覆盖），硬规则与组件 API 见根 `AGENTS.md` 第 6.5 节。

- `api/request.js`：axios 实例与统一错误提示（支持 `silent` 选项抑制全局 toast）。
- `styles/tokens.css + base.css`：设计令牌（色彩/氛围/海拔/动效/字阶）与全局样式（选项判分反馈链等）。
- `views/AppLayout.vue + ui/AmbientLayer.vue + ui/DockNav.vue`：外壳三件套——
  环境氛围层（底纱/极光/视差光斑/墨渍/浮尘，单 rAF 循环，reduced-motion 全关）、
  顶部悬浮玻璃 Dock（滑动 pill/悬浮标签/复习环）、「墨漫纸面」rAF 换肤（clip-path 圆形扩散，防重入锁）。
- `ui/`：自建基件库（零 UI 框架依赖）——按钮（印章渐变+涟漪）、玻璃弹窗/下拉、
  GlassCard（渐变描边+流光+#badge 骑缝）、MetricTile、RingProgress、AreaChart（手写 SVG，
  颜色用 CSS 变量自动跟主题）、BarRow、Heatmap、Skeleton、StageBadge（骑缝徽章）等。
- `views/`：10 个页面 + `/design` 组件画廊（不入导航）。统计=Bento 网格；复习=沉浸舞台
  （流光进度线/骑缝徽章/落章完成）；生词闪卡=真 3D 翻面；公式背诵=翻卡 reveal。
- `composables/`：useBaseData（科目数据单例）、useMistakeFilters、useBulkActions、
  useImportExport、useSubSubject、useTagInput、mistakeDraft 等逻辑复用单元（重构未动）。
- `router/`：10 个路由全部懒加载，嵌套在 AppLayout 下；路由过渡带显式 duration
  （后台标签页 transitionend 被推迟，防切页卡死）。
- `components/`：错题卡片、详情对话框、录入表单、三种题型作答组件、EnglishAnalysisPanel
  精读面板、MathText/RichText 文本渲染通道（AI 文本禁止裸插值）等。
- 字体：`@fontsource/noto-serif-sc` 本地子集（unicode-range 分片按需加载，离线可用，
  无 CDN）；开场编排等字体就绪后触发（`body.app-ready`）。

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
