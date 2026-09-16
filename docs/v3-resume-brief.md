# v3 工作简报（可独立执行版）

> 给**接手的新会话**：本文件自成一体，读完它 + `docs/v3-handoff.md` 就能继续开发，
> 不需要上一轮对话的任何上下文。上一轮因上下文与余额耗尽主动停手（非技术阻塞）。

## 一、30 秒了解现状

`km-v2` 是考研错题本（单用户、生产在用）。正在**并行构建 v3 沉浸式前端**，
放在 `frontend-v3/`，**v2（`frontend/`）完全不受影响**，随时可切回。

- 隐喻：**夜航星图** —— 未掌握的是暗，已掌握的是光；题=星，亮度=复习遍数，反复错=红移
- 已完成：阶段 0（基建+外壳+启动页）、1（设计系统+动效原语）、2/2b（13 个组件）、3 第一页（今日复习，接真实 API）
- 规模：`frontend-v3/src` 28 文件 / 4419 行；单测 64 个（4 文件）
- 远端 main = 本地 = `922a890`；工作区干净

## 二、接手第一件事（按顺序做）

```bash
cd D:/km-v2

# 1) 确认后端契约未变（v3 复用 v2 后端与同一张库）
python scripts/contract_diff.py --check docs/contract-baseline.json   # 期望：无差异

# 2) 确认 v2 仍健康（并行期间必须）
curl -s http://127.0.0.1:8000/api/health

# 3) 起 v3 开发服务器（端口 5175，与 v2 的 5174 隔开）
cd frontend-v3 && npm run dev        # 后台跑

# 4) 看现状：设计规格页与已完成的复习页
#    http://127.0.0.1:5175/design   （令牌/材质/动效原语/全部组件）
#    http://127.0.0.1:5175/review   （真实数据）
```

**改完组件或视图后必须重启 dev server 再验证**（否则会读到陈旧的模块图 —— 踩过）。

## 三、下一轮做什么（阶段 3 剩余）

按顺序，每页做完即验证 + 提交：

1. **智能录入 · 蘸墨台**（最大的一块，建议单独一轮）
   - 多图暂存：`<input multiple>` 一次选多张（后端支持最多 5 张；v2 只能一张张加）
   - 分析走 `POST /api/ai/english`（英语整篇）或 `/api/ai/ocr`；**实测 165–210 秒**，前端超时须 ≥300s
   - 进度必须用**真实阶段**（阶段日志来自后端流程），不显示假百分比
   - 依据：`docs/contract-baseline.json` 里的 `ai.english` / `ai.ocr` 形状
2. **错题列表与详情**：`GET /api/mistakes`（不传 page 返回数组，传 page 返回分页对象）
3. **知识点库**：`GET /api/knowledge`（服务端分页）+ `GET /api/knowledge/linked-mistakes`

然后是阶段 4（统计/真题/模考/生词/公式/科目/练习/设置）、阶段 5（移动端+可访问性+性能预算）、
阶段 6（切换 + 契约对照 + v2 归档）。

## 四、绝对不要做的事

1. **不要改 `frontend/`（v2）**。它是线上在用版本。曾有清理脚本越界改了 21 个 v2 文件（已全部回退）。
   工具默认范围必须限定在 `frontend-v3/`。
2. **不要改后端 API 与数据库 schema**。v3 只消费现有接口。切换前必须 `contract_diff --check` 通过。
3. **不要删 v2**，直到用户明确验收 v3。
4. **不要用 `body{cursor:none}` 隐藏原生光标**（自定义光标 JS 失效会让用户失去指针）。
5. **不要引入 CDN**（字体/图标/库）。离线必须可用；Lucide 走本地 `lucide-vue-next`。
6. **不要写 emoji 与字符图标**（含注释里的 `→`）。pre-commit 会拦，且规则就是规则。

## 五、可用的质量门禁（每轮结束都要全绿）

