# 研错本 · 工作日志（WORKLOG）

> **文档分工**：`AGENTS.md` 只放**约束与规定**（规矩、红线、架构约定）；本文件记录**"什么时候干了什么"** —— 批次明细、改动清单、踩坑叙事、当时的测试数据。
> 新批次完成并验证后，在文件**末尾追加一节**（格式：`## 日期 · 批次名（提交哈希）`）。
> ⚠️ 踩坑里如果沉淀出"以后必须遵守的规矩"，要同时登记进 `AGENTS.md` 对应节 —— 日志负责叙事，规矩归 AGENTS.md。

---

## 2026-09-06 · 墨韵 2.0 重构 + 功能补全（基线）
- **前端墨韵 2.0 重构 + 功能补全批次全部完成**。UI：7 Phase（`2c1e52b`…`1458fdc`）+ 三轮反馈迭代；功能批：详情卷宗v3+缩略图+预报（`d19bf5a`）、SM-2 调度（`ccedc90`）、错因周报+Anki 导出（`e66a24e`）、真题模考（`e5c3481`）、层叠修复+模考存档+高亮+打印+速查+Vitest（本批）。
- 后端契约：迁移到 v8（v6=ease_factor/last_interval，v7=mock_records 表，v8=exam_papers/exam_questions 真题库）；`/api` 新增 `/mocks`、`/ai/weekly-report`（按天缓存 app_meta）、`/export/anki`、`/reviews/forecast`、`/images/thumb/{name}`；`/reviews/practice` 支持 `mistake_id` 与 `mode=mock`。
- **真题库已上线**：真机验证英语二 2013 全链路（导入拆题 33 题 50 秒 / 答案配对 20/27 / 整卷模考 / 错题自动入本）。**扫描版/乱码文本层 PDF 已支持且公式更准**：数学/408 优先 DeepSeek 视觉（输出 LaTeX），实测 2025 数二 22 题/配答案 10/10（公式/偏导/积分限/矩阵准确）、2009 计算机408 问卷乱码文本层 → 视觉逐页提取 47 题/配答案 40/40，且图示题（二叉排序树等）自动存整页原图 `/images/exam_papers/<pid>/p<n>.webp` 供模考查看；仅当视觉与 OCR 都提不出文字时才报 error。每份卷导入约 1-3 分钟 + 数次 AI 调用（含视觉，成本低）。
- 视觉基准原型 `D:\temp\km-redesign\ink2-prototype.html`。

## 2026-09-10 · 后端优化批次
①复习队列＝新题优先+逾期轮转+每日配额（不做毕业机制）；②真题库扫描＝合卷识别+按科目年份去重+年份/科目修正（可导入 1→59 份）；③知识点↔错题链接（`/api/knowledge/linked-mistakes` + 详情弹窗展示，支持 related_tags 兜底）；④工程项＝`HOST`/`PORT` 可配、请求耗时与错误监控（`app/metrics.py` + `/api/health` 摘要）、`/api/snapshots` 快照（导入/批量删除自动先快照）。测试：后端 95、前端 49。

## 2026-09-14 · 质量与架构批次
①**卡片整块可点**：知识笺/公式卡改为卡体 `@click` + 控件 `@click.stop`（原 `.k-hit` 覆盖层被 z-index:2 的子元素盖住，只有缝隙能点）；
②**智能录入多图暂存**：粘贴先暂存成图组再一次分析（原 `for...of` 里 `await` 让所有回调都用了最后一个绑定）；
③**录入表单保存后整表重置**（新增模式 `row` 恒为 null，原先 watch 不触发）；
④**deepseek-flash 回归修复**：视觉 `max_tokens` 4000 → 16000 + `finish_reason=length` 翻倍重试（原来推理 token 吃光预算 → 原文只剩一两段）；OCR 提示词加 `【原文】/【题目】` 分段标记 + `_split_ocr_sections`（原来题目段被混进原文导致「题目完全不一致」）；`qa["passage"]` 取纯原文（原先错取 `source_text`）；数学/英语/标题提示词加「原样照抄」约束与页眉页脚/水印排除；
⑤**答案文件解析**：`_normalize_answer_text` 支持 `(1)C. (2)B.` 与 `1【答案】（A）` 两种版式；`classify_file` 新增 **mixed（问答合卷）** 判定，无答案文件时同文件文本回填；docx 后缀分派（原先被当扫描 PDF）；
⑥**安全**：`/api/papers` 的 `source_path`/`answer_path` 增加 `_resolve_inside()` —— 拒绝绝对路径、`..` 段、越出根目录的路径（生产实测 7 种穿越全部 400）；`routers/system.py` 补 `error` 导入（F821 真 bug）；
⑦**架构拆分**：`ai_service.py` 1402 → 约 950 行，英语整篇流水线抽到 `app/services/ai_english.py`（约 500 行，真并发 `executor.submit` + `.result()`，通过 `_svc()` 惰性引用模块以便 mock 生效），底部保留兼容 re-export；
⑧**工具链**：后端 Ruff、前端 ESLint 扁平配置 + Prettier、`pre-commit`（含密钥扫描与大文件检查，`scripts/`）、CI 增加 ruff/eslint/prettier/前端单测/覆盖率门槛 55%；顺带修出两个真 bug（`FormulaView.vue` 的 `reciteRevealed` 未声明、`system.py` 的 F821）；
⑨**前端 E2E（Playwright）**：`frontend/e2e/` 31 个用例（desktop + Pixel 7 两档 project）—— 卡片整块可点（含键盘 Enter/Space 等价入口、`@click.stop` 不误开详情，桌面与窄屏都跑）、智能录入多图暂存（3 张只暂存 / 只发一次请求 / 请求体 3 张图齐 / **解析结果真的渲染**）、10 条主路由渲染烟测。CI 新增独立 `frontend-e2e` job；`CaptureView.vue` 主图 input 加 `data-testid`；
⑩**E2E 自查**：打桩夹具字段名/形状对齐真实契约（`/api/ai/english` 的 `passage_text` 等、`/api/knowledge/tags` 的 `[{tag,mistake_count}]`）；否定断言改正向；断言同步点从"请求已发"改为"结果已渲染"（并用变异测试证明断言真的会失败）；新增 `expectAllApiStubbed`（漏打桩即失败）与 `guardPageErrors`（三个 spec 都装页面错误守卫）；`vite.config.js` 纳入 lint 目标；E2E 默认端口改 5274 避免误复用旧 dev server；mobile project 补跑卡片点击。
测试：**后端 148、前端 49 + E2E 31**，覆盖率约 62%。

## 2026-09-18 · 前端动效与首屏批次（`77af90d` + `d025aa9`）
以"网页进入动画的工程水平"为基准做的全前端对齐，规矩都写进 AGENTS.md 6.5 节。
①**动效词汇表**落地（`--dur-1..5` / `--stagger-1..3` / 语义缓动），弹层基件（UiModal/UiDropdown/UiSelect/CommandPalette/ToastHost/QuestionImages）与四张卡片墙、AreaChart 全部改为引用令牌，`base.css` 里 `.tilt`/`.reveal-*` 的手写 cubic-bezier 也已收掉；
②**换页动画只留 JS 一条路径**：删掉 `base.css` 里那条压住内联样式的 `.page { animation: page-in }`（五次"换页没动画/方向反"commit 的真因）；
③**开场三条链合流**（splash / BootCalibration / AppLayout 靠 `km:boot-done` + `window.__kmFontsReady` 串成一条），`app-ready` 必须等字体样式表注入完再读 `document.fonts.ready`；
④**首屏减负**：字体 CSS 拆成异步 chunk（阻塞 CSS 528.6KB 降到 54.7KB、`renderBlockingStatus` 变 non-blocking）、`manualChunks` 切 katex/motion/vendor（入口 219.8KB 降到 62.5KB）、woff2 禁内联；
⑤**生命周期泄漏**：ShaderBackdrop 解绑的从来不是注册的那个函数、AppLayout 匿名快捷键监听、`router.afterEach` 磁吸只增不减、AmbientLayer 每帧空转、confetti/ResizeObserver 之类的成对问题；
⑥**`prefers-reduced-motion` 补 `animation-iteration-count: 1`**（只压时长会让无限循环动画以 0.01ms 空转，比有动画更费 GPU）；
⑦**`.gitattributes`** 治掉 `core.autocrlf=true` 造成的 10 个伪差异（需 `git add --renormalize .` 才生效）；
⑧**回归踩坑**：把 `BootCalibration.runAnim` 从 setInterval 改成纯 rAF 之后，后台标签页里合成器不排帧，撕裂阶段永不结束，遮罩以 `pointer-events:auto` 压住整页（`/design` 实测）—— 装饰性动效才用纯 rAF，驱动流程的时间线一律「wall-clock + setInterval 兜底」；复现开关就是 `document.hidden === true`；
⑨**叠层焦点与滚动锁**：`UiModal` 负责焦点圈（Tab 不跑出面板）+ 关闭后归还焦点 + `aria-labelledby`，监听改为 `{immediate:true}`；滚动锁收敛到 `ui/scrollLock.js` 的**全站计数**；
⑩**加载失败态与空态分家**：新增 `ui/UiLoadError.vue`，六个整屏页（错题/知识点/公式/生词/复习/卷库）不再把取数失败伪装成"暂无数据"。顺带修出：`MistakeListView` 漏解构 `loadError` 导致错误 UI 永不渲染、`FormulaView` 用 `<Icon>` 却没 import 导致背诵完成页图标静默消失、`ReviewView` 快捷键面板里 9 个 `↵` 与 `MistakeListView` 难度 chip 的 `★` 字符图标（改成 `icons.js` 新增的 `star` 实心五角星 + `aria-label`/`aria-pressed`）；
⑪**这类 bug 现在有测试兜了**：`tests/templateBindings.test.js` 用 Vue 编译器扫全量 SFC（未解析的模板标识符 + 未 import 的组件），带幽灵变量自检；顺手清掉 `EnglishAnalysisPanel` 里最后两个字符图标（选项正确标记的 `✓` 换成 `<Icon name="check">`、写入 `approach` 的 `❌ ` 前缀换成「【答错】」）。
测试：**后端 148、前端 61 + E2E 31**（`--workers=2` 下全绿；单 worker 会因并发争抢假红）。

## 2026-09-19 · 前端设计质量批次（`d951ab0`，impeccable + design-taste-frontend 双 skill 走查后）
skill 装于 `C:\Users\Administrator\.agents\skills\`，只动了 `frontend/`。
①**三级文字对比度达标 WCAG AA**：`--ink-3` 浅 `#9a917d→#726852`、深 `#7c7361→#93897a`——旧值在 surface 上只有约 3:1，全站占位符/微注/「共 N 条」不达 4.5:1；换后 bg/surface/surface-2 三种底全部 ≥4.5:1，且与 `--ink-2` 仍保一档明度差；
②**页首墨迹揭示编排**（base.css）：`.view-hero` 四段级联（眉标淡入 → 大标题 clip-path 自左向右展开 → 描述上浮 → 操作行淡入），全部引用 `--dur/--stagger/--ease` 令牌，`prefers-reduced-motion: no-preference` 包裹，初始态只写在 keyframes 里配 `fill: both`（禁动画环境直接落末帧，不会白屏标题）；
③**错题列表头部 6 按钮 → 3 控件**：自主练习升 primary（唯一主 CTA），导出/打印/Anki/导入收进「导出与工具」UiDropdown；隐藏 file input 改 `ref` 触发（复用 `useImportExport` 现成的 `fileInput`）；
④**两个概念性动效锚点**：统计页大数字 `ink-bloom` 墨晕显影（blur+scale 一次性，与 useCountUp 叠加）；复习完成页编舞 = 容器薄纱 → 标题/小结/积压/操作按 `--stagger-2` 逐段 `gather-in` → 印章第 5 拍最后落下（呼应「朱砂印为证」）；
⑤**动效硬编码收编**：`cubic-bezier(0.22,0.8,0.36,1)` 就是 `--ease` 的手写原文，4 处（UiButton×2 / MistakeListView×2 / FormulaView）收编为 `var(--ease-enter)`；墨韵编排家族（`0.22,1.12` 系列、0.5-1s 大位移）是刻意手感，保留不收；
⑥杂项：`.page` 对齐 `var(--content-max)`（1200→1150）、`.field-input` 加 `caret-color: var(--accent)`、打印块补全全部新动效的末帧豁免；
⑦**/design 画廊**新增「动效 · 页首墨迹揭示」节（`:key` 重播样例 + 全站动效锚点清单）。
**有意保留**（skill 建议砍但属于品牌件，别再"修"）：英文眉标 `view-kicker`（全站报头装置）、自定义光标 AppCursor（用户点名要的效果）。
⚠️ **E2E 不要和浏览器截图/自动化会话并行跑**：资源争抢会假红 8 个（capture/card-click/render-smoke 全中，症状全是"element not found"；单独重跑 1 分钟全绿）。
测试：后端 148 未动、前端 61 + E2E 31 全绿。

