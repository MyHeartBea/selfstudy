# 考研错题本

单用户考研错题管理平台：错题录入、分类筛选、知识点补充、统计分析与数据导入导出。

## 技术栈

- 后端：FastAPI + SQLite（内置 `sqlite3`），Python 3.10+
- 前端：Vue 3 + Element Plus + Vue Router + axios + GSAP + @element-plus/icons-vue，Vite 构建
- 数据库：SQLite 单文件，首次启动自动建表并写入演示数据

## Git 与 GitHub 自动同步

- 远端：https://github.com/MyHeartBea/selfstudy.git
- 默认分支：`main`，Git Credential Manager 已登录
- 工作区 `AGENTS.md` 约定：每次完成代码/数据/文档修改并验证后，
  自动执行 `git add -A`、`git commit -m "简短说明"`、`git push`，
  除非用户明确要求先不要提交/推送
- `.gitignore` 已排除 `.env`、数据库、`node_modules`、`dist`、浏览器缓存等

## 目录结构

```text
kaoyan-mistakes/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── config.py        # 应用配置
│   │   ├── database.py      # SQLite 连接与初始化
│   │   ├── schemas.py       # Pydantic 请求/响应模型
│   │   ├── models/          # 表结构定义
│   │   ├── services/        # 业务逻辑层
│   │   │   ├── formula_defaults.py  # 公式背诵库预置内容
│   │   │   └── ...
│   │   └── routers/         # API 路由层（含 formulas.py 公式库）
│   ├── main.py              # 后端启动入口
│   └── requirements.txt
├── frontend/                # Vite + Vue 3 前端
│   ├── src/
│   │   ├── api/             # axios 封装
│   │   ├── assets/          # 全局主题样式
│   │   ├── components/      # 复用组件
│   │   ├── composables/     # 基础数据与工具函数
│   │   ├── router/          # 路由配置
│   │   └── views/           # 页面视图（含 PracticeView、FormulaView）
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docs/                    # 架构与 API 文档
├── data/                    # SQLite 数据文件（自动生成）
├── start_system.bat         # 一键启动
├── main.py                  # 根目录后端启动入口
└── requirements.txt
```

## 启动方式

### 开发模式（前后端分离）

后端：

```bash
cd backend
pip install -r requirements.txt
python main.py
```

前端（新开终端）：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。

### 一键启动（幂等，可重复执行）

双击 `start_system.bat`，会自动启动后端（8000）与前端（5173）并打开浏览器；
服务已在运行时重复执行会自动跳过，不会启动出第二个实例。

- 无窗口启动：双击 `start_system_hidden.vbs`（后台隐藏运行，不弹窗）
- 开机自启：已配置 Windows 启动项 `开始菜单\启动\考研错题本自启.vbs`，
  登录后自动拉起前后端；若已手动运行过，会自动跳过。

### 生产模式（单端口）

```bash
cd frontend
npm install
npm run build
cd ../backend
python main.py
```

构建后的前端会由后端挂载，访问 `http://localhost:8000` 即可。

## 功能

- 智能录入：粘贴题干、上传题目图片，或截图后直接 Ctrl+V，AI 自动识别选项、答案、解析与知识点
- AI 解析：题干/图片自动整理为结构化错题，保存前可核对修改
- 今日复习：间隔重复排期（1/3/7/15/30 天），答对答错自动调整掌握度
- 自主练习：按记忆曲线、按错误时间、随机抽题（10/20/50 题），
  支持科目、题型、难度、知识点、来源与年份筛选，含“真题专项”
- 复习管理：错题可暂停/恢复复习，卡片显示下次复习时间；解答题可跳过 AI 批改手动标记
- 题型区分：选择题、填空题、解答题，录入、列表筛选、详情展示、复习流程各不相同
- 真题分类：真题记录年份，模拟题记录年份和卷名（如 2026 李林六套卷(一)），
  自编与其他合并为一类；支持真题专项练习、来源与年份筛选
- 填空题：输入答案后系统自动判断，支持等价答案别名、全半角与数值容差
- 解答题：AI 按步骤批改，按过程给分（0-100），指出错因、得分点、标准解答与其他解法
- 科目指南：政治、英语、数学、408 各有专属复习重点与方法建议，可编辑；
  数学与 408 支持二级科目（高等数学/线性代数、数据结构/计算机组成原理/
  操作系统/计算机网络）
