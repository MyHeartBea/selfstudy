# 研错本（考研错题本 km-v2）

单用户考研错题管理平台：错题录入（手动 / AI 文本 / 三通道视觉识图）、知识点库、
公式背诵、生词本（英语单词闪卡）、统计分析与数据导入导出。

> **2026-08-29 起本仓库为唯一在用系统**（D:\km-v2，生产端口 8000）。
> 旧系统（C盘 work/km，Element Plus 版）已弃用并停服；开机自启动已指向本系统。
> 本提交延续原仓库历史，属于对旧项目的整体重构替代。

## 技术栈

- 后端：FastAPI + SQLite（内置 sqlite3，无 ORM），Python 3.10+
- 前端：Vue 3 + 自建设计系统「墨·纸·印」（零 UI 框架依赖）+ Vue Router + axios + KaTeX，Vite 构建
- 数学公式：KaTeX（$...$ / $$...$$），Markdown 表格/列表渲染
- 数据库：SQLite 单文件 `data/kaoyan_mistakes.db`，首次启动自动建表写入演示数据；启动前自动备份（保留 20 份）

## 目录结构

```text
km-v2/（仓库根 = D:\km-v2）
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── config.py       # 端口(8000)/路径/AI 参数
│   │   ├── database.py     # 连接、建表、迁移门控(v5)、备份
│   │   ├── schemas.py      # Pydantic 模型
│   │   ├── models/tables.py# DDL
│   │   ├── services/       # 业务逻辑（mistake/review/knowledge/formula/vocab/stats/ai/answer）
│   │   └── routers/        # mistakes/reviews/knowledge/formulas/vocab/subjects/stats/transfer/ai/system
│   ├── main.py         # 启动入口（127.0.0.1:8000）
│   ├── tests/          # 40 个单元/接口测试（临时库，不碰真实数据）
│   └── .env            # AI 密钥（不入库）
├── frontend/           # Vue 3 前端（自建组件库 src/ui/）
│   └── src/{views,components,ui,composables,utils,styles,directives}
├── scripts/vision_request.py   # 三通道视觉识别脚本（DSH vision 技能调用）
├── docs/               # api.md / architecture.md / notes/
├── data/               # SQLite 数据（不入库）
├── start_backend.cmd   # Windows 一键启动
└── .github/workflows/  # CI（后端测试 + 前端构建）
```

## 启动方式

### 生产模式（默认，开机自启动用）

```bash
cd backend
pip install -r requirements.txt
python main.py
```

浏览器访问 **http://127.0.0.1:8000**（后端挂载 `frontend/dist`，若 dist 不存在请先构建）。

前端构建：

```bash
cd frontend
npm install
npm run build
```

### 开发模式（前后端分离，热更新）

后端照常启动（8000），另开终端：

```bash
cd frontend
npm install
npm run dev   # http://127.0.0.1:5174，已代理 /api 与 /images 到 8000
```

### 一键启动

双击 `start_backend.cmd`。开机自启动：开始菜单启动文件夹中的 `考研错题本自启.vbs`
（无窗口拉起后端并打开浏览器，已在运行则跳过；日志 `D:\temp\km-launch.log`）。

## 功能

- **错题库**：题型按科目感知（数学/408：选择·填空·解答；政治：单选·多选·分析；英语：客观题·翻译·作文），
  筛选/排序/分页、批量操作、URL 同步筛选状态、导入导出 JSON
- **智能录入**：粘贴题干 AI 解析；截图走三视觉通道（DeepSeek-Vision → GLM-4.6V-Flash → Agnes×2），
  全败退回本地 OCR；支持解题要求补充与参考图
- **今日复习**：间隔重复 1/3/7/15/30 天，选择/多选（全对判分，顺序无关）/填空（别名+数值容差）/
  翻译（对照参考译文自评）/解答（AI 按步骤给分 0-100）；全键盘流（1-4 选答、Enter 下一题、Q/W 标记）
- **自主练习**：记忆曲线 / 按错误时间 / 随机 / 真题专项，多条件筛选
- **生词本**（英语）：闪卡快刷（认识→1/2/4/7/15/30/60 天阶梯，模糊→明天，不认识→留在队列）、
  批量导入词表、掌握度分布
- **知识点库**：标签同义归一、AI 自动总结、贴图分析、服务端分页
- **公式背诵**：分类/搜索/**过卡循环背诵模式**（没记住排队尾直到全会）
- **科目指南**：各科复习重点与方法建议（政治/英语已预置默认档案，可编辑）
- **学习统计**：8 指标卡（数字滚动）、复习热力图（119 天）、7 天趋势、掌握度/题型/来源分布、
  薄弱知识点直通练习、科目与二级科目统计
- **科目感知交互**：政治多选错因快选（干扰项混淆/多选漏选…）、英语错因快选（词汇不识/长难句误读…）
- **前端体验**：墨纸印设计系统、启动动画、按钮涟漪、复习礼花、命令面板（Ctrl+K 全局搜索错题/知识点/公式）、
  图片灯箱、深色模式（View Transitions 圆形扩散换肤）

## AI 配置（可选）

复制 `backend/.env.example` 为 `backend/.env`：

```bash
AI_API_KEY=your-api-key          # DeepSeek 等文本模型
AI_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-chat
AI_VISION_MODEL=...              # 可选：视觉通道（详见 .env.example）
API_TOKEN=...                    # 可选：设置后 /api 需携带 X-API-Token
AI_RATE_LIMIT=30                 # AI 端点每分钟限流
```

未配置 AI 时录入/批改功能提示配置方式，其余功能不受影响。

## 测试与 CI

- 后端 40 个测试：`cd backend && python -m unittest discover -s tests -v`（临时库，不碰真实数据）
- GitHub Actions：push 触发 backend 测试 + frontend 构建

## Git 约定（继承自原 AGENTS.md）

- 远端 `origin` = github.com/MyHeartBea/selfstudy.git，分支 `main`，Git Credential Manager 已登录
- 每次完成代码/数据/文档修改并验证通过后：`git add -A && git commit -m "简短说明" && git push`
- `.env`、数据库、node_modules、dist、日志一律不入库
- C 盘空间紧张：临时文件一律放 `D:\temp`

## 数据安全

- 全部数据在 `data/kaoyan_mistakes.db`，升级/重启不删数据；迁移只加列加表（版本门控 v5）
- 每次启动前自动备份数据库到 `data/backups/`，保留最近 20 份
- 演示数据只在数据库首次创建时写入

## API 文档

启动后访问 `http://127.0.0.1:8000/docs`（Swagger）；接口约定见 [docs/api.md](docs/api.md)。

## DSH / agent 集成

- 视觉识别脚本：`python D:\km-v2\scripts\vision_request.py --image <路径> --json`
  （DSH `vision` 技能已指向此路径；密钥读 `D:\km-v2\backend\.env`，脚本永不打印密钥）