## 2026-09-19 · 墨韵 3.0「数字文房」全面升级批（`9c33838` + `62b84a8` 修墨滴可见性）
核心隐喻：**记忆即墨，复习即描摹**。
①**令牌**：`--fs-display` 改流体 `clamp()`、新增 `--fs-mega`（门面页巨型字档）；新增**墨迹褪色阶** `--ink-fade-1..4` + `--ink-wash`（用 color-mix 挂在 `--ink` 上，随主题自动换色，禁止再引新灰）；
②**浏览器表面补完**（base.css）：`li::marker`、number 步进箭头移除、`summary` 折叠标记主题化；
③**掌握度/遗忘语义化**：错题卡新增 `.ink-due`「今日到期/逾期 N 天 · 墨迹将干」状态章（SM-2 的 next_review_at 到期才渲染，字段缺失静默不渲染；与复习队列"今日到期"同口径 = `due <= 今日 23:59`）；统计页平均掌握度 chip 改为**墨滴**（`.ink-lvl`，opacity=掌握度）；
④**统计首屏非对称重构**：巨型竖排「今日」水印（`.hero-mega`，writing-mode vertical-rl + `--fs-mega`）立于页首左，信息块右移（≤900px 整体退场）——Ink Dynasty 竖排书法的转译；
⑤**复习完成页升格**：新增 `ui/InkRain.vue` **内容文字雨**（本轮队列题干的真实汉字在卷宗框内缓落晕开；rAF 自停 + visibilitychange 停 + reduced-motion 不渲染；队列题干在内存里直接取，零新增请求）；印章落地后**两圈墨环晕开**（scoped `ink-ring` keyframes，延迟对齐 stamp 落地拍点）；礼花升级为**洒金**（confetti.js 金箔条 2.6:1 + 金/朱砂色板）；
⑥**氛围层**（AmbientLayer）：新增**落墨画布** —— 点击纸面墨滴洇开。⚠️ 画布必须 fixed 悬在内容层之上（`z-index: 1400`）：初版挂在 `.ambient`（z-index 0）里，墨滴被玻璃卡/不透明容器压住完全不可见（用户实测"点了没反应"，`62b84a8` 修复）；墨色 spawn 时读一次 `--ink`（深色主题=浅墨）；画布 buffer 尺寸用 `clientWidth`（用 innerWidth 会与 CSS 尺寸错位一个滚动条宽）；湿边（咖啡环效应描边）让浅底上有轮廓；远山/墨字水印改 **CSS scroll-driven** 视差（`animation-timeline: scroll(root)`，Firefox 静态兜底；`.c1/.c2` 的旋转改用独立 `rotate` 属性避免被动画 transform 覆盖）；
⑦**Dock 磁吸**：图标被指针吸引（只写 `--mag-x/y` 变量、每次 pointermove 一帧 rAF 批处理、先读后写、离场归零、reduced-motion/触屏不绑定）；**光标悬锋**：命中可点元素内芯变毛笔尖（teardrop），按下滴墨涟漪；
⑧**纸牌落桌**：v-reveal 入场带随机倾角 —— `.card-grid` 按 nth-child 三拍预设 `--reveal-tilt`（纯 CSS，指令零改动）。
⚠️ **统计页卡片 root 不许画背景/边框/内边距**（用户三轮实测的"框中框/槽中卡"真因，`5071d58` + `01cbe74` 修复）：报刊层的 `.stats-page :is(.b-hero, .b-tile, .span2, .span3) { background/border/padding !important }` 曾让圆角玻璃卡浮在一块更大的方形底上 —— 浅色下 root 底与纸色同形看不出来，**深色下原形毕露**。现在的约定：root 全透明，可见卡片只有 `.gcard-body`（玻璃+渐变描边，height:100% 铺满格位），留白全在 gcard-body 自身 padding；`.bento-top` 的组版容器框也已拆除。**双主题必须都截图**——浅色下同形的问题深色必现。
**刻意不做**（都有理由，别"补"）：BootCalibration 不重画（五轮实测打磨出的撕裂开屏是资产不是负债）；pageFlip 不接入换页（km-flip.css 里记录了 Vue Transition 四连败，JS 单路径是结论）；OKLCH 全量换算（零视觉收益、有回归风险）；字重 300（体积不划算）；卷宗纸感/模考试卷纸（下一批）。
测试：前端 61 + E2E 31 全绿；双主题真机回看通过（竖排大字/墨滴/将干章逐项 DOM+截图验证）。

## 2026-09-19 · 墨韵 3.0 续批（`4d9424b`，用户反馈"光标太丑要毛笔"）
①**AppCursor 整体重做为毛笔**：Lucide `brush` path 做笔身（30px，斜握 6°），**笔锋尖端 = 指针热区**（0×0 锚点 + 图标左下角对齐）；悬停可点元素 = 提笔转朱砂 + 锋下浮出 34px 细墨环；按下 = 压笔（前倾下沉）+ 锋尖滴墨涟漪；tip 处 teardrop 墨点保精度。旧"圆点/圆环"版本已删；
②统计页 `.bento` 改**非对称杂志网格**：三列不等宽（1.4fr/1fr/1.2fr）+ 薄弱卡与热力图换位（行序交错）；
③复习完成页新增 **`ui/YearRing.vue` 数据年轮**：每道题一段弧（朱砂=答对、淡墨=答错，错题弧均匀穿插），印章落地 1s 后按 1.4s 顺时针生长、rAF 自停，reduced-motion 直接画完整；
④错题详情弹窗末尾**卷宗骑缝章**（章盖卷末右下，in-flow 定位免纠缠）；
⑤InkRain 触屏（pointer: coarse）密度减半；完成页 **Enter 直达返回错题列表**（onKeydown 的 done 分支）；/design 新增 **FPS 自检卡**（验收线 ≥55，reduced-motion 停测）。

## 2026-09-19 · 墨韵 3.2 五维度批次（`967a603`，动画/背景/排版/UI/交互复查）
①**换页墨扫**（AppLayout + base.css `.page-wipe`）：换页时一条朱砂/墨柔光带随方向扫过纸面（0.62s 一次性、纯 transform、`--wipe-from` 由 pageDir 给方向、z-index 930 压内容不压弹层、reduced-motion 下 display:none 且 playPageEnter 不触发）；
②**笔过留痕（飞白）**：AmbientLayer 的 onMove 加速度门限（>2.2px/ms）+ 节流（140ms），快速扫过时复用落墨画布 spawn 更淡更急散的墨丝（`trail` 参数：r 4-10 / alpha 0.10-0.15 / decay 0.9），零新增监听与 rAF；
③**氛围 blob 有机化 + 主题混色**：drift 关键帧加中途位移（像墨在水里游）；浅色 `mix-blend-mode: multiply`（墨沁进纸）、深色 `screen`（墨在暗处发亮）；
④**排版**：`.view-hero h2` 流体字号 `clamp(30px, 2.4vw+16px, 46px)`（10 个页面一齐跟上统计页）；统计页巨型「今日」hover 时 opacity 0.075→0.11（纸下有字，扫过浮出）；
⑤**UI**：`[data-theme='dark'] .gcard-body::before` 上缘 8% 白渐变受光边（深场玻璃立起来；浅色不加，会显脏）。

## 2026-09-19 · 墨韵 3.3 背景与进入动画批（`d0fdff1`，用户点名"学习 motionsites 案例，重点优化背景和进入动画"）
①**环境字瀑**（StatsView `.mega-fall`）：Ink Dynasty 文字瀑布的静音转译 —— 统计页页首 7 枚宋体字（研墨题错记忆纸）以 0.04-0.05 透明度自上缘缓落、下缘洇出（60-120s CSS 合成器循环，零 rAF；reduced-motion 与 ≤900px 整层 display:none）。⚠️ 落程用 `translateY(-60px→330px)` **像素**而不是百分比（百分比是元素自身高，不是容器高）；裁切靠 `.mega-fall{overflow:hidden}` 自身，不要给 `.view-hero` 加 overflow（会裁掉 ::after 双细线）；
②**巨字笔锋显影**：`.hero-mega` 入场 = 自上而下 clip 揭示 + blur 8px 聚焦（vertical-rl 的书写方向），`fill: backwards` 播完释放——用 `both` 会把末帧钉死、hover 浮出过渡失效；
③⚠️ **层序规则别用 `:not()` 反选整层子元素**：`.view-hero > :not(.mega-fall)` 会把同为装饰的 `.hero-mega`（absolute）也覆盖成 relative，巨字掉进 flex 流、页首被撑到 556px（实测）。层序只精确给内容块（`.view-hero-copy` / `.header-actions`）；
④**三层远山 + 雾带**（AmbientLayer）：新增 `.mountains-near` 近景山脊（更暗更近、行程更大）+ 两道纸色雾带 `.mist`（空气透视），全部 CSS scroll-driven（`animation-timeline: scroll(root)`）各走各速；
⑤**主题混色补全**：`.aurora` / `.ink-blob` 也吃 multiply（浅）/ screen（深），与 `.amb-blob` 一致；
⑥顺手修掉：AmbientLayer 模板里遗留的**第二个落墨画布**（初版残留在 .ambient 内，与外层 fixed 画布叠了同一个 z-index 白占合成层），已删，全站只剩一个。

---

