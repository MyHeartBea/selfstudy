# v3 前端 · 夜航星图 · 阶段交接（NEW_SESSION 补充）

> 这份文件是 v3 重构的**唯一权威交接**。每次阶段结束必须更新它，新会话只读这一份即可接手。
> 主交接文档仍是 `docs/NEW_SESSION.md`（v2 与整体规范）。

## 当前进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| **0** | 脚手架 / 设计令牌 / 基础层 / 启动页 / 星点场 / 光标 / 并行切换基建 | **已完成** |
| **1** | 材质层 / 六条动效原语 / 章节外壳（滚动隐藏·磁吸）/ 规格页 | **已完成** |
| **2** | 组件库：UiButton / UiField / UiTag / InkCard / InkDot / StarRow | **已完成** |
| **2b** | 组件库续：UiTextarea / UiSelect / UiCheck / toast / UiModal / UiEmpty(含 skeleton) | **已完成** |
| 3 | 核心场景（复习 / 录入 / 错题 / 知识点） | **进行中：复习页已完成** |
| 3b | 核心场景续：录入 / 错题 / 知识点 | 未开始 |
| 4 | 剩余页面（统计 / 真题 / 模考 / 生词 / 公式 / 科目 / 练习 / 设置） | 未开始 |
| 5 | 移动端重排 + 可访问性 + 性能预算 | 未开始 |
| 6 | 切换（FRONTEND_DIST）+ 契约对照 + v2 归档 | 未开始 |

### 阶段 1 追加决策：GSAP 推迟到阶段 3

原计划阶段 1 引入 GSAP + ScrollTrigger。实际执行时**推迟**，理由：
1. 阶段 1 的动效（沉降 / 红移 / 描绘 / 扫描 / 聚焦 / 漂移）用 CSS + rAF 已完整覆盖，
   引入 GSAP 只会增加 chunk 与构建复杂度；
2. 真正的收益点出现在阶段 3（复习流程与录入过程需要**时间线编排与可中断的序列**），
   那时再按需引入，并作为独立 `motion` chunk 懒加载（`vite.config.js` 里已预留分包规则）。


## 一、v2 保护机制（**改动前必读**）

v3 **不会**影响 v2 使用，这不是承诺而是机制：

1. **同一后端，两套 dist**。后端 `app/main.py` 的 SPA 回退 `GET /{full_path:path}` 服务
   `settings.FRONTEND_DIST` 目录；该值支持 `backend/.env` 的 `FRONTEND_DIST` 覆盖
   （commit `1838a49`）。默认仍是 `frontend/dist`（v2）。
2. **切换/回滚**只能通过脚本，不要手改路径：
   ```bash
   powershell -ExecutionPolicy Bypass -File scripts/serve_frontend.ps1 -Status
   powershell -ExecutionPolicy Bypass -File scripts/serve_frontend.ps1 -Target v3
   powershell -ExecutionPolicy Bypass -File scripts/serve_frontend.ps1 -Target v2   # 回滚
   ```
   脚本会：先校验目标 `dist/index.html` 存在（否则拒绝，不会把站点切空）→ 备份 `.env` →
   只改 `FRONTEND_DIST` 一行 → 重启后端 → 探活；探活失败自动回滚。
3. **v2 稳定点**：`git tag v2-stable-2026-09-16`（已推送）。
4. **冷备**：`D:\temp\km-v2-backup\{frontend,dist}`（约 60 MB，非仓库）。
5. **v2 目录在 v3 验收通过前不删**。

## 二、数据一致性（可验证，不靠推断）

- v3 **复用 v2 的后端与同一张 SQLite**（`data/kaoyan_mistakes.db`），**不做任何 schema 迁移**。
- 契约形状基线：`docs/contract-baseline.json`，由
  ```bash
  python scripts/contract_diff.py --dump docs/contract-baseline.json   # 采样
  python scripts/contract_diff.py --check docs/contract-baseline.json  # 切换前必跑
  ```
  覆盖 28 个**只读**端点（不写库、无副作用），把响应递归折叠为"键名+类型"形状后做结构化 diff。
  **切换前后都必须通过**；任何字段增删改都会列出路径并非 0 退出。

## 三、v3 目录结构（阶段 0 已建立）

