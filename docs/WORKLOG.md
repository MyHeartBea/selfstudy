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