## 其他
- 2026-09-19（`6807104`）：AGENTS.md 新增「缓存/下载一律放 D 盘」规矩（`D:\caches\` + 环境变量清单：pip / npm / IMPECCABLE_HOME / PLAYWRIGHT_BROWSERS_PATH 已配好）；impeccable + design-taste-frontend 两个 skill 装于 `C:\Users\Administrator\.agents\skills\`。
- 2026-09-19（本批）：工作日志从 AGENTS.md 迁出至 `docs/WORKLOG.md`，AGENTS.md 从此只放约束与规定。

## 2026-09-19 · 墨韵 3.4 内页全面升级批（三期一次完成，用户点名"错题列表/复习/公式/知识点/英语等内页全面升级"）
### 第 1 期 · 核心交互
- **`ui/FlipCard.vue` 共享 3D 翻牌**（D2）：生词闪卡与公式背诵统一语言；组件只管视觉与点击翻面（interactive 可关），键盘归使用方，避免双重切换。
- **生词闪卡三向滑动判分**（F1）：右=认识（朱砂提示章）/ 左=不认识（淡墨）/ 下=模糊（洒金）；指针事件覆盖鼠标+触屏（`touch-action: pan-y` 保竖向滚动），阈值 80px 松手飞出后判分，未过阈值回弹；`justDragged` 区分拖拽与点击翻面；键盘 ←/→/↓ 等价（加入原 onKeydown 流）。
- **公式背诵翻牌舞台**（D1）：背诵弹窗从"按钮 reveal"升格为 FlipCard 翻牌（正面分类+公式名，背面解析 max-height 滚动）；**记住=右飞归档 / 没记住=左飞回队尾**（flyRecite 240ms 飞出后真正过卡）；键盘 空格/→/←。分类印章悬停 thud（D3）。
- **复习题卡抽换**（C1）：stage-card 内容包 `<Transition name="qswap" mode="out-in">` + `:key="current.id ?? index"`，换题旧内容墨淡出、新内容自下聚现（只动 transform/opacity/filter）。
- **判分印章化**（C2，base.css 全局 option-row）：答对 = 右下"对"字朱批小章落定（judge-stamp，替换旧 ring-pulse，行尾留 52px 空位）；答错 = 淡墨晕开（wrong-ink，替换 shake 之外的空缺）+ 保留 opt-shake。
- 巨字换字补 blur 聚焦（C3，numeral-in from 态加 filter:blur(7px)）。
### 第 2 期 · 认知减负
- **激活筛选 chips**（B1，MistakeListView）：computed `activeFilterChips` 把 9 类筛选态（搜索/题型/科目/二级/来源/年份/难度×5/标签/思路）外显为可单独移除的墨点 chips + 清空全部；工具栏下方 `.filter-chips`。
- **批量条**（B2）：已选数字 `:key` + pop-num 跳动；删除按钮 `bulk-danger` 朱砂缓脉（2.2s 循环，reduced-motion 停）。
- **知识笺挂 km-live**（E1）：幽灵序号=笺序、四角取景框、扫描线、顶边标尺，内容包 `.km-live__inner`（kmLive.js 事件委托按 .km-live 类挂载，加类即生效）。
- **卷库导入流水线 stepper**（H1）：状态药丸 → 三段工序条（提取→拆题→配对），done=绿实心、active=金点缓脉（ps-pulse）、排队=灰+「排队中」注记、error=红；轮询重闪已由 `:key="p.id"` 天然规避（H2 ✓）。
- **会话完成墨环**（F3）：生词快刷完成页挂 YearRing（total=本轮判分总数，wrong=不认识）。
- **印章空态**（A1）：UiEmpty 新增 `seal` prop（64px 淡墨方印，rotate -4°），错/式/知/词/卷/习 六页接入（仅在真正空态渲染）。
### 第 3 期 · 打磨
- **弹窗内容级联**（A3）：UiModal `.modal-body > *` 逐档 `--stagger-1` 淡入上浮（全局，打印已在 base.css 强制末帧）。
- **科目指南编辑式排版**（I2）：`.tips` 行距 2 + `::first-letter` 首字下沉（朱砂宋体）。
- **长表单分区**（I3，MistakeForm）：六个编辑式分区头（壹题型与科目/贰题面/叁作答区/肆判分与思路/伍解析与标签/陆来源），`.form-sec` 汉字序号+发丝线。
- **关联错题行**（E3）：RelatedList related-card 挂 km-item 整行刷底悬停。
- 骨架核对（A2）：Mistake/Knowledge/Subject/Practice 加载骨架均为网格卡片形 ✓；MistakeForm 共 6 处 label 上置 ✓（原本就符合规范）。
### 有意不做（记录在案）
- B3 首图视差（图片对象定位动画易抖，收益低）；C5 进度线滴墨（进度线已有流光，再加是堆）；E2 标签 pills（现状是文本输入框，非标签堆叠，不适用）；F4 分布条墨阶渐变（现有墨点语义已够）；PracticeView 预览（"今日出征"已存在）。
测试：前端 Vitest 61 + E2E 31 全绿、build/lint 干净；真机抽验 chips/stepper/空态印章 DOM 命中。

## 2026-09-19 · 复习分块批（`e3b1a13`，用户需求：今日复习按科目分块，默认只刷数学）
首个前后端协同功能批。
**后端**：
- `review_service.get_today_queue` 新增 `category` 参数（math/cs408/english/politics）：队列 SQL 加 `subject_id IN (...)` 过滤，dueTotal/remaining 按块统计；不传 = 全部（向后兼容，旧测试全过）。
- 归块表 `REVIEW_BLOCKS`：按**科目名包含关键词**匹配（数学 / 408|计算机 / 英语 / 政治），兼容 数学二/英语二/计算机408 命名；不入块的杂项科目不出现在分块里（只能走自主练习）—— 刻意行为。
- 新接口 `GET /api/reviews/blocks`：四块汇总 `{key,name,due,total}`，due 口径与今日队列一致（新题永远算到期）。
- ⚠️ 语义教训：`remaining` = **该块积压**（dueTotal-本批），我初版错误地让它和今日剩余配额取小，被既有测试 `test_daily_limit_caps_and_subtracts_reviewed_today` 当场抓住 —— done 页的"积压 N 题"文案靠它。配额与积压是两个概念。
**后端测试**：新增 `tests/test_review_blocks.py` 5 用例（分块过滤/关键词归块/汇总计数/空块/配额全局共享），后端 **153** 全绿。注意：`review_count=0` 的题无论 next_review_at 排到多远都算"到期"（新题必须被见到）—— 写测试数据时容易踩。
**前端（ReviewView）**：
- 分块 Tabs（编辑式药丸 + 到期数徽标），**默认选中数学**；`?block=` 同步 URL（刷新/回跳保持所在块）；仅今日复习模式显示（练习/模考/整卷不显示）。
- 换块 = 清空上一题作答现场（index/selected/revealed/judgeResult 等）再取新队列（watch route.query.block）；换块后完成的标题显示"数学 · 复习完成"。
- 完成页**跨块跳转**：数学刷完时显示"408 · 16 题到期 / 英语 · 10 题到期"墨点按钮，点击直接切块续刷（blocks 在 done 时刷新）。
- E2E `fixtures.js` 补 `/api/reviews/blocks` 打桩（漏打桩会被 expectAllApiStubbed 判假红）。
**真机验证**（重启 8000 后端后）：Tabs 显示 数学 80 / 408 16 / 英语 10 / 政治 1（真实到期数）；默认数学队列只出数学题；切 408 后队列 16 题、DOM 卡片显示"408计算机基础综合/计算机网络"、API 确认 subject_id 全部归属 408 块。
测试：后端 153、前端 61 + E2E 31 全绿。

## 2026-09-19 · 五项快修批（`39ec3f7`，用户四点反馈 + 倒计时立项）
①**考研倒计时**：`config.py` 新增 `EXAM_DATE`（默认 2026-12-19，`.env` 可覆盖），`/api/stats` 返回 `exam_countdown{days,date,passed}`（非法日期 days=None、已过 passed=true，前端静默不显示）；统计页 hero 主按钮左侧虚线章条"距考研 N 天"（宋体大数字）。
②**生词卡整卡可点**：卡片挂 role=button + 键盘 Enter/Space，点开**详情弹窗**（大字词头/音标/掌握度墨点/释义/例句/笔记/来源与复错数），页脚 关闭/编辑/删除；编辑与删除先关详情再动作。卡片原"编辑/删除"按钮补 `@click.stop`（AGENTS 6.5 整卡可点规范）。
③**生词本每页 15**（pageSize 20→15，sizes [15,30,60]）。
④**知识点每页 9**（pageSize 10→9，三列网格恰好 3×3，sizes [9,18,45,90]）。
⑤**练习页高级筛选下拉被裁**（用户截图实测）：根因是 `details.adv-filter` 放在 `.deploy` 玻璃卡内，`gcard-body` 的 `overflow:hidden`（流光裁切用）把 UiSelect 下拉菜单整个裁掉。修法 = 提前闭合 GlassCard，把筛选挪出为独立 `.card.card-pad` 纸片（普通 .card 无 overflow 裁切）。真机确认 adv-filter 已不在 gcard-body 内。
测试：后端 153 + ruff 全绿、前端 61 + E2E 31 全绿；真机四页 DOM 验收（倒计时 91 天/点卡出详情/portrait 词、page_size=9、adv-filter 出卡）。

## 2026-09-19 · 英语作文 AI 批改批（`9d389b5`，新会话接管后的第一个功能批）
交接后先确认两件事：`EXAM_DATE=2026-12-19`（用户给的预计初试日）写进 `backend/.env` 并重启后端（`/api/stats` 实测 `days:91`）；功能选型由用户点定「英语作文批改」。

**后端**（`app/services/ai_essay.py` + `app/routers/essay.py`，迁移 **v10** 新增 `essay_records`）：
- 四型评分档 `ESSAY_KINDS`（e1/e2 × 小/大作文，10/20/10/15 分）+ 五档与零分档区间写进 prompt；`normalize_essay_grade` 钳制分数、band 缺失按分数兜底、**四维分和与总分偏差 >1 分时按权重（内容.4/结构.2/语言.3/格式.1）重算**、丢弃 `original` 为空的改错项、字符串字段按换行规整成列表。
- 手写稿照片**逐张** `_vision_extract_text` 转录后合并再走文本批改（守第 5 节"先提文字再分析"）；视觉指令要求第 1 行输出【题目】、正文**原样转录**、看不清写 `[?]`、**严禁替学生改错词**（否则批改等于自问自答）。转录通道与 `/ai/ocr` 一致：`_vision_providers()` 顺序回退 + 本地 Windows OCR 兜底。
- `POST /api/essays/grade`（text 优先，`persist` 默认存档并回 `record_id`）、`GET /api/essays`（kind/分页，`_row_brief` 带 kind_name + excerpt）、`GET|DELETE /api/essays/{id}`。
- **后端测试** `tests/test_essay.py` 12 个（归一化各分支 + API 全流程），后端 **165** 全绿。

**前端**：录入页第三个 Tab「英语作文批改」（`components/EssayPanel.vue`，粘贴照片走 CaptureView 的 essay 分流）+ 档案页 `/essays`（`views/EssayView.vue`，整卡可点 + 分数趋势条 + 印章空态）+ 结果组件 `EssayGradeResult.vue`（分数印/四维 bar/**逐词 diff**）+ `utils/essayDiff.js`（LCS 逐词，标点随词，避免 `home.` vs `home` 误判两处改动）。"存入错题库"走普通错题（`question_type=solution`），**先匹配「英语」科目，匹配不到直接 toast 拒绝**——`subject_id` 是必填 int，传 null 会被 pydantic 422。
- 顺手补 `AppLayout` 的 `LIBRARY_NAV`：`/papers` 真题库**原本没有导航入口**（只能手输 URL），与 `/essays` 一起补上。

**踩坑（都是会被静默吞掉的那类）**：
1. `from app.services.ai_service import _chat_json` 会把函数**绑死在原模块**，`patch.object(ai_service, "_chat_json")` 打不中 → 单测在 CI 里真调了 DeepSeek（返回 402）。改成 `import ai_service` 后按模块属性调用（`_vision_extract_text` 同理）。
2. 模板里写 `**原样转录**` 会把星号显示出来（不是 markdown 上下文）；`<GlassCard>` 用了没 import 只会运行时 undefined，build 不报错。
3. prettier 会把多语句内联 `@change="a(); b()"` 拆成属性换行 → 3 个单测当场红。改成具名方法 `onImagePicked(event)`。
4. `error()` 返回**真实 HTTP 状态码**（400/404），测试别只断言 body 里的 code。
5. TestClient 不进 lifespan，`setUpClass` 里必须显式 `init_database()`，否则 `no such table: essay_records`。

**验证**：后端 165 + ruff check/format 干净；前端 eslint(0 warning) + prettier + Vitest **70** + `npm run build`；E2E **37** 全绿（`card-click` 新增作文卡整卡可点与"删除只弹确认框、确认后卡片换成空态"两条真命中用例，`render-smoke` 加 `/essays`）。生产 8000 重启后真机自查：`/essays` 浅色（印章空态/Dock 高亮正确）、`/capture` 深色作文 Tab，零 console/page 错误。
⚠️ **未验到的部分**：DeepSeek 与智谱两把 key 目前都是 `402 Insufficient Balance`，**真实批改的 prompt 效果无法端到端确认**（代码路径到 AI 调用前正常，失败会以 502 + 明确 message 返回）。充值后需补一次真机批改。

## 2026-09-19 · 全局考研倒计时印批 + 作文批改真机复核（`d8c82c4`，用户：DeepSeek 已充值；倒计时要全局、更醒目更大）
**真机复核（上一批欠的一次验证，已补上）**：`POST /api/essays/grade`（e2_long，一段故意写错的 132 词图表作文，`persist:true`）→ 200，`record_id=1`，**9/15 第三档**，四维 3/2/2/2（和=总分，归一化没触发重算），8 条逐句改错**全部成立**（`the number...have`→`has`、`The chart show`→`shows`、描述 2021-2023 数据用现在时→过去时、`There have two reasons`→`There are`、`is convenience`→`are convenient`、`make a good use of`→`make good use of`），并给出「字数不足 150 必须降档」的定档理由 + 967 字同题范文。结论：**评分严格度与改错质量达标，不需要调 prompt/档位**。
⚠️ 踩坑：curl 的 `-d '{...中文...}'` 在 Windows 上会被 argv 码页弄成非法 UTF-8，FastAPI 直接 400 `There was an error parsing the body`（**不是**接口的问题）。带中文的 JSON 请求一律写成文件再 `--data-binary "@file"`。

**全局倒计时**：
- 后端：`stats_service._exam_countdown` 提为公开 `exam_countdown()`，新增 `GET /api/exam-countdown`（纯日期计算、**不查库**，所以外壳每页取一次也不心疼）；`/api/stats` 里的 `exam_countdown` 字段保留（老前端兼容）。新增 `tests/test_exam_countdown.py` 3 用例（未来/日期非法/已考完）。
- 前端：新基件 `ui/ExamCountdown.vue` 挂进 AppLayout 外壳 —— 桌面右上角悬浮印（42px 渐变数字 + 朱砂 kicker + 洒金描边 + 掠光 sheen + 呼吸光晕，`right: max(16px, calc(50vw - var(--content-max)/2 + 6px))` 与正文右边缘对齐），窄屏走 `.mobile-bar` 紧凑 chip；三档语气（`<=7` 冲刺洒金、`<=30` 紧迫加快脉动、常态）；入场串在 `body.app-ready` 后面（与 Dock 同批落下）。取数在 AppLayout：挂载一次 + 10 分钟刷新，`onUnmounted` 里 `clearInterval(examTimer)`。
- **统计页 hero 的 `cd-strip` 已删**（含三个 computed 与样式）—— 同屏两个倒计时是重复，用户要的是"挪成全局"。
- 测试：`tests/examCountdown.test.js` 4 用例；E2E `fixtures.js` 补 `/api/exam-countdown` 打桩，并把「`.exam-cd` 可见且含 91」加进 **11 条渲染烟测**（漏打桩或外壳没挂上 → 22 个用例全红，正是想要的兜底）。
  - VTU 坑：根节点带 `v-if` 时 `wrapper.exists()` 仍为 true（实例在，根是注释节点），而 `find('.x')` **不查根自己**，两个都会让"不渲染"的断言假通过 → 用 `element.nodeType === 8` 断言，并在正常分支加 `nodeType === 1` 作对照。
- 真机自查（生产 8000）：浅/深两主题下印章几何 `[1157,14,132,74]`、与 Dock 间隙 31px、`elementFromPoint` 命中自身（没被盖住）；窄屏 420px 顶栏 `scrollWidth === clientWidth`（没挤出横向滚动）；零 console/page 错误。
- ⚠️ **一次 E2E 假红**：改完后第一次全量跑 `/vocab`、`/knowledge` 两条 desktop 烟测失败，单跑与重跑都绿（37/37）。冷启动 vite + 2 workers 的争抢，符合"并发争抢假红"的老毛病；**结论前至少跑两遍**，别被单次红牵着改代码。

测试：后端 **168** + ruff 干净；前端 Vitest **74** + eslint/prettier + build；E2E **37** 全绿。

## 2026-09-19 · 全栈体检第 1 批：P0 数据与可用性包（`87228c0`）

体检清单（前后端 7 张表）见本次对话产出；这批只做表里 P0 的 7 行，全是一类问题：**接口照样 200、页面照样渲染，只有数据/文件在悄悄变坏**。

**后端**：
- **B1 批量删图泄漏**：`batch_mistakes(action='delete')` 原来只删行、不删配图文件（单题删除路径是对的，批量漏了）→ 实测 `data/images` 里 **102/152 个孤儿**，内容仍能通过 `/images/<name>` 直接访问（是隐私问题，不是磁盘问题：总共才 1.1MB）。改为删行前取回 `images`、提交后 `remove_image_files()`。
  - 新增 `scripts/clean_orphan_images.py`：**默认 dry-run**，`--apply` 才删，`--keep-days` 保护正在写入流水线里的新文件。引用来源是 `mistakes.images` + `exam_questions.diagram_image` 两处（库里带图片列的表就这两个，只按 mistakes 判定会把真题图示题的原图删掉）——解析不了的 JSON 保守跳过，宁可漏报不误删。真实数据尚未执行清理，等用户点头。
- **B2 快照静默失败**：`snapshot_database()` 的 `except Exception: return None` 会吞掉一切异常，而调用方正对着用户说"可回滚"。现在失败写 `logger.exception`，批量删除 / 导入两条路径按 `None` 把响应 `message` 降级成"快照失败 —— 本次无法一键回滚"。`/api/system/snapshots` 本来就报 500，没动。
- **B3 批改结果被 INSERT 失败带走**：`/api/essays/grade` 的存档段现在整块 try 住，失败仍返回 200 + `record_id:null` + `persisted:false` + `persist_error`；`EssayPanel` 见 `persisted === false` 补一条 warning toast（否则用户会去档案页找这条，找不到就以为从没批过）。
- **B4 PUT 抹掉精读字段**：`MistakeUpdate` 里 `passage_text: str = ''` 这类默认值会让"没带这个键"和"显式清空"长得一模一样。router 传 `body.model_fields_set` 进 `update_mistake(provided=...)`，服务层对 `ATTACHMENT_KEYS`（`images` + 5 个 passage/english 列）按库里原值回填。前端 `MistakeForm` 一直提交完整字段所以行为不变；`images` 那条尤其要紧——原来一个不带 `images` 的 PUT 会把**文件**也删掉。
- **B9 空文字仍往下分析**：`_analyze_standard_content` 里 `except Exception: pass` + `text or "请分析这道题。"` 看着像活的编造路径，**查了调用方才发现唯一调用点 `ai_english.analyze_english` 已有 `if not source_text.strip(): raise` 前置守卫，且只以 `images=[]` 进来** → 那条分支是死代码，不是在线 bug（教训：体检表里每条都要自己复核过再写进结论）。仍按第 5 节约定补成第二道闸：提字失败改 `logger.warning`（不再静默），文字为空抛 `AiRequestError`，并把 `"请分析这道题。"` 这个占位 content 删掉。
- **F10 判分双源**：新增 `answer_service.judge_letters()`（取 A-D、去重、排序整体相等），`judge_multi` 变成它的别名；`review_mistake` 在 `question_type in (choice, multi)` 且 `user_answer` 非空时**用服务端结论覆盖前端传来的 result**（fill 早就这么做了）。没传 `user_answer` 的 Q/W 自评路径不受影响（新增用例专门钉住这条）。
  - 前端 `normalizeLetters` 原来**不去重**（`'AAB'` vs `'AB'` 判错，后端判对）→ 补 `new Set`。两端各钉一张同样的用例表（后端 `test_data_safety.TestScoringSingleSource`、前端 `examScoring.test.js`）。
  - 顺带抓到自己写的 F821：`review_service` 里 `judge_letters` 忘了 import，而**182 个测试全绿**——说明那条分支原本没有任何覆盖。补了两条覆盖它（服务端覆盖 + 自评不覆盖）。

**前端**：
- **F1 KaTeX 字体被 base64 内联**：`assetsInlineLimit` 的白名单只写了 `woff2?`，20 个 `.ttf` 照旧内联 → `dist/assets/katex-*.css` **708,986 B**；扩成 `\.(woff2?|ttf|otf|eot)$` 后 **24,475 B**（-96.5%）。真机复验（生产 8000，错题详情弹窗）：12 个 `.katex` 且 `.katex-html` 全部渲染、5 个 KaTeX woff2 命中 200、**0 个 ttf 请求**、0 个 4xx、零 console/page 错误（现代浏览器根本走不到 ttf 那档 fallback）。

**测试**：后端 **182**（新增 `tests/test_data_safety.py` 14 个：图片泄漏 2 + 快照降级 1 + PUT 附加字段 3 + 批改存档 2 + 判分口径 4 + 空文字闸 2）、前端 Vitest **75**、E2E **37** 全绿；ruff check/format、eslint、prettier、`npm run build` 均干净。
**文档**：AGENTS.md 第 3 节加"数据路径禁止静默失败"三条铁律（快照降级 / AI 结果不许被 INSERT 带走 / 删行必删文件）+ PUT 附加字段语义 + 字母题判分单一口径；第 5 节补"提不到文字必须报错"；`docs/api.md` 补 `/api/essays` 整节（上一批漏了）与三处契约说明。

## 2026-09-19 · 全栈体检第 2 批：P0 键盘与录入保护包（`46d78a1`）

体检表里 P0 的第二批：全是"鼠标用户看不见、键盘用户进不去 / 一次误点就丢一整场"的问题。

**F6 全站错误边界（`utils/errorBoundary.js`，新）**
- 改前全站没有 `app.config.errorHandler`、没有 `window.onerror`：任一组件在 setup/render 抛错 → `#app` 停在半渲染（实测就是白屏），而收启动屏的逻辑挂在挂载成功之后 → 白屏上还可能压着遮罩，用户只能手动刷新，刷新前什么信息都不留。
- 现在：`installWindowGuards()` + `installErrorBoundary(app)`，`app.mount('#app')` 包 try/catch。面板 `#km-fatal` 用**原生 DOM** 建（走到这里 Vue 本身已不可信），`role="alert"` + 重新加载/回首页/知道了三键，一次会话只弹一次（闸门不随「知道了」重置，避免砸脸）。资源 404 的 `error` 事件没有 `event.error`，按此过滤；`unhandledrejection` 只写日志不弹窗（接口 4xx/5xx 已由 axios 拦截器弹过 toast）。
- 单测 8 个（`tests/errorBoundary.test.js`）。happy-dom **没有 `PromiseRejectionEvent` 构造器**，用普通 `Event` 挂 `reason` 才能派发。