```bash
cd frontend-v3
npx vitest run                                  # 期望 64 passed
npx eslint src tests vite.config.js
npx prettier --check "src/**/*.{js,vue,css}" "tests/**/*.js" "vite.config.js"
npm run build                                   # Vue 模板编译错误只有 build 能发现

cd .. && python scripts/preflight_check.py       # 卫生 + 字符图标
pre-commit run --all-files                       # 6 个钩子
```

提交后确认 CI：`gh` 没装，用
`curl -s -H "User-Agent: Mozilla/5.0" "https://api.github.com/repos/MyHeartBea/selfstudy/actions/workflows/334074877/runs?per_page=2&branch=main"`
（**别用 `.../runs?per_page=1`，该接口返回陈旧数据，曾因此误判"CI 没触发"**）。
四个 job 全绿才算通过：backend-tests / frontend-test-build / **frontend-v3-build** / frontend-e2e。

## 六、设计与工程决策（不可回退，改前先问用户）

- **星云用 CSS 不用着色器**：四轮着色器方案都留硬边（`exp(-d)` 圆边 / 只抖中心 / 域扭曲 / 解析梯度雾团），
  最后靠隔离实验定位残留硬边来自大尺度噪声。职责分离：CSS 管柔（`.aurora`），WebGL 管锐（星点 620 颗）。
- **不隐藏原生光标**；**圆角一律 2px**；**不用默认阴影/玻璃拟态**；层次靠亮度差 + 细线。
- **动效六原语**（`src/design/motion.js`）：沉降/红移/描绘/扫描/聚焦/漂移；全部只改 transform/opacity/filter；
  全部有 reduced-motion 降级（瞬时到位、信息不丢）；**所有入口都有 `isElement` 守卫**（缺守卫会抛异常并
  让同一 onMounted 里后续原语全不执行 —— 表现是"元素永不出现"）。
- **组件优先用原生控件**（select/checkbox），只接管视觉：键盘导航与移动端语义浏览器已做对。
- **契约层 `src/core/api/`**：URL 只在这一层出现；统一解包 `{code,data,message}`；失败抛 `ApiError`。
- **掌握度用五档墨点而非百分比**（自评只有三档，不做假精度）；**复习遍数用 SVG 星形而非 Unicode 星号**。

## 七、成本与授权（开工前确认）

- 已用约 ¥20（阶段 0–3 第一页）。剩余阶段 3–6 预估 **¥20–30**。
- **余额长期停在约 ¥1.94**，不足以支撑一轮开发。项目偏好明确要求：
  **预算不足时先充值再开始下一阶段，避免跑到一半中断。**
- **视觉方向尚未由用户确认**：v3 按「夜航星图」（深空 `#05060a` + 氧化橙 `#ff5a3c`）
  推进了三个阶段。阶段 3 剩余页面都基于这套令牌，**越往后改越贵**，建议先确认。

## 八、关键文件索引

| 文件 | 作用 |
|------|------|
| `docs/v3-handoff.md` | v3 权威交接：进度表 / 保护机制 / 隐喻与决策 / **8 条踩坑表** |
| `docs/contract-baseline.json` | 28 个只读端点的响应形状基线 |
| `scripts/contract_diff.py` | 契约对照（切换前后必跑） |
| `scripts/serve_frontend.ps1` | v2/v3 切换与回滚（`-Status` / `-Target v2|v3`） |
| `scripts/check_render.py` | 渲染像素校验（比 `gl.readPixels` 可靠） |
| `scripts/strip_chars.py` | 清除字符图标（**默认只扫 v3**） |
| `scripts/check_workflow.py` | CI YAML 结构校验（GitHub 对非法 workflow 静默拒绝） |
| `frontend-v3/src/design/` | `tokens.css` / `base.css` / `materials.css` / `motion.js` |
| `frontend-v3/src/sky/` | `Starfield.vue`（WebGL 星点）/ `SkyCursor.vue` |
| `frontend-v3/src/app/` | `App.vue` / `AppShell.vue` / `InkLoader.vue` / `router.js` |
| `frontend-v3/src/ui/` | 13 个组件 + `toast.js` / `toast.css` |
| `frontend-v3/src/core/api/index.js` | 契约层（唯一写 URL 的地方） |