- 错题列表：题型/科目/二级科目/难度/标签/思路/题干筛选，服务端分页与排序
- 错题管理：支持勾选后批量暂停/恢复/删除/改来源分类，导入前预览，
  按当前筛选结果导出
- 错题详情：正确答案高亮、解析、知识点补充、同知识点错题联动、掌握度追踪
- 知识点库：搜索、编辑摘要与科目归属、AI 自动总结、删除词条、一键练习该知识点错题；
  摘要支持 $...$ / $$...$$ 公式、Markdown 表格、列表与图片；
  支持服务端分页（page/page_size）与数据库索引（科目+二级科目、created_at、标签 UNIQUE）
- 选择题选项公式渲染：详情弹窗与复习页选项均使用 KaTeX（MathText）渲染，
  不再显示 $\alpha$、$A^T x=0$ 等原始 LaTeX 文本
- 公式背诵库：积分表、泰勒展开、等价无穷小、三角恒等式、线代与概率统计公式，
  以及英语/政治背诵素材，支持分类、搜索、增删改、公式渲染与“背诵模式”
- 统计：总错题数、今日新增、题型分布、复习趋势、今日/累计正确率、连续复习天数、
  掌握度分布、薄弱知识点、各科目统计与复习情况
- 导入导出：JSON 备份与批量导入
- 前端设计：gpt-taste 风格设计系统、GSAP 页面动效、图标侧边栏与顶栏、
  统计页 4×2 两行卡片、错题卡片 4 位倒排编号、桌面/移动端自适应

## AI 配置（可选）

未配置时，智能录入会提示配置方式，其他功能不受影响。复制 `backend/.env.example`
为 `backend/.env` 并填写：

```bash
AI_API_KEY=your-api-key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
```

支持任何 OpenAI 兼容接口，例如 DeepSeek、豆包、通义等，只需修改
`AI_BASE_URL` 与 `AI_MODEL`。

截图粘贴时，应用会先用 Windows 本地 OCR 把图片转成文字，再交给 AI 解析，
因此 DeepSeek 这类纯文本模型也能直接处理截图。首次使用需要安装本地 OCR
依赖（已写入 `backend/requirements.txt`）：

```bash
pip install winsdk
```

如果希望直接识别排版更复杂的题目图片，可配置支持图片的模型
（如 `gpt-4o-mini`、豆包视觉、通义千问 VL），本地 OCR 识别不到时会自动
退回模型自带的图片识别能力。

### 让截图识别更准

1. 配置视觉模型（推荐）：在 `backend/.env` 中增加
   `AI_VISION_MODEL=你的视觉模型名`，识别时系统会优先直接把图片交给视觉模型，
   比本地 OCR 准确得多。示例：

   ```bash
   # OpenAI
   AI_VISION_MODEL=gpt-4o-mini

   # 阿里云通义千问 VL（DashScope OpenAI 兼容接口）
   AI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   AI_VISION_MODEL=qwen-vl-max

   # 豆包视觉模型（火山方舟 OpenAI 兼容接口）
   AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
   AI_VISION_MODEL=豆包模型ID

   # 智谱 GLM-4.6V-Flash（免费视觉模型，OpenAI 兼容接口，可独立于文本模型配置）
   AI_VISION_BASE_URL=https://open.bigmodel.cn/api/paas/v4
   AI_VISION_MODEL=glm-4.6v-flash
   AI_VISION_API_KEY=你的智谱APIKey

   # 视觉模型 2：Agnes（可独立配置备用模型）
   AI_VISION_2_MODEL=agnes-2.0-flash
   AI_VISION_2_MODEL_FALLBACK=agnes-2.5-flash
   AI_VISION_2_BASE_URL=https://apihub.agnes-ai.com/v1
   AI_VISION_2_API_KEY=你的Agnes Key 1

   # 视觉模型 3：Agnes（独立通道）
   AI_VISION_3_MODEL=agnes-2.5-flash
   AI_VISION_3_BASE_URL=https://apihub.agnes-ai.com/v1
   AI_VISION_3_API_KEY=你的Agnes Key 2
   ```

   目前有直接可用的免费视觉模型：智谱 GLM-4.6V-Flash（免费、支持中文和数学截图）；
   阿里云百炼的 qwen-vl-plus（价格低、新用户有免费额度）；豆包视觉模型
   （新用户有免费额度）。三者的 API Key 分别去智谱开放平台、阿里云百炼、
   火山方舟申请，都是 OpenAI 兼容接口，填进 `backend/.env` 即可。
   也可以自己用 Ollama 部署开源视觉模型（如 Qwen2.5-VL、MiniCPM-V），
   把 `AI_BASE_URL` 指向本地 Ollama 服务，完全免费离线。
   系统会按 智谱 GLM-4.6V-Flash → Agnes-2.0-Flash → Agnes-2.5-Flash 三通道轮询，
   全部失败才退回本地 OCR + DeepSeek 文本解析，并在前端显示降级原因。