**U1 难度星级键盘可达（`ui/UiStars.vue`）**
- 改前整组是 `role="img"` 的裸 span、无 tabindex、只有 `@click` → 录入页**必填项**「难度」对键盘用户完全不可达（`MistakeForm.vue:383`）。
- 现在 `role="radiogroup"` + 每颗星 `role="radio"`，**roving tabindex**（组内唯一 Tab 落点 = 选中那颗，0 星时落第 1 颗），←/→/↑/↓ 加减、Home/End 到端点、Enter/Space 确认，`nextTick` 里把焦点跟到新选中星；`:focus-visible` 用 `var(--accent)` 描边。只读模式保持 `role="img"` 且**不暴露任何 tabindex**（列表卡片不该被 Tab 逐个穿过）。半星（AI 给 3.5）展示不变，键盘落点取整。
- 单测 8 个 + E2E 1 条。**为什么必须补 E2E**：VTU 的 `trigger('keydown')` 是直接在元素上派发事件，等于跳过"这个元素根本进不了 Tab 序列"这个真缺陷；`keyboard-guard.spec.js` 改成"聚焦星级前面的复选框 → 按一次 Tab → `activeElement` 必须是 `[role=radio]`"，改前这条必然红。
- 顺带：`QuestionImages.vue` 的 `figure` 补 `role="button" tabindex="0"` + Enter/Space + `:focus-visible`，并把 `openPreview(images.indexOf(img))` 改成 `openPreview(index)`（`showList` 是前缀切片，下标本就等价；按 URL 找会在图片重复时全跳到第 1 张，且哪天改成非前缀切片就**静默**错位）。

**U6 模考中途离开保护（`views/ReviewView.vue`）**
- 模考作答只暂存在内存（未交卷不写库），改前刷新 / 点 Dock / 点「重新选题」都会让整场作废且**零提示**。
- 两道挽留：`beforeunload`（刷新、关标签页）+ `onBeforeRouteLeave`（站内导航，配全局 `ConfirmHost`，所以弹窗不会被路由卸载带走）。判据是 `mockAnsweredCount > 0` —— 一题未答没有东西可丢，拦住就是骚扰。监听器在 `onMounted`/`onUnmounted` 成对注册。
- E2E 覆盖整条链（未作答放行 → 作答后弹确认并报"已作答 1 题" → 取消留在原地且答案还在 → 确认才走）。

**U14 六处已确认 bug**
- `KnowledgeView`：`?tag=` 只在 `onMounted` 读一次 → 人已经在知识点页时从错题详情点别的标签，vue-router 只换 query、组件复用、钩子不重跑，**点了没任何反应**。补 `watch(() => route.query.tag)`（同步筛选 + `page=1` + 重新取数）。
- `StatsView.loadStats`：`/dashboard` 失败后回退的两个请求**没带 silent** → 拦截器各弹一条 toast（同屏两条重复报错），而 catch 吞掉后页面仍是全 0。改成 silent + `Promise.allSettled`（一个接口活了就先渲染）+ 一条汇总 toast。
- `MistakeListView` 搜索高亮：`document.querySelectorAll('.card-grid .question-text')` 换成页根 `ref="listRoot"` 内的查询。当前类名恰好只在列表里用（`UiModal` 又 teleport 到 body），所以**不是在线故障**，但 `.question-text` 是通用类名、全局查询会把 Range 画到列表外并留悬空引用 —— 按"高亮只属于本页"收敛。
- `DesignView` 分页演示：模板里裸写 `:total="83"` → 提为 `demoTotal` 并派生 `demoPages`，标题改成「当前第 2 / 9 页」，换每页条数后不再可能显示一个不存在的页。
- 复核记录：体检表里这条写的是"高亮会串到复习页"，实测 `.question-text` 只在 `MistakeCard` 出现，**结论按实况改写成"防外溢的收敛"**，没有夸大成 bug（上一批 B9 也是同类自我纠正）。

**测试与自查**：后端 **182**（未改后端）；前端 Vitest **91**（+8 errorBoundary、+8 UiStars）；E2E **39**（+2）全绿，跑两遍无假红；ruff / eslint / prettier / `npm run build` 干净。生产 8000 真机（深色主题）：`/design` 零 console 消息；Tab 落点 `aria-label="3 星"`、`:focus-visible` 命中、描边 `rgb(224,88,61) 2px`；按 → 后 `aria-checked` 与 tabindex 一起移到第 4 颗、组标签变「难度 4 / 5」；坏图片不触发错误面板，派生 `ErrorEvent` 则面板出现（`role=alert`、z-index 9999、深色卡面 + 朱砂边）。

## 2026-09-19 · 全栈体检第 3 批：工程性收敛（索引 / 接口契约 / 列表加载，`e0bd126`）

**B5 多步写入的事务原子性 —— 复核后判定为"不是缺陷"，本批没改事务。**
逐条读了所有多语句写路径：`create_mistake`（补词条 + INSERT 错题 + 同步标签）、`update_mistake`、
`review_mistake`（UPDATE 调度 + INSERT 记录）、`delete_mistake`/`batch_mistakes`（连删四张表）、
`import_mistakes`（`with conn:` 包住整批）—— **全部只在末尾 commit 一次**，中途异常靠 `conn.close()`
回滚，`sync_mistake_tags` / `ensure_knowledge_tags` 内部也没有偷偷 commit（这是最容易破原子性的地方，专门查了）。
唯一"一条函数里多次提交"的是后台拆题流水线的 `_set_status`：那是**进度上报**（extracting→structuring→done），
故意即时落库，不属于该收敛的对象。体检表里这一条按实况降级为"已验证无问题"。

**B6/B7/B10 → v11 索引补齐（`app/models/tables.py`，共 5 条，全部对着真实 SQL 建）**
- `idx_solution_grades_mistake (mistake_id, id DESC)`：错题详情每次都跑
  `WHERE mistake_id=? ORDER BY id DESC LIMIT 1` 取 last_grade，删错题还要按 mistake_id 批删 —— 此前**整表无索引**。
- `idx_vocab_created (created_at DESC, id DESC)`：生词本是增长最快的表（820 行且一篇精读进几十条），
  列表默认按它排序。真库 EXPLAIN 现在走 covering index 顺序扫，不再建临时 B 树。
- `idx_mock_records_created (created_at DESC, id DESC)`：`GET /api/mocks` 的固定形状。
- `idx_exam_papers_source_year (source_path, year)`：登记真题的幂等查重。
- `idx_essay_records_kind_id (kind, id DESC)` **替换** 原单列 `idx_essay_records_kind`：
  档案列表是 `WHERE kind=? ORDER BY id DESC`，单列索引命中后还要再排一次。
- **`mistake_tag_map` 不建索引**：`(mistake_id, tag)` 主键就是 `WHERE mistake_id=?` 的 best index，
  体检表把它列成"缺索引"是错的，已在测试 docstring 里钉住免得下次重复报。
- **不走 `MIGRATION_VERSION` 门控**：索引全是 `IF NOT EXISTS` / `IF EXISTS` 的幂等 DDL，
  而 `init_database()` 每次启动都 `executescript(TABLES_DDL)`，门控只管一次性全表扫描 —— 所以版本仍是 10。
  顺带删掉 `migrate_database()` 里那句重复的 `CREATE INDEX idx_essay_records_kind`：它在 DDL **之后**运行，
  留着会把刚 DROP 的单列索引又建回来（写成注释 + 一条 `test_dropped_single_column_index_stays_gone` 钉死）。
- **踩坑**：`EXPLAIN QUERY PLAN` 的断言在只灌 1~3 行的表上**必红** —— SQLite 成本模型认定扫小表更便宜，
  索引建对了、查询写对了也照样输出 SCAN。测试改成灌 400 行 + `ANALYZE`（`tests/test_index_coverage.py`，10 条，
  既验"索引存在"也验"计划真的用上"）。真库重启后复核：5 条到位、旧名消失、四条查询逐条命中。

**C2 分页参数名统一**：`GET /api/essays` 的 `per_page` → `page_size`（全站唯一例外名消除）。
后端、`EssayView` 调用、docs 三处同步；新增契约测试断言**旧名字必须彻底失效**（FastAPI 忽略未声明 query →
回落到默认 15 条），否则两套名字并存时前端漏改是静默的。

**C3 `docs/api.md` 补齐与纠错**：此前有 **11 个端点从未记录**（`/api/papers` 全套、`/api/mocks` 读写、
`/api/reviews/blocks`、`/api/reviews/forecast`、`/api/reviews/today?category=`、`practice?mistake_id=`、
`/api/ai/sense`、`/api/ai/weekly-report`、`/api/vocab/import-english`、`/api/export/anki`、`/api/exam-countdown`），
且「系统」小节整块重复两次。现在：合并为一个「系统」段、新增「真题库与模考存档」段、补齐上述条目，
并在开头写下**两种信封的约定**（有分页 → `{items,total,page,page_size}`；无分页全量 → 裸数组；
`mistakes`/`vocab` 不传 `page` 时退化为数组）。写文档时自己错了一次并当场改掉：整卷模考**不走**
`/reviews/practice`，是前端取 `GET /api/papers/{id}` 客户端组卷 —— 文档必须以代码为准。

**C1 响应信封是否统一 —— 判定为"约定，不是 bug"，只补文档不改代码**：裸数组是有意的（全量集合无需再包一层），
把 6 个数组接口改成 `{items,total}` 会连带改 6 个前端调用点 + 一批测试，收益只是好看。

**F8/F9 `composables/useResourceList.js`**：把「loading / loadError / items / total + 失败清空 + 重试位」
从四个纯列表页收敛到一处（`EssayView` / `KnowledgeView` / `VocabView` / `FormulaView`）。
理由不是少写几行，而是这类状态**错一次就静默**：上一批刚踩过"`useMistakeFilters` 早 return 了 loadError、
视图解构漏一个字段 → 错误 UI 永不渲染、三道质量关卡全绿"。composable 只认一种返回形状，漏不了；
两种后端信封也在这一处认完（`KnowledgeView` 原来自己写了一遍 `Array.isArray` 分支）。
`KnowledgeView` 的"详情弹窗跟随列表刷新"留在外面（`await fetchList()` 之后同步），不为此加钩子参数。
**没接进来的页面是刻意的**：`MistakeListView`（筛选状态要同步 URL，已在 `useMistakeFilters` 里）、
`ReviewView`（沉浸流程，队列不是资源列表）、`PapersView`（轮询型加载，只在库为空时才报失败）、
`StatsView`（十几个面板各自兜底，见 AGENTS 6.5）。新增 7 条单测（两种信封 / null 响应不算失败 /
失败清空并置位 / 重试清位 / loading 收敛 / fetcher 同步抛错也被收住）。

**测试与自查**：后端 **193**（+10 索引计划、+1 essay 分页契约）；前端 Vitest **98**（+7 useResourceList）；
E2E **39** 全绿；ruff / eslint / prettier / `npm run build` 干净，`katex-*.css` 仍是 24,475 B（字体未被重新内联）。
生产 8000 真机逐页验数据加载（重构的是取数层，E2E 打桩返回空数组、测不出真回归）：
`/vocab` 30 张卡、`/knowledge` 9 张（=page_size）+ 分页器、`/formulas` 7 张（"共 7 条"与库一致）、
`/essays` 平均得分率 60%（=库里那条 9/15，说明 items 真的穿过 composable 到了 computed）；四页零 console 消息。

## 2026-09-19 · 全栈体检第 4 批：AI 通道遥测 + 静默降级显形 + 密钥脱敏（N1 / C5 / C6，`72f63eb`）

**N1「建 AI 网关」按实况降级成"在唯一漏斗处记账"**：grep 过一遍 `backend/`，`chat/completions` 的出口
只有 `ai_service._chat` 一条（没有第二处 urllib/httpx 直连端点）。既然只有一个出口，再包一层
"gateway 类"就是为假想需求加抽象；改成在 `_chat` 上记账，**代价 60 行、覆盖全部 AI 调用**。

**`_chat` 拆成「记账外壳 + `_chat_request` 实体」**：原来那个重试循环（`finish_reason=length` 翻倍预算、
最多 4 次尝试、`with_meta` 双返回）整段搬进 `_chat_request`，固定返回 `(content, meta)`、`with_meta`
参数在外壳保留。外壳只负责：起计时、catch 异常记一笔、成功后按"内容是否为空"记一笔。
- **通道键是 `"{model} @ {host}"` 而不是 model**：`AI_VISION_MODEL`(glm-4.6v-flash) 与
  `AI_VISION_MODEL_FALLBACK`(glm-4.6v-flashx) **同名不同端点的情况真存在**（智谱两把额度），
  只按 model 归并会把两个通道的账混成一本。