```
frontend-v3/
├── index.html              首帧兜底底色（防白闪），Vue 挂载后移除
├── vite.config.js          base 可切（BASE_PATH）· dev 端口 5175 · 代理 /api,/images → 8000
├── eslint.config.js        与 v2 同标准，独立依赖
├── .prettierrc.json        与 v2 同格式约定
└── src/
    ├── main.js             入口（先样式后应用，避免 FOUC）
    ├── design/
    │   ├── tokens.css      OKLCH 令牌 + 十六进制回退（--sky/--ink/--redshift/--vein/--gold/--violet）
    │   └── base.css        重置 · 排版基元 · 材质(.grain/.halftone/.aurora) · 焦点环 · reduced-motion
    ├── app/
    │   ├── App.vue         外壳：星点场 + 雾气 + 材质 + 光标 + 路由出口 + 启动页
    │   ├── router.js       base 跟随 import.meta.env.BASE_URL
    │   └── InkLoader.vue   启动页：研墨开场三段式
    ├── sky/
    │   ├── Starfield.vue   WebGL 星点场（闪烁 + 视差；无 WebGL / reduced-motion 时静默降级）
    │   └── SkyCursor.vue   自定义光标（lerp 跟随；**不隐藏原生光标**）
    └── views/
        └── AtlasHome.vue   阶段 0 占位首页（阶段 3 替换为观测星表）
```

## 四、核心隐喻与设计决策（后续阶段不得违反）

**未掌握的是暗，已掌握的是光。** 一道错题 = 一颗星；亮度 = 复习遍数；颜色 = 科目；
反复错 = 红移（氧化橙 `--redshift`）；复习队列 = 当晚可观测星表；解析中 = 校准台；
统计 = 星图断面。

已定且**不要回退**的决策：

1. **星云用 CSS 不用着色器**。实测四轮着色器方案（`exp(-d)` / 只抖中心 / 域扭曲 /
   解析梯度雾团）都会留下肉眼可见硬边，最后靠隔离实验定位到残留硬边来自大尺度噪声。
   职责分离：CSS 管柔（`.aurora`），WebGL 管锐（星点）。
2. **不隐藏原生光标**。SOLARIS 参考稿用 `body{cursor:none}`，一旦 JS 失效用户就没有指针；
   这是高频键盘工具，所以自定义圆点与原生指针并存。
3. **零外部 CDN**。Lucide 走 `lucide-vue-next` 本地打包（不引 unpkg）。离线必须可用。
4. **无 emoji / 无字符图标**。箭头等一律 Lucide；已写进 pre-commit 钩子
   （`scripts/preflight_check.py` 的 EMOJI_RE）。
5. **圆角 2px、不用默认阴影、不用玻璃拟态**。层次靠亮度差 + 细线。
6. **动效只允许 transform / opacity / filter**；每条动效必须有叙事或交互理由。

## 五、踩过的坑（复现过一次就别再犯）

| 坑 | 症状 | 正解 |
|----|------|------|
| `vertexAttribPointer` 绑定的是"当前 ARRAY_BUFFER" | 星点场全黑（画布一个像素都没画） | 每帧 draw 前重新 `bindBuffer` + `vertexAttribPointer` |
| GPU 合成下 `gl.readPixels` 返回全黑 | 误判"没渲染" | 渲染判据用**截图**：`python scripts/check_render.py <png>` |
| **原语入参没有守卫** | 传进非元素（组件实例代理）抛 `el.addEventListener is not a function`；异常在 `onMounted` 内，**同钩子后续原语全不执行** → 元素永不出现 + 加载页卡住 | `motion.isElement()` 入口守卫；已加 11 条单测钉死非法入参 |
| 把 `matchMedia` 默认值当测试前提 | 单测误判（happy-dom 对任意查询都返回 `matches: true`） | 测试里显式 mock `matchMedia`，不依赖宿主默认值 |
| Windows PowerShell 5.1 按 ANSI 读无 BOM 的 .ps1 | 中文被破坏 → 语法错误 | 脚本用 **ASCII-only** 且加 BOM |
| PowerShell `Set-Content` / 内联 `-c` 破坏引号与 UTF-8 | 文件被写坏、提交信息被截断、测试假失败 | 不用它改源码或写多行提交信息；用 edit/write 工具与 `git commit -F <file>` |
| GLSL 不允许在 `main()` 内定义函数 | 着色器编译失败，静默退到兜底 | 辅助函数写在全局作用域 |
| 组件文件头注释被压成一行 | 可读性差（发生过两次：`InkLoader.vue`、`App.vue`） | 发现即整份重写；写完用 read 回读确认格式 |

## 六、阶段 0 验收证据