2. 不配置视觉模型时，系统会对截图做多档预处理（灰度、对比度、2-3 倍放大）
   再本地 OCR，并自动选最优结果，适合文字清晰的截图。
3. 截图尽量只包含题目本身，避免水印、弹窗和答题框干扰；数学公式较多的题目
   建议优先使用视觉模型，本地 OCR 对复杂公式识别有限。

约定：DeepSeek 负责文本/解题，GLM 只负责识图；AI 识别结果只作草稿，
最终题目、答案、解析必须人工复核并重写。

## 长期记忆（agentmemory）

本机已安装 agentmemory（0.9.28 + iii-engine 0.11.2），用于跨会话长期记忆，
程序与数据全部放在 D 盘（C 盘空间紧张）：

- 服务与数据：`D:\agentmemory`，数据目录 `D:\agentmemory\data`
- REST 端口：`3111`；实时查看器：`http://localhost:3113`
- 启动检查：`curl http://localhost:3111/agentmemory/health`
- 未启动时运行 `D:\agentmemory\start-agentmemory.cmd`
- 一键启动：`D:\agentmemory\start-agentmemory.cmd`
  （会自动拉起记忆服务 + 转录监听器）
- MCP：Codex 已注册 `agentmemory`
  （`node D:\agentmemory\node_modules\@agentmemory\mcp\bin.mjs`，
  `AGENTMEMORY_URL=http://localhost:3111`），共 53 个 memory 工具；
  重启 Codex 后即可用 `memory_recall` / `memory_save` / `memory_smart_search`
- 官方 16 个技能已安装到 `~/.codex/skills`
- hook：官方插件 `agentmemory-hooks@agentmemory-local` 已安装启用；
  当前 Codex 桌面版不执行插件 hooks，实际自动记录由
  `D:\agentmemory\transcript-watcher.mjs` 完成——每 5 秒扫描两类会话写入 agentmemory：
  Codex CLI（`~/.codex/sessions` 的 rollout JSONL，字节偏移增量）与
  DSH 图形界面（`~/.dsh/sessions/**/session.jsonl.zstd`，追加式多帧 zstd，按帧数增量）；
  user 提问以 `prompt_submit`、工具调用/结果与助手回复以 `post_tool_use` 提交，
  观察立即可被 `memory_recall` / `memory_smart_search` 搜索；进度状态在
  `D:\agentmemory\watcher-state.json`
- 新窗口用法：直接说“召回记忆”，或调用 `memory_recall` / `memory_smart_search`

## 已安装 Skills（全局 + 工作区）

- `gpt-taste`：高级网页设计技能（Elite UX/UI + GSAP Motion），
  来源 [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)；
  全局位置 `D:\Codex\home\skills\gpt-taste`，
  工作区位置 `.agents\skills\gpt-taste`
- `caveman`：token 压缩技能（回答更短但技术信息不减），
  来源 [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)；
  全局位置 `D:\Codex\home\skills\caveman`，
  工作区位置 `.agents\skills\caveman`

新窗口做前端时优先按 `gpt-taste` 规则设计；希望省 token 时使用 `caveman`。

## 数据安全

- 全部数据保存在 `data/kaoyan_mistakes.db`，升级、重启、迁移都不会删除数据。
- 演示数据只在数据库文件**第一次创建**时写入，之后永远不会自动重置。
- 每次启动后端前会自动备份数据库到 `data/backups/`，保留最近 20 份，
  误操作时可手动恢复。
- 结构升级只做“新增字段/新增表”，不会重建或清空已有表。

## API 文档

后端启动后访问 `http://localhost:8000/docs` 查看 Swagger 文档，接口约定见 [docs/api.md](docs/api.md)。