- **HTTP 200 但 content 为空也算失败**（`输出为空（finish_reason=…）`）：这正是第 5 节第 4 条踩过的那类
  ——推理把预算吃光、`content=""`，链路"成功返回"却什么都没有。
- **`AiNotConfigured` 不计数**：一个请求都没发出去，记进通道账会把"没配 key"污染成"通道在报错"。
- 耗时口径**覆盖 `_chat` 内部的重试与预算翻倍**，即"这个通道交付一次结果要多久"，不是单次 HTTP 延迟。

**429 单独计数**：`metrics.record()` 里 `status_code == 429` 累进 `throttled_total`，**不进** `errors_total`
也不进 `recent_errors`（那是 `>=500` 的口径）—— 被 `ai_rate_limit` 挡掉的请求在 HTTP 层是"正常响应"，
但用户看到的就是"点了按钮没反应"，必须有一笔账能回答"今天被限流了几次"。

**静默降级现在三处同时可见**（以前只在局部变量里，日志一行异常）：
1. `GET /api/health` 的 `data.metrics.ai.by_model`：每通道 calls / errors / truncated / avg_ms / max_ms /
   **reasoning_avg** / `last_error` + `last_error_at`。按 `(-calls, -errors)` 排序，主力通道在前、
   出错那个的 `last_error` 一眼可读。`reasoning_avg` 是刻意留的：它暴涨说明 `max_tokens` 正在被
   reasoning 吃（AGENTS 5.4 的那次 11998/12000 事故，从此不用翻日志）。
2. **WARN 日志**：`ocr_image` / `english_analysis` / `_vision_extract_with_fallback` / 作文 `_transcribe`
   四条多通道轮询，每次退到下一个通道都 `logger.warning("…通道 %s 失败，改用下一个兜底通道：%s", …)`。
3. **用户可见的 `message` 后缀**：新 `_degrade_note(failed_channels)` 产出
   `（首选通道 X 失败，已降级）`，拼在"视觉模型识别完成"/"英语整篇解析完成"后面。

**前端为什么本来"看不见"降级：`CaptureView` 的 gate 写死在 `method === 'local'`** —— 退到本地 OCR 才显示
后端 message；首选通道挂了、退到**另一个视觉通道**时 `method` 仍是 `vision`，note 就算发了也不渲染。
改成 `(method==='local' && msg) || msg.includes('已降级')`。**"已降级"这三个字是前后端锚点**，
`_degrade_note` 的 docstring 里钉了这句话，改字必须同步改前端。
作文批改的转录降级**只进日志和账本、不进 message**：那要把 `_transcribe` 改成返回三元组，
只为多一处提示不值得 —— 已记为取舍，不是漏做。

**密钥脱敏落到每一条"上游错误文本会离开进程"的边界**（`metrics.mask_secret`，正则三叉：`sk-…` /
`api[_-]?key=…` / `Bearer …`）：`/api/health` 的 `last_error`、`_ai_error_message`（两个端点各自手写的
`error(502, str(exc))` 收敛到它）、本地 OCR 的 reason、超时 RuntimeError、`knowledge`/`mistakes` 的 502、
以及 `exam_papers.status_note`（后台拆题的异常文本会直接显示在 /papers 页面上）。
DeepSeek/智谱的 4xx 会把响应体原样带进异常，网关偶发回显请求头 —— 只靠"我们不打印 key"的自觉是不够的。

**测试**：`test_ops.py` +5（429 单计 / 通道归并 / `last_error` 里 key 被打码 / truncated+reasoning_avg /
reset 清 AI 与限流）；新增 `tests/test_ai_telemetry.py` 10 条（外壳记账 6 条 + `/api/health` 契约 1 条 +
`RouterDegradeTest` 三条：`/api/ai/english`、`/api/ai/ocr` 首选失败后退到兜底时**必须 200 + message 含
"已降级" + 含失败通道名**，首选直接成功时**不许出现"降级"**）。
**CI 陷阱**：断言里硬编码 `api.deepseek.com` 会在 CI 必红 —— CI 没有 `backend/.env`，
`settings.AI_BASE_URL` 回落默认端点。测试改为 patch `AI_MODEL`/`AI_BASE_URL`/`AI_API_KEY`，
期望通道串由模块常量拼出来。

**E2E 修了一次"假 bug"**：新增 2 条用例后整批红了 3~14 个 `Test timeout of 30000ms exceeded`，
**每次红的都是随机用例、且含本批根本没碰的 `card-click`/`keyboard-guard`/`render-smoke`**；
`--workers=1` 或单跑全绿 → 真凶是 `playwright.config.js` 的 `workers: process.env.CI ? 2 : undefined`：
本地 undefined 取「核数一半」，十几个 worker 共用同一个 vite dev server，冷编译排队被放大成超时。
钉成 `workers: 2`（串行全跑 2.0m、并发 2.1m，**并发本来就没省下时间**）。
`e2e/fixtures.js` 加 `withMessage(data, message)`：`mockApi` 默认只回 `message:'success'`，
要验"只在 message 里留痕"的行为必须有这个逃生口。

**验证**：后端 **208**（193→+15）、Vitest **98**、E2E **41**（`--workers=2` 复跑 41 passed 1.4m）；
ruff check+format / eslint / prettier / `npm run build` 干净，`katex-*.css` 仍 24,475 B；
pre-commit 6 项全 Passed；CI 同口径覆盖率 **71%**（`coverage report --fail-under=55`；
注意加 `--source=app` 会因不含 tests 而显示 59%，AGENTS 里那句"约 62%"是旧口径）。
**生产 8000 重启真机复核**：`/api/health` 新增段全部到位（`throttled_total`、`ai.by_model`），
跑一次真实 `/api/ai/sense?word=algorithm` 后账本出现
`deepseek-flash @ api.deepseek.com`：calls 1 / errors 0 / avg_ms 3152.6 / reasoning_avg 374。
**刻意没做**真机识图（一次 18s 的付费视觉调用只能证明"成功路径没被改坏"，而这已由单测 + E2E 双向钉住）。

## 2026-09-19 · 全栈体检第 5 批：能力拓展包（N3 导入去重 / X5 全站搜索 / X1 按标签直练 / N5 降级为索引可用，`6eb2d18`）

**取证先把范围改小了**（三项原判都被实测推翻，记下来免得下次又按清单原样立项）：
- **X1 已建一半**：错题详情的 `related_knowledge` 早就渲染成可点标签，缺的只是"练这些题"这一步，
  于是只做那一步，没有重做关联区；
- **N5「统计预计算」是投机工程**：真库上逐个量了 StatsView 那十几条聚合 SQL，**12–18ms**，
  物化到 `app_meta` 只会带来缓存失效这个新问题。降级成"把唯一两条整表扫的谓词改成能用上索引的写法"；
- **N3 只缺错题那一半**：`vocab_service` 本来就按词形去重，真正会翻倍的是 `POST /api/import`
  （同一份导出文件再导一次 → 全库 ×2），所以只做错题指纹。
- 未开工遗留：**N2 图片一致性治理**（`/api/system/integrity`）与 102 个孤儿图文件的 `--apply` 清理，
  都等用户明确批准再动（删文件不可逆）。

**N3 指纹判重的口径**（`mistake_service.question_fingerprint`）：归一化剥的是"复制粘贴 / 多次导出"
必然产生的差异 —— HTML 标签与实体、大小写、全部空白（含换行）、Markdown 强调符，图片只取**张数**参与
（`sha1("图片数|归一题干")[:16]`）。两条刻意的边界：
① **归一后 <8 字（纯图片题）返回空串 = 不判重，照常入库** —— 没有可比对的文字时判重只能靠猜，
误判的代价是"导入时静默丢题"，比翻倍严重得多（AGENTS 第 3 节那条数据路径红线的镜像）；
② 比对图片**字节**被否掉：一次批量导入里几十 MB data URL 全 sha256，又慢又没必要。
`duplicates: [{index, existing_id}]` 逐条给到"撞的是库里哪一条"，`message` 追加"重复跳过 N 条"，
前端 toast 同源显示（不是只报一个 created 数字）。既有库的 `images` 是 JSON 串，一次全表扫描把指纹
预先算进 dict（107 题量级），避免逐条 SELECT。

**X5 全站搜索的形状**（`search_service.search_all` + `GET /api/search?q=&limit=`）：五个实体各一条
`LIKE` + 一条同形状 `COUNT`，返回 `{q, limit, total, groups:[{key,label,total,items}]}`、**空组不返回**
—— 前端因此不需要知道系统里有几种实体，加第六种只改 service。`limit` 是**每组**条数，`total` 是各组
命中之和（面板要显示"还能更多"）。摘要 `_snippet` 以命中位置为中心截一段，让"为什么匹配上"一眼可见；
这里有个偏移量陷阱：**必须先把文本折叠成一行再找下标**，题干里全是换行，直接对原文 `find` 到的偏移
在折叠文本里对不上，截取位置会漂；折叠后搜不到（命中发生在被吃掉的换行处，如"自\n由"）则退回开头。
**`%` / `_` 按字面量匹配**（`like_pattern` + `ESCAPE '\'`）：通配符是用户内容的一部分而不是查询语法 ——
实测 `50%`、`a_b`、`%zzzq` 均 0 命中，`_` 单字符 82 命中（说明转义真在生效，不是碰巧没匹配上）。
`essay.py` 的 `?search=` 复用同一个 `like_pattern`，全站"按关键词 LIKE"只有这一个口径。
上 FTS5 的空间留在这个文件里（响应形状已按"分组 + 每组 total"钉好），但**现在这个量级不值得**（N6 仍 P2）。

**命令面板（`Ctrl+K`）从"跳页面搜索框"升级成真搜全站**，两处设计取舍：
- **作用域 chips 是"对已取回结果做本地过滤"，不再重新请求**：一次输入要打好几个实体，先全量拿回来
  再按类型筛，比每换一个 chip 发一次请求快且省；测试因此断言"整个用例只发一次 `/api/search`"。
- **分组渲染但键盘是一维的**：面板是扁平列表 + 分组标题，`visibleSections()` 给每组带上
  **扁平下标**（`rows:[{item,index}]`），active 判定用 `row.index`。这个转换是纯函数、单独导出并
  用 `tests/commandPalette.test.js` 钉住（含"跨组 ArrowDown 落在扁平第 2 项"），因为它是那种
  "DOM 里数对了、切组后就错位"的经典坑。落地页统一吃 `?search=`（错题/公式/生词/作文各自筛选参数
  名与视图一致），知识点走 `?tag=` 直达详情。
- 竞态：`runSearch` 带自增 seq，**旧响应不许覆盖新结果**；请求失败要清空 `groups`（留着会把上一次
  查询的结果当成"本次没搜到"）。

**X1「练这些题」**：详情弹窗底部的 `RelatedList` 加一枚按钮，走的查询参数与它自己那份列表**完全同源**
（`review?mode=curve&count=10&tag=<knowledge_tags[0]>`，就是 `get_mistake_detail` 算 `related_mistakes`
用的那个标签）—— 否则"看到的题"和"练到的题"会不是同一批，那是最难被发现的 bug 类型。按钮只在
既有错题**且**有标签时出现（没题可练就别摆一个点不动的按钮），点击后关弹窗再跳转。

**N5 降级项：`/api/reviews/forecast` 的两条 SCAN 改成 sargable**。原来写成
`date(next_review_at) < date('now','localtime')` —— 列被套进函数，SQLite 只能整表扫，
已有的 `idx_mistakes_next_review_at` 白建。换成**定宽日期串的范围比较**（`>= 今天`、`< 今天+days+1`）
后走索引。等价性是这次改动的全部风险，所以做法是**让 SQLite 自己当 oracle**：
`test_forecast_range_predicate_is_equivalent_to_date_comparison` 把新旧两条 SQL 跑在同一批
锚定日期（相对 `forecast_bounds` 生成，不是硬编码"今天"，否则过一天就红）的样本上逐行比对，
样本覆盖 `'YYYY-MM-DD HH:MM:SS'`（真库实际形状）、只有日期、带 `T` 的写法、NULL。
顺带修掉一个**既有**的口径不一致：旧 SQL 下界用 `localtime`、上界却是 `date('now')`+days 的 UTC，
现在两边都是本地日。分桶结果仍按 UTC 前缀分组（那是展示层的事，没动）。

**测试**：后端 **227**（+13 `test_search.py`、+6 导入去重、+2 索引计划/等价性、+essay `?search=` 契约）；
Vitest **111**（+8 commandPalette、+5 relatedPractice）；E2E **43**（+2 command-palette：
真键盘 ArrowDown/Enter 走完"分组结果 → 落 `/formulas?search=` 且列表真的被过滤"，
以及"Tab 换作用域只发一次请求"）。`e2e/fixtures.js` 补 `/api/search` 打桩，形状直接照
`search_service.search_all` 的响应抄，避免"打桩形状不对但前端自己 catch 掉"那类假绿。

**验证**：ruff check+format / eslint / prettier / `npm run build` 干净（`katex-*.css` 仍 24,475 B）；
生产 8000 重启后 curl 实测：`/api/search?q=导数` → total 18（错题 7 / 知识点 10 / 公式 1）、
摘要以命中为中心且 LaTeX 完整；`/api/search?q=chart` 命中作文题干且 `/api/essays?search=chart`
同条命中；通配符三条否定用例全 0；`/api/reviews/forecast?days=30` → `{"overdue":98,"items":[]}`
（库里最大 `next_review_at` 是 2026-09-17、今天 09-19，所以未来窗口为空是对的）。
**UI 不再用真机浏览器逐个走查**（被项目基线否决：E2E 已含"能不能打开"的烟测 + `npm run build` 是
模板编译的唯一门禁），本批把轮次花在 API 直连实测与静态门禁上。

**踩坑记录（提交时才红）**：`preflight hygiene` 钩子把 `frontend/src/**` 里的 `→`（U+2192）与
`↑`（U+2191）当"字符图标"拦掉，**注释里也算** —— `commandPalette.js` 两句注释被拦，改成 `->` 与
"上下方向键"。注意它**只在 `git commit` 时暴露**：同一次改动 `pre-commit run --all-files` 是 Passed 的
（脚本对传入文件清单的处理与暂存清单不同），所以"all-files 绿了"不等于能提交，最终以 commit 那一次为准。

## 2026-09-19 · 全栈体检第 6 批：N2 数据体检（只读巡检页 + 判定口径合一，`3cf1e8a`）