- v3 构建通过：`dist` gzip 约 43 KB（vendor 34.6 / app 5.3 / css 2.5）
- 真浏览器（无头 Chrome + SwiftShader）验证外壳：
  - 启动页时序正确：`rest`(≈0.9s) → `inking`(≈1.4s) → `opening`(≈3.5s) → 卸载，`body.ready` 生效
  - 星点场真绘制：截图右半区 3484 个亮像素、强边占比 2.73%（雾气柔和，无硬边）
  - 自定义光标 / 雾气 / 颗粒均在位；无横向溢出；页面零异常
- v2 未受影响：`/api/health` ok、`/stats` 首页 200、148 后端测试通过、v2 前端 lint 通过
- 契约基线一致：28 端点 `--check` 无差异
- **CI run #74 全绿**（sha `62bed63`）：backend-tests / frontend-test-build /
  **frontend-v3-build** / frontend-e2e 四个 job 全部 success
- v3 单测 5 个通过（`tests/inkLoader.test.js`）

### 排查记录：CI 曾"看起来不触发"

一度以为推送没触发 CI（`per_page=1` 的 runs 列表接口返回陈旧数据，连续两次都看到旧的 #73）。
正解是查 **workflow 维度**的端点并带分支过滤：

```bash
curl -s -H "User-Agent: Mozilla/5.0" \
  "https://api.github.com/repos/<owner>/<repo>/actions/workflows/<id>/runs?per_page=1&branch=main"
```

用它立刻看到 pending 的 #74。另新增 `scripts/check_workflow.py` 排除"workflow 语法非法被
GitHub 静默拒绝"这一可能（4 个 job 结构合法）。**下次 CI 像没跑，先查 workflow 维度端点。**

### 补充：GitHub Actions 存在数十分钟级的事件延迟（第二次观察到）

- 提交 `bd7a04d` / `6931c84` 推送后长时间没有任何 run；后来 **run #74 是挂在更晚的 `62bed63` 上**出现的，
  即那两次 push 的事件**没有生成 run**。
- 阶段 1 的 `4192e9a` 推送后同样在 12 分钟内没有任何 run（多次查询 workflow 维度端点均只见旧的 #74）。

结论：本项目当前的 Actions 事件投递偶发丢失/长延迟。**依赖 CI 才能宣称完成的事项，
若 12 分钟内没看到 run，不要判定为"代码有问题"**，也不要反复重试推送刷屏；
应记录为"CI 待确认"，并在下一次推送时一并确认（或到 Actions 页面手动 `Re-run` / 手动触发 workflow_dispatch）。


## 七、下一步（阶段 3：核心场景）

前置状态（阶段 2 完成时）：v3 共 26 文件 / 3903 行；组件库 13 个；v3 单测 64 个；
规格页 `/design` 20 个 reveal 全生效、零异常；CI #75（88c67da）四 job 全绿；
`4e56165`（阶段 2b）的 run 尚未生成（与本文件记录的 Actions 延迟现象一致）。

阶段 3 要做四页核心场景（这是工作量最大的一阶段）：
1. **今日复习 · 砚台**：墨量（待复习积压）+ 落笔弹层 + 键盘流（空格看答案 / 1-4 选项 / Enter 确认）
2. **智能录入 · 蘸墨台**：多图暂存（一次选多张）→ 一次分析；解析过程用**真实阶段进度**，不编造百分比
3. **错题列表与详情**：整块可点（InkCard）+ 筛选 + 详情侧栏；掌握度/星等复用组件
4. **知识点库**：卡片墙 + 关联错题；链接接口 `/api/knowledge/linked-mistakes`

开工前必做（顺序不可颠倒）：
1. `python scripts/contract_diff.py --check docs/contract-baseline.json` —— 确认契约未变
2. 先写 `src/core/api/` 契约层（每个端点一个函数，URL 只在这里出现）
3. 每页完成即接入浏览器验证（**改组件/视图后先重启 dev server**，见踩坑表）
4. GSAP 到本阶段再引入（独立 motion chunk，vite.config.js 已预留分包规则）；
   用时序编排做「落笔」与「研墨」两处，其余仍用 CSS 原语

## 八、成本与授权状态（开工前请确认）

- 已用：约 ¥20（阶段 0–2b）。
- 剩余阶段 3–6 预估：**¥20–30**。余额长期停在约 ¥1.94，**建议充值后再开阶段 3**，
  避免跑到一半中断（用户偏好里也明确写了"预算不足先充值再开始下一阶段"）。
- **视觉方向尚未由用户确认**：v3 按「夜航星图」（深空 #05060a + 氧化橙 #ff5a3c）推进了三个阶段。
  阶段 3 起是真实业务页面，改色成本显著上升，**建议在阶段 3 前确认**。
  dev server：`http://127.0.0.1:5175`，规格页 `/design`。

