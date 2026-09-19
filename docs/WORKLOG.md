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