**用户决策记录（影响后面所有清理类动作的口径）**：给了三个选项后选**"先只做只读巡检页，暂时不删"**。
理由摆得很清楚：这批孤儿文件总共只有 **1.1 MB**（图片目录 15 MB），省空间根本不值得；
而**自动备份只备份数据库、不备份图片目录**，删错了没有任何回滚点 —— 收益微小 + 不可逆 = 先看清再说。
所以本批**一个文件都没删**，删除入口也没做进页面（只在文案里写清要用脚本 `--apply`）。

**真库实测（体检页要给出的就是这几个数）**：库里引用 50 张、磁盘上图片文件 213 个、
孤儿 102 个 / 1.1 MB、**保护期内 21 个**（最近 1 天生成，后台拆题图先落盘、`diagram_image` 后写库）、
**缺图 0 条**（没有"点开详情是破图"的记录）、坏 JSON 引用 0 条。
最大的三张孤儿是已删除试卷留下的 `exam_papers/18|19/p4.webp`（各 138 KB）。

**头号改动其实是一次重构：判定口径从两份合成一份。**
原来 `scripts/clean_orphan_images.py` 自带一套 `REF_SOURCES` + 遍历规则，页面若再写一套，
迟早漂移成"页面说干净、脚本说要删 102 张" —— 而那正是最需要一致的地方。
现在规则全在 `integrity_service`（`image_references` / `scan` / `orphan_paths`），
脚本与 `GET /api/system/integrity` 都是它的调用方；脚本只负责打印与 `--apply` 删除，
连"数一下保护期"这种话术都从报告里取，不再自己算。

**三条判定细节各有真实事故背景**：
- **按 basename 归并引用**：`mistakes.images` 存 `images/x.png`（相对路径），
  `exam_questions.diagram_image` 存 `/images/exam_papers/16/p0.webp`（URL）。比整串就会把一张图看成两个，
  引用侧少一条、文件侧多一个孤儿。
- **`exam_questions.diagram_image` 必须算引用**：脚本原来就写了这条并留着注释，
  本批把它钉成用例 `test_exam_diagram_counts_as_a_reference`（只按 mistakes 判定就会误删真题图示原图）。
- **坏 JSON 保守跳过但必须回数**：少读一条引用 = 把那张图往"孤儿"那边推，所以
  `unparseable_refs` 要出现在响应与页面上，不能静默。
- 缩略图跟随主图（`_thumbs/<stem>.webp`）；孤儿清单**按体积倒序**（要看/要清的都先关心大的），
  超过 `limit` 时 `orphan_truncated` 明说"只列了前 N 个"。

**页面**：`/integrity`「数据体检」，**不进 Dock 导航**（维护页，和 `/design` 同性质），
命令面板 Ctrl+K 有「数据体检」动作可达。四块瓷砖 + 两张清单，
瓷砖**特意为 0 也占位**（"缺图 0 条"是这页最有价值的结论，不是没数据）；
`UiLoadError` + `UiEmpty` 两种状态分开（失败绝不能显示成"很干净"）；
页面上**没有删除按钮**，并有专门用例断言这一点（按钮文案里不许出现"删"/"清理"）。

**测试**：后端 **240**（+13 `test_integrity.py`）；Vitest **118**（+7 `integrityView.test.js`，
纯函数在 `src/utils/integrity.js` 里单独导出以便直接断言）；E2E **45**（render-smoke 多一条 `/integrity`，
`fixtures.js` 的 `integrityReport` 照 `scan()` 的真实形状抄）。
**端点与脚本同源已被实测双向验过**：同一时刻跑两者都是 `50 / 102 / 21 / 1.1 MB`。

**两条踩坑（都已写进代码注释）**：
1. 用例里那个"固定的现在"**必须落在过去**。第一版取 `NOW=1.8e9`（约 2027-01，比真实时钟晚），
   于是 `scan(now=NOW)` 的用例全绿、走真实时钟的**端点用例却查不出孤儿** ——
   文件 mtime 比真实 cutoff 还新，被算进"保护期内"。改成 `1.7e9`（2023-11）后两条路径一致。
2. 临时库在类内共享，而这批用例**要写库**：`setUp` 不清 `mistakes/exam_questions/exam_papers`
   就会让上一条用例的引用混进下一条的断言（红成"孤儿数对不上"这种莫名其妙）。
   另有一次自伤：`ruff format` 的路径写成仓库根，顺手把 14 个无关脚本格式化了 —— 已退回，
   以后格式化只写 `app tests` 两个目录名。

## 2026-09-20 · 全栈体检第 7 批：N11 快照/回滚做真（`755389d`）

**为什么要做**：`GET|POST /api/snapshots` 从第一批起就在，批量删除/导入前也确实打了快照，响应文案
还写着"可回滚"——但**全站没有任何一个入口能把这份快照用回去**。那句话的真实含义是
"可回滚，请自己打开 sqlite 命令行"。这就是体检口径里最典型的一类：接口在、文案在、能力不在。

**后端**：`database.restore_snapshot()`（+ `snapshot_label()` 把文件名末段翻成来源标记，
`list_snapshots()` 多返回一个 `label`）+ `POST /api/snapshots/restore`（`schemas.SnapshotRestore`）。
四根不可移动的桩，每根都有用例：
1. 只接受 `SNAPSHOT_NAME_RE` 且 `resolve()` 后仍在 `BACKUP_DIR` 内的文件名 —— 一个能整库覆盖当前数据的
   入口如果接受任意字符串，就等于把备份目录开成"读哪个文件都行"；
2. 覆盖前必须先给当前现场打 `before-restore`，**打不出来就中止**（没有反悔点不动手）；
3. 打完反悔点后**复查目标快照还在**：`snapshot_database()` 会按 `MAX_BACKUPS` 清最旧一份，用户挑的
   正好是最旧那份时它此刻已消失，少了复查下一步 `sqlite3.connect()` 会凭空建一个空库并把当前数据
   覆盖成空白（一次静默的全库清空）；
4. 覆盖完重跑 `TABLES_DDL` + `migrate_database()`，否则回到 v8 那份会让 `/papers` 打到 500 且要重启才自愈。
老快照里缺的表在 `tables_*` 里记 `null` 而不是 0（"没有这张表"和"这张表 0 条"是两件事）。

**两个踩坑**：
- **句柄要关在打反悔点之前**。第一版照"POSIX 直觉"写着"源句柄一路持有到复制完，反正 Windows 打开的
  文件删不掉"，结果第 7 条用例真红在这一点上：`unlink` 抛 `WinError 32` → `snapshot_database()` 兜底
  返回 None → 回滚以"反悔点失败"中止。**数据是安全的，但错误结论是误导的**（真因是保留份数清理）。
  改成"验完就关 → 打反悔点 → 复查还在 → 再开一次"，两个平台同一条路径。
- **造边界数据要按实际上限造**。用例里写 `..._090000_l33x4400.db` 想测"40 字符标签之外"，可那个标签
  只有 8 个字符，是个**合法名** → 返回 404，断言 `(400, 422)` 红。这类"看着在测边界、其实没碰到边界"
  的用例比没测更糟（它给你一份虚假的覆盖感）。

**前端**：`/snapshots`「数据备份与回滚」页（不进 Dock，Ctrl+K 可达，与 `/integrity` 同性质）：
四块瓷砖（可用份数 / 最新一份 / **最早一份可回到** / 目录占用）+ 列表（时间·来源翻人话·大小·每行一个
回滚入口）+「立刻备份一次」。回滚要**手输 `RESTORE`**（服务端另有 `confirm === name` 那道，是给脚本
兜底的 —— 让人逐字敲文件名不叫确认，叫折磨），成功后把**前后各表条数对照**和反悔点文件名留在页面上
（只飘一条 toast 的话，用户关掉就再也找不到那份文件名）。"图片文件不在快照里"这句话在副标题、确认框、
结果 toast 各出现一次。纯函数照 `integrity.js` 的先例放 `src/utils/snapshots.js` 以便直接断言。

**顺带修掉一处真静默失败**：`useBulkActions` 的 toast 写死 `'批量操作完成'`，而后端在快照失败时把降级
写在响应的 `message` 里 —— 也就是说 AGENTS 第 3 节点名要防的那句话**从来没有到达用户眼前**。
现在 delete 且 `snapshot` 为空走 warning toast 并原文渲染；批量删除的确认框从"删除后不可恢复"
（半句假话：数据是能整库回滚的）改成"数据可整库回滚，配图文件会一并删除且回滚找不回来"（后半句才是真的）。

**测试**：后端 **251**（+11 `test_snapshots.py`，整份文件都在钉"该拒绝的时候必须拒绝，且拒绝时一个字
都不改"）；Vitest **129**（+11 `snapshotsView.test.js`）；E2E **51**（+4 `snapshots.spec.js`，
render-smoke 多一条 `/snapshots`）。覆盖率按 CI 口径约 **73%**。
单测里两个结构性坑（都写进注释）：`ConfirmHost` 的弹窗 **teleport 到 body**，`wrapper.find` 摸不到，
得用 `defineComponent({render: () => [h(View), h(ConfirmHost)]})` 一起挂再查 `document`；
弹窗按钮文案必须与列表行按钮**不同名**（都叫"回滚到这一份"时按文案找按钮会点错那颗）。
E2E 只补单测结构上看不见的两段：`@keyup.enter` 提交与 `Esc` 取消（`trigger('click')` 永远抓不到
"回车把整库覆盖了"），两条都同时断言"该发时恰好一次、不该发时一次都没有"。

**明确没做**：单题删除 `DELETE /api/mistakes/{id}` 仍然**不打快照**（与批量删除不对称）。它的确认框
现在写的"删除后不可恢复"因此还是准确的；要不要给单题删除也留反悔点，等一次真实误删再定，
这一批不动它以免把"每次删除都多一份快照"变成默认成本。

**补交（同一批的漏网）**：`/snapshots` 的路由名漏登记进 `NAV_ORDER`，
后果不是报错而是**换页方向永远算成"往前翻"**（`navIndexOf()` 对未知名字返回数组长度，两页都是
最大编号）。而这条链子上一批已经翻过一次同型事故——第一版 `NAV_ORDER` 写的是 `home / mistakes /
papers` 这类根本不存在的路由名，注释里留着教训，却没有一道断言把"表里的名字必须真的存在"钉住。
这次补上：登记 `data-snapshots`，并加 `tests/routerOrder.test.js`（4 条，双向：表里没有假名字、
每个有名字的页面都在表里、名字不重复、维护页排在日常页之后、未知名字仍排最后）。Vitest 129 -> **133**。
另外 push 连红三轮的根因记进 AGENTS 第 3 节：本机 git 装在 `~\.qoder-cn\bin\git\` 下，找不到自己的
system config，`~\.gitconfig` 里只剩 `credential.helperselector.selected=manager` 而没有
`credential.helper=manager`，等于凭据 helper 从没被注册；**不改全局配置**，push 时内联
`-c credential.helper=manager` 就通（`32aa8c5..755389d`）。

## 2026-09-20 · C 盘腾挪 + 每日清理脚本加固（顺带修好 Agent 的 Bash 工具，`755389d`）

**清理脚本在偷偷吃有用的东西**，这是本次最值钱的一条：`D:\dsh-home\scripts\daily-cleanup.ps1`
按"目录 mtime 超期就整棵删"来清 `D:\temp`，而 **npm/pip 这类缓存的 mtime 会被读操作刷新**，
于是 `D:\temp\npm-cache` 三次被删（09-10 / 09-14 / 09-19），`D:\temp\km-art` 被删过一次，
`D:\temp\km-redesign`（视觉基准原型，AGENTS 第 6.5 节点名要留的）09-09 就没了、只剩 zip 里那份。
- 现在：`$protect` 名单（npm-cache / km-v2-backup / km-art / playwright-browsers + 仓库外
  `D:\temp\.cleanup-protect` 里的每一行）只**按文件新旧修剪内容**、不整目录删；
  `$noTrim` 名单（km-v2-backup / km-art）完全不动。
- `km-art` 那批 html/svg 已倒进 `D:\caches\archive-20260920-km-art\`（78 个文件，原件还在原地）。
- 系统 `%TEMP%`（在 C 盘）改成**递归按文件龄期清 + 事后收空目录**，脚本本体换成纯 ASCII
  （PowerShell 5.1 按 GBK 读 .ps1，注释里的中文会把下一行吃掉）。
- 实测一次跑完回收 **851.4 MB**，日志 `D:\temp\daily-cleanup.log`。

**C 盘现状**：还剩约 1.8 GB 空闲。大头是 `~\.cache\codex-runtimes`（约 1.3 GB，Agent CLI 自身运行时）、
`~\.cargo`（约 600 MB，动它要改 PATH）、系统 `%TEMP%` 里被占用的一部分。这三处按 AGENTS 的约定
属于"迁移有风险，动前先问"，本批只报告不动手。

**Agent 的 Bash 工具是怎么坏的**：`C:\Users\Administrator\.qoder-cn\bin\git.staging` 残留了一个
解压到一半的 Git（`ENOTEMPTY`），导致每次 Bash 调用都失败。用 node-repl 把 `git.staging` 改名成 `git`
补全安装后恢复。另外这个 shell 是 **Cygwin bash**：`/c/...` 不挂载（要用 `/cygdrive/c/...`），
且每次调用末尾都会因写 cwd 文件失败而**多报一个假的 Exit code 1** —— 所以本仓库的验证命令一律
以 `MARKER_*_DONE` 标记 + 输出文本为准，不看退出码。

## 2026-09-21 · 英语链路降本提速批（机械步骤关推理，`thinking=False`）

**用户诉求**：英语仍会超时（前端 `timeout of 300000ms exceeded`），又慢又贵，问能否**在输出质量不变的前提下**降本提速。

**先测，不猜**。读 `/api/health` 的 AI 遥测拿到事实：**9 次调用 5 次失败（56%）**、
`avg_ms 45750.7`、`max_ms 187506.3`、`reasoning_avg 2442`、**`truncated 0`**、
最后错误全是 `The read operation timed out`。→ 不是预算被吃，是**单次调用太慢**。

**受控实验逐个排除候选方案**：
1. **换模型？否。** `/v1/models` 只有 `deepseek-flash` 与 `deepseek-v4-pro`；实测同一张图
   用 `v4-pro` 返回"当前图片显示为 Unsupported Image"（输入 token 只有 107 = **图根本没进去**），
   `v4-pro` **不支持视觉**。识图必须留在 `deepseek-flash`。
2. **关推理？可以，且该端点支持。** 逐个试参数：`reasoning_effort=none` 与
   `thinking={"type":"disabled"}` **都真的生效**（推理 token 归零、输出 188→19）；
   而 `enable_thinking=false` / `chat_template_kwargs` / `temperature` **被静默忽略**
   （推理 token 不变）。**必须看输出内容**才能判断是不是"静默降质"——两组完整输出打印出来对比，
   **内容一字不差**（第②组理由措辞略异，结论与解释都正确）。
3. **上下文缓存**：同一前缀连发三次，第 2、3 次命中 **128 token（32%）** —— 缓存机制可用，
   但遥测里一直是 0；留作后续（把稳定内容前置到 system、可变内容放 user）。

**改动**（只动机械步骤，分析步骤保持开推理）：
- `ai_service._chat_request` 新增 `thinking: bool = True`：为假时下发
  `thinking: {"type": "disabled"}`，并**同时取消 1.5 倍推理余量**
  （没有推理却放大 `max_tokens` 等于按更大的上限定预算，而且以前推理吃掉一半、
  正文反而更少）。`_chat` 透传，`_chat_json` 走 `**kwargs` 自动跟随。
- `ai_english` 三处 `thinking=False`：**识图提字**（原样转录）、**题目清单**（指令本身就是
  "照抄、禁止改写"）、**词汇短语抽提**（按 schema 抽取）。阅读解析与逐题解析**保持开推理**。

**实测（真实函数 A/B）**：
- 识图：`14.3s / 推理 3167 / 输出 3297 / 正文 210 字` → `0.9s / 推理 0 / 输出 131 / 正文 229 字`
  （**快 16 倍、输出 token 省 25 倍，转录字数还更多** —— 以前推理吃掉约 12000 预算）。
- 完整英语精读（原文 729 字 + 2 题）：`104.8s` → `38.8s`（**快 2.7 倍**），
  其中词汇那一步 `83.3s` → `6.0s`（**快 14 倍**）。
  那 83 秒的日志原话是：`AI 输出被截断（finish_reason=length，推理 11514 tokens，预算 12000）→ 翻倍重试`
  —— **11514 个推理 token 吃光预算、正文零字**，所以关推理不只是提速，是修掉一个真实故障。
- 产出完整性（用正确键名 `passage_text/english_*`）：729 字原文 / 245 字译文 /
  **8 句**拆解（含 structure+pattern）/ **12 条**短语 / **18 条**生词 / 2 题解析 —— **内容不减**。

**测试**：`tests/test_ai_multi_image.py` 的假 `_chat` 补 `thinking` 形参（接口合法变更）；
`tests/test_ai_reasoning_budget.py` 新增 `MechanicalThinkingOffTest` 3 条断言钉住优化
（必须真的下发 `disabled`、**不许**再乘余量、默认路径行为不变）。后端 **254** 全绿（251+3）、
ruff check/format 干净。

**踩坑（自查记下）**：第一版端到端测量**读错了键名**（读 `sentences` 而实际是 `english_sentences`），
差点把"产出为空"当成我改动导致的回归上报。**看产出前先确认键名**（`normalize_english_parsed`
输出的是 `passage_text / english_sentences / english_phrases / english_words / english_questions`）。

**明确没做**：逐题解析（`_qa_task`）**保持开推理** —— 它要写「定位/来源/思路/总结」，属于分析任务，
A/B 已验证的收益只覆盖机械步骤；要不要把这步也关掉，等一次能对比解析质量的实测再定。

## 2026-09-21 · 追做三件（逐题解析关推理被否 / 缓存可见性 / 2014 T3 词汇入本）

**① 逐题解析关推理 —— 实测后否决，不改。**
先做质量 A/B（同一题、同一 prompt，只切 `thinking`）：
| | 开推理 | 关推理 |
|---|---|---|
| 耗时 | 21.7s | **2.5s** |
| 解析长度 | **730 字** | 443 字 |
| 四段结构 / 定位段 / 答案 / 选项覆盖 | 4/4 · 第一段 · B · 4/4 | 4/4 · 第一段 · B · 4/4 |

**光看这张表会误判成"关了也行"**。打印全文才发现关推理那版**在【定位】里引用了一句原文里根本不存在的话**
（"Today, because of technological change, the economic downturn has highlighted the threat of machines
to human jobs."），【思路】的排除理由也建立在这句编造的原文上。
**编造原文引用比"变短"严重得多** —— 学生会以为原文里有那句。
所以判据不能是"结构齐不齐、答案对不对"。该项**不做**，并写进 AGENTS 第 5 节"不要再试"。

**② 前缀缓存：不是没生效，是**没有口径能看见它**。**
实测应用真实流程（6 次调用，同一篇 + 3 题）：
```
#  耗时     输入  命中  命中率  推理   步骤
1  24.3s   340   128   38%   4560  阅读解析[开推理]
2   1.1s   456   128   28%      0  题目清单[关推理]
3   4.7s   320   128   40%      0  词汇抽提[关推理]
4   6.8s   553   256   46%    394  逐题1
5   7.5s   566   384   68%    567  逐题2
6  20.4s   577   384   67%   3663  逐题3
合计输入 2812 token，命中 1408（50%）
```
逐题命中量**递增**（128→256→384）—— 共享的 system prompt 正在被缓存并累积。
**结论：当前"静态 system + 可变 user"的结构本来就是缓存友好的，不需要改造。**
我此前说"遥测里一直是 0"是**误判**：那个 0 来自我自己拼的原始 API 测试，不是应用遥测。
改动只有一件——**把这件事变成可观测**：`metrics.record_ai` 新增
`prompt_tokens` / `cache_hit_tokens`，`snapshot` 输出 `prompt_avg` / `cache_hit_avg` /
`cache_hit_pct`，链路从 `_chat_request` 的 meta 贯通；新增 `CacheHitMetricsTest` 3 条钉住口径
（累加、零输入不除零、缺 usage 字段不炸也不误算命中）。

**顺带量到真正的成本结构**：同一轮里输入共 2812 token，而**两步分析调用就产出
4560 + 3663 = 8223 个推理 token** —— **成本大头是输出（推理），不是输入**。
所以"缓存"这条杠杆的上限有限；想再省只能动分析步骤的推理，而①已经证明那会伤质量。

**③ 2014 T3 的词汇入本（用户指出"没添加到生词本"）。**
查清原因：`EnglishAnalysisPanel.saveAll()` 只导入**用户勾选过的**词汇
（`selected = ref([])` 默认空选），而我是**直接走 API 建的记录 #185**，绕过了这一步 —— 流程差异，不是 bug。
用 `/api/vocab/import-english` 补录 56 条（37 词 + 19 短语）：**新建 49 / 已存在 7 / 过滤拒绝 0**。
生词本总量 568 → 869（含用户期间自己录入的）。
**遗留待用户定**：这批里 `concept` / `argument` / `practice` / `replace` / `recovery` 属四六级级词，
按现有停用表不算"简单词"但观感偏基础 —— 要不要收紧，等用户给具体判断。


## 2026-09-22 · 全栈体检第 8 批：确凿问题打包（非真题版，`5a2eaa8`）

**为什么是这批**：全库巡检（前后端两路并行）产出 22 条清单；用户拍板"避开真题（晚上再做）"，
于是抽走真题相关的 5 条（error 重试 / N+1 / 图示孤儿 / 一键转错题 / 答案人工修正），留下 7 条
全是"确凿、小而真"的问题一次打包。另有一条巡检误报被 AGENTS 记录在案后**放弃修复**：
"StatsView/SubjectView 缺 UiLoadError"其实是第 6.5 节写明**故意不接**的两处，不能当缺陷修。

**1. A1 图片路径口令缺口（本批最重）**：token 只挂在 12 组 /api 路由上，`/images` 静态挂载与
缩略图端点匿名可访问——巡检还顺手揭出一个更大的事实：**前端压根没实现带 token**，设了
API_TOKEN 整个 SPA 全 401，图片缺口只是"token 模式半成品"的一个症状。修复分三层：
① `security.py` 的 token 来源从"两种 header"扩到四种（+ cookie `km_token` / query `?api_token=`，
`<img>` 标签发不了自定义头，这两条是必须不是可选）；② `/images` 守门用 HTTP 中间件
（`images_token_guard`，StaticFiles mount 挂不了 router 依赖，缩略图端点路径同以 /images 开头
一处判断全覆盖）；③ 前端 axios 请求拦截器自动带头 + `main.js` boot 时把 localStorage 的
`km-api-token` 同步写进 cookie。未设 token 时全部放行，单机零配置行为不变。
测试用"401 拦下 vs 404 放行到处理器"来证放行，不碰真实图片目录。

**2. A6 键盘可达（含一次巡检自我纠错）**：四基件里 **UiSelect/UiDropdown 真缺**（Esc 关、
方向键进菜单移动焦点、UiSelect 的 Delete/Backspace 清空——清空按钮嵌在 trigger 按钮内部，
嵌套 button 不合法，键盘此前没有任何清空路径）；**UiCheckbox/UiPagination 是误报**
（原生 input/button 本就可达），如实记录不画蛇添足。ReviewView 模考图示补 role/tabindex/
Enter/Space。单测两个环境坑写进了 AGENTS：happy-dom 里 detached 元素 `.focus()` 不动
`activeElement`（必须 `attachTo: document.body`）；`v-if` 弹层要 `await nextTick()` 才查得到。

**3. 其余四件小的**：`/api/ai/sense` 补挂 `ai_rate_limit`（曾是唯一漏挂的 AI 端点，用路由
依赖内省钉住）；`DELETE /api/mocks/{id}`（模考成绩记错此前永远挂在趋势图上）；删知识点连带
清其他词条 `related_tags` 里的悬空引用（不清的后果在"练这些题"的兜底路径上：拿不存在的
知识点名查标签永远空手而归）；图片上传内容校验——**扩展名以文件头嗅探为准而不是请求声称的
mime**（裸 base64 一律按 .png 收等于把任意文件当图片存，删除链路还会照着文件名删文件），
Pillow 存在时再加解码级校验，CI 无 Pillow 按有无分开断言。

**4. 连带修掉两处旧账**：PapersView 扫描空结果 toast 的 `${''}` 空插值残留；
`test_export_import_round_trip` 的夹具假图（"hello" 的 base64）在新校验下现形，换成真 1x1 PNG——
夹具造假被真实校验抓出来，正是这批要的效果。

**测试**：后端 257 -> **272**（+15：security_images 6 / 图片校验 4 / knowledge 清引用 2 /
mocks 2 / sense 限流 1）；前端 Vitest 133 -> **138**（+5 `uiSelectKeyboard.test.js`）；E2E 51 不变。
覆盖率按 CI 口径约 73%。

**明确没做**：真题相关 5 条（等晚上）；图片校验没做体积-分辨率双上限（8MB 尺寸门已有）；
cookie 方案没有做成登录页（单用户场景 localStorage 手配，文档已写明）。

## 2026-09-22 · CI 连红排查与修复（5a2eaa8 之后）

**现象**：GitHub CI 连续多批全红（最近 6 次无一绿），用户问"CI 老出问题"。

**三个失败点，全是历史遗留，第 8 批只是把它们撞了出来**：
1. `backend-tests`：`main.py::image_thumbnail` 把 `from PIL import Image` 写在函数最顶部
   （404 判断之前），CI 没有 Pillow → `ModuleNotFoundError` 未处理异常，本该 404/回退
   原图的请求全变 500，第 8 批新加的 `test_header_accepted`（断言 404）当场撞上。
2. `frontend-v3-build`：`scripts/verify_requirements.py` 检查"稳定 tag 在位"，那个 tag
   从未打过——这个脚本守的是 2026-09-17 之后就没再动过的旧原型 frontend-v3。
3. `frontend-v3-e2e`：journey.spec 还在找旧导航项"成册"，用例与页面早已脱节。

**修复**：
- 缩略图端点把 PIL 导入挪进"文件存在且没生成过缩略图"的分支内并 try 包住，
  Pillow 缺失与解码失败同样走"回退原图"（docstring 本来就是这么承诺的，实现没做到）。
- 新增 `ThumbWithoutPillowTest`（2 颗）：用 `sys.modules['PIL']=None` 模拟无 Pillow
  环境，断言不存在→404、存在→200 回退原图字节。后端 272 → **274**。
- `ci.yml` 删掉 `frontend-v3-build` / `frontend-v3-e2e` 两个 job（目录保留不动）：
  废弃原型的门禁连续报红没有维护价值，需要时按 git 历史可恢复。

**验证**：后端 274 全绿 + ruff 双查通过；v3 两个作业移除后 CI 剩 backend-tests /
frontend-test-build / frontend-e2e 三个作业，与本地三门对齐。

## 2026-09-22 · 删除废弃原型 frontend-v3（用户拍板）

**决定**：v3 沉浸式前端自 2026-09-17 起停止演进，现行系统与生产 dist 全在 frontend/，
按用户要求把 v3 从仓库与磁盘整体删除（git 历史仍在，需要时可整体恢复）。

**删除清单**：
- `frontend-v3/` 整目录（源码 + node_modules + dist + test-results）
- v3 专用脚本：`verify_requirements.py` / `check_bundle_budget.py` / `check_page_motion.py` /
  `audit_a11y.py` / `audit_pages.py` / `strip_chars.py`（默认只扫 v3）/ `serve_frontend.ps1`（v2/v3 切换器）
- v3 文档：`docs/v3-acceptance.md` / `docs/v3-handoff.md` / `docs/v3-resume-brief.md`

**挂钩清理**：pre-commit 摘掉 frontend-v3-lint 与 page-motion-wiring 两个钩子；
`frontend_lint.mjs` 去掉 --dir（只剩 frontend）；`preflight_check.py` EMOJI_SCOPES 去掉 v3；
`.gitignore` 4 行、`backend/.env.example` 注释、`backend/app/config.py` FRONTEND_DIST 注释、
`ci.yml` 注释同步更新。WORKLOG 历史叙事不动。

**验证**：后端 274 全绿 + ruff 双查；frontend_lint / preflight 钩子跑通；`npm run build` 通过；
全仓 grep frontend-v3 只剩 WORKLOG（历史）与 ci.yml 注释（删除说明）。

## 2026-09-22 · 真题专项 6 项 + 冲刺计划页 + 生词深挖（一/三档批次）

**背景**：低价时段开工，用户拍板「一三挡开始，第四档不做手机相关，第二档不需要做」。

### 真题专项（papers，6 项全落地）
1. **导入前亮账单**：`GET /api/papers/estimate`——本地探针（pypdf 页数 + 文本层字符）估算
   页数/拆分段数/AI 调用次数/耗时，`high_risk` 标记扫描卷；前端 `importPaper` 先取账单再确认，
   高危卷确认按钮变红「我知道了，仍要导入」，mixed 角色推荐同目录纯试题册。全程零 AI 调用。
2. **AI 拆题断点续跑**：进度存 `app_meta`（key=`paper_resume_<id>`，JSON），每段成功即存、
   全卷完成即清；重导同卷时 `_apply_checkpoint` 校验段数一致才续跑（不一致丢弃重来）；
   扫描/非扫描两条分块循环合并成一条，续跑文案进 status_note。
3. **error 状态卷可重试**：`POST /papers/{id}/retry`（仅 error 可重试，置回 pending + 入队）；
   前端 error 卡片加「重试导入」按钮。
4. **答案人工修正**：`PATCH /papers/{id}/questions/{qid}`——choice 只收 A-D 或空、fill 原文
   （不放大写，`x=1` ≠ `X=1`）、solution 拒绝（无标准答案字段）；前端答案徽章变可点按钮 +
   未配答案的选择题给「补答案」入口。
5. **单题转入错题本**：`POST /papers/{id}/questions/{qid}/to-mistake`——科目按关键词匹配
   subjects（匹配不到拒绝并提示先建科目）、无答案的选择题拒绝（先补答案）、同卷同题干幂等
   （返回已有错题）；前端逐题「转入错题本」按钮。
6. **删卷清孤儿图 + N+1**：`delete_paper` 连带 `remove_paper_images`（`data/images/exam_papers/<pid>/`）；
   papers 列表 answered_count 从逐行子查询改成单条 GROUP BY。

### 冲刺计划页（`/sprint`，不进 Dock，Ctrl+K 可达）
- 后端 `sprint_service.get_sprint_plan` + `GET /api/sprint/plan`：按 `EXAM_DATE` 倒推
  `daily_target = ceil((到期+从未复习)/剩余天数)`，科目聚合（到期/新题/掌握度）与按周分桶
  （每天目标 × 当周天数）；口径与今日复习队列**完全一致**，数字要能和复习页对上。
  `EXAM_DATE` 非法/已考只回三态标志，前端降级说明不瞎算。
- 前端 `SprintView.vue`：倒计时 hero（≤7 天金 / ≤30 朱砂 / 常态青）+ 4 块 MetricTile +
  科目墨条（BarRow）+ 按周里程碑 + 「去复习」直达；路由/NAV_ORDER/TITLE_MAP/命令面板四件注册齐。

### 生词深挖（零 AI）
- **闪卡 TTS**：`utils/speech.js`（浏览器 speechSynthesis，en-US，rate 0.9）；闪卡正面
  喇叭按钮 `@click.stop` 防误翻面；不支持的浏览器 toast 提示。
- **真题语境回链**：`GET /api/vocab/{id}/context`——错题 `passage_text` LIKE 粗筛
  （复用全站 `like_pattern` + `ESCAPE '\'` 口径）后 `\b` 词边界正则精选（art 不命中 start），
  最多 3 条 `{mistake_id, source_name, source_year, snippet}`；闪卡背面翻面即取（会话内按词缓存、
  答完即清），点条目直通 `/review?mode=curve&count=1&mistake_id=X` 单题直练（与知识点「练这题」同落点）。

**测试**：新增后端 3 个文件（estimate 9 / retry+checkpoint 9 / question-ops 10 / sprint 7 /
context 6——共 41 颗，全库 315）、前端 speech.test.js 3 颗（全库 141）、E2E 渲染烟测补
`/sprint`（53）+ fixtures 补 `/api/sprint/plan` 与 `/api/vocab/{id}/context` 打桩。
全部门禁：后端 315 全绿 + ruff 双查；Vitest 141 + build；E2E 53；ESLint/Prettier 干净。

**CI 插曲**：首批提交（284ec1b）backend-tests 红在 `test_rejects_absolute_path`——
Windows 上 `Path("C:/x/y.pdf").is_absolute()` 是 True，Linux 上是 **False**，盘符路径
在 CI 里被当成相对路径放行（探针探不到文件回 200 账单而非 400）。修复：`_resolve_inside`
对盘符路径改用正则 `^[A-Za-z]:[\/]` 单独拒绝（盘符路径在任何主机上都不该当相对路径），
UNC `\\` 开头一并挡；b2683f5 全绿。教训入档：**路径校验别只依赖 is_absolute 的主机语义**。

## 2026-09-23 · 搁置清单 5 项 + 热力图修复 + 直接看答案（用户一次性全批）

**背景**：用户对上次列的零散清单拍板「都可以做」，另提两条：复习热力图有很大问题（截图）；
复习页要能「直接看答案」——不想算就先看答案，有思路选对、没思路选错。

### 热力图修复（#17）
`v-reveal` 的显现类只加不摘，`will-change:transform` 常驻在热力图格子上：一格一层常驻 GPU
合成层，119 格让整条面板变灰、动画把格子打散。修法：显现完成（`reveal-in` 且动画结束）后
摘掉 `reveal-pending` 并关合成层；`Heatmap.vue` 的入场动画同理收进令牌时长，动画完即关。

### 直接看答案（#18）
复习页四题型通用「直接看答案」按钮：选择/填空展示正确答案与解析（本次作答按未答处理，自评
对错照常走 `POST /review`）；翻译展示参考译文对照；解答直接看 AI 解析。不判分、不计入今日
正确率徽章，只有真正提交自评才写 `review_records`——口径与"翻译自评"一致。

### 搁置清单 5 项（#19–#23 全落地）
1. **收藏标星**：`mistakes.starred` 列（DDL + 迁移 additions，门控不动）+ `POST /mistakes/{id}/star`
   （body 空则取反）+ 列表 `starred=true` 筛选 + 卡片星标/详情收藏键/筛选 chip。只影响展示，
   不进复习调度。
2. **打印背诵稿**：`/print?type=mistakes|knowledge|formula&ids=`（上限 100）——题干+选项在前、
   答案/解析/思路在后，A4 打印样式（工具条 `@media print` 隐藏）。三处入口：错题勾选批量、
   知识点/公式工具条「打印本页」。
3. **每日配额调节**：`GET|PUT /api/reviews/quota`，覆盖值存 `app_meta`（key=`review_daily_limit`），
   优先于 `.env`，`0`=不限；复习页积压 chip 变成可点按钮弹窗调节，改完即时重载队列；
   **冲刺计划页的 daily_target 同源**（`sprint_service` 改用 `review_service.get_daily_limit`）。
4. **复习日历**：统计页热力图面板可切「日历」——按月网格看每天完成（accent）/到期（金）/
   未来 90 天预报（金点），周一开头，翻页边界 11 个月前 ~ 2 个月后；组件按需异步加载
   （`defineAsyncComponent`，E2E 冷编译不加压）。
5. **Snooze 稍后再看**：`GET|POST /api/reviews/snooze`——当前题推到明天（`next_review_at`
   = UTC 明天同时刻），**不写复习记录、不动 mastery/SM-2**；每天 3 次（`app_meta`
   `snooze_count_<本地日>`，自动清旧键），超限 400；复习页头部按钮带剩余次数。

**E2E 命令面板假红排查（半天，教训入 AGENTS）**：command-palette 在 workers=2 下稳定红在
`toBeFocused` not found。三段取证：① 页面侧 keydown 记录器 —— 按键**确实到达** window；
② dispatch 后查 `defaultPrevented` —— 失败时 CommandPalette 的 handler **没跑**（post:false）；
③ 包一层 addEventListener 记注册时机 —— 排除"被 stopImmediatePropagation 吃掉"。
真因：`body.ready` 由 BootCalibration 独立加上，而 AppLayout 是懒加载路由 chunk —— 并发跑时
ready 先于外壳出现，Ctrl+K 落在还没挂监听的页面上被整个丢掉。修法：按键前先等
`.dock` 可见（= AppLayout 已挂载 = 监听一定在）。修后 workers=2 连跑 8 次全绿 + 全量 53 绿。

**测试**：新增后端 8 颗（star 3 / quota 3 / snooze 2，全库 323）、E2E fixtures 补
snooze/quota/star 三条打桩；全部门禁：后端 323 全绿 + ruff 双查；Vitest 141 + ESLint +
Prettier + build；E2E 53。**需重启后端生效**（新增 star/quota/snooze 三组端点）。

## 2026-09-25 批次：英语录入三件（完形填空 + 七选五 + 点词增强）

用户反馈三个痛点：完形/七选五录入质量没有阅读理解高、原文里 AI 没提取到的词没法手动加
生词本、点词查义每次都调 AI 又慢又花钱。三件全走「提示词/缓存」路径，零新增 AI 调用。

### #24 完形填空高质量录入（提示词改造）
`ai_english` 捕获提示词与 `_parse_english_questions_prompt` 写明拆题规则：**每个空一道题**，
题干 = 该空所在完整句子（保留编号如 (41)，空位写 `____`），四个选项**原样照抄**，
解析仍是【定位/来源/思路/总结】四段。不增调用、不加表。

### #25 七选五支持（A-G 全链）
- **DB**：`mistakes` 加 `option_e/f/g TEXT`（TABLES_DDL + 迁移 additions 字典，
  与 `starred` 同模式，`migration_version` 门控不动）。真题库 `exam_questions` 仍 A-D。
- **判分**：`answer_service.MULTI_LETTERS_RE` → `[A-Ga-g]`（去重排序整体相等的口径不变）；
  `normalize_parsed` 选项键扩到 a-g、choice 答案钳制 `[ABCD]`→`[A-G]`；
  `mistake_service` 校验放行 A-G、插入/更新走 `MISTAKE_COLUMNS` 自动带新列。
- **前端**：`examScoring.js` 过滤到 A-G；ChoiceAnswer / DetailMeta / PrintView / 面板多题列表
  / 模考卷面一律 **A-D 恒渲染、E-G 非空才出现**（阅读题零回归）；复习页 `KEY_TO_OPTION`
  加 5-7/e/f/g，并加「选项存在才响应按键」守卫（顺带修掉按不存在选项的键会静默选中的老问题）；
  MistakeForm 的 E/F/G 输入与答案字母按钮只在题带 E-G（或手动展开）时出现——
  手动表单平时不变，编辑七选五时不会被全量 PUT 清掉 E-G。
- **提示词**：标准/英语两套提示词的 correct_answer 放宽到单个字母 A-G，
  七选五规则（A-G 整句选项填 option_a~g、题干含上下文句）写进两处。
- 共享判分用例表两侧各补 5 条 E/F/G 用例（TestScoringSingleSource + examScoring.test.js）。

### #26 点词加生词本 + 查义缓存
- **加入生词本**：查义弹窗 footer 加按钮（复用 `importVocabItems`）——AI 没提取到的词也能加，
  查义失败时释义留空照常入库（进生词本后可补）；readonly 错题详情里同样可用。
- **`/api/ai/sense` 服务端缓存**：按词存 `app_meta`（key=`sense_<小写词>`，命中忽略大小写、
  响应带 `cached:true`）；TTL 90 天 + 500 条上限双清理（写入时淘汰过期与最旧）；
  **查不到释义的不缓存**。同一个词第二次点击零 AI 调用、即时返回。

**测试**：新增后端 4 颗（normalize E-G / 缓存命中忽略大小写 / 空释义不缓存 / 500 条上限淘汰，
全库 327）；examScoring 双侧用例表补 E-G。全部门禁：后端 327 全绿 + ruff 双查；
Vitest 141 + ESLint + Prettier + build；E2E 53。**需重启后端生效**（迁移加列 + 缓存）。

## 2026-09-26 点词两处修复（用户实测反馈）

用户在错题详情（readonly 精读面板）发现两个问题：

### ① 点词弹窗「加入生词本」后原词不变红
`addLookupWord` 只入库、不动本地状态，`isExtracted` 只看 AI 提取的 `english_words`。
现在加 `addedWords` 本地集合（reactive Set）：点词弹窗或勾选清单加入成功后立即登记，
`isExtracted` 一并检查，原词立刻套红色高亮，不用刷新页面。

### ② 短语不能整体点，只能一个词一个词点
`tokenize` 原来只按单词切分。现在由 `english_phrases` 生成 `tokenRe` 正则
（长短语优先、词间 `\s+`、前后字母边界 lookaround），短语在原文/句子拆解里
**整体成一个可点 token** 且直接高亮；点击弹窗直接用已提取释义（`lookupKind='phrase'`），
**不调 `/ai/sense`**（那是单词接口）；「加入生词本」按 kind=phrase 入库。

**测试**：新增 `tests/englishPanelWords.test.js` 3 颗（短语整体成 token + 高亮、
加词后立刻变红、点短语零 AI 调用且 kind=phrase），Vitest 141→144。
ESLint 抓到一次改名残留（`/ai/sense` 还用旧参数名 `word`），已修。
门禁全绿：ESLint + Prettier + Vitest 144 + build + E2E 53。纯前端改动，无需重启后端。

## 2026-09-26 人工录入 2014 英语二完形（零 AI）+ PUT 部分更新踩坑

用户智能录入 2014 英语二完形超时（`/api/health` 账本：deepseek-flash 30 调 4 错，
最后错误 = `AI 连接中断：The read operation timed out`——网络层断连，非流程 bug），
且明确要求不再花 AI 余额。改走**人工录入**：我直接读原图转录全文 + 20 空题干/选项 +
答案键（BACADACCDBABCDBDADCB），自写全文翻译（按段落对齐进 `english_sentences`，
对照翻译右栏才有内容），3 张原图（原文/选项/答案键）以 data URL 随错题入库，
`POST /api/mistakes` 一条整篇记录（id 189，english_questions 20 题）。
浏览器实测详情页：对照翻译、点词、20 题与答案全部正常。

**踩坑（已写进 AGENTS 第 3 节）**：PUT /api/mistakes 的"不传就回填"只保护
ATTACHMENT_KEYS；`source_type/source_year/source_name/source/knowledge_tags`
等普通字段不传会**按默认值重置**——一次只为 `english_sentences` 做的部分更新
把真题来源和标签全冲掉了（已补回）。前端表单全量提交所以从没暴露；
脚本/自动化必须 GET 后全量 PUT，或带上全部普通字段。

另补：小题逐条带 `question_type: 'choice'`，详情面板才会渲染 A-D 选项（否则只显示答案字母）。

### 补记：完形精读内容补齐（仍零 AI）
用户反馈人工录入只有题目不够——AI 精读本应有逐句拆解/生词/短语/解析。全部由 Agent 亲自撰写后
PUT 进 id 189：english_sentences 升级为 **26 句逐句拆解**（翻译+句型标签+结构分析）、
**13 条重点短语**（原文里整体可点，直接用已提取释义不调 AI）、**16 个生词**
（音标/词性/释义/例句，原文中变红可点加生词本）、**20 题逐题解析**（【定位】点名原句 +
【思路】排除理由 +【总结】考点）。浏览器实测：632 个词 token、64 处红词、26 条句解、
20 段解析全部渲染正常。生词未自动导入生词本（留给用户点击挑选，符合「词汇保存后只在生词本」约定）。
