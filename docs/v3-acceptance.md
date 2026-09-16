# v3 交付与验收（终局快照）

> 这一份是给用户看的**验收凭据**，与 `v3-handoff.md`（开发交接）和
> `v3-resume-brief.md`（接任会话简报）互补：那两份讲"怎么继续做"，这份讲"做成了什么、凭什么说做成了"。
>
> 快照时间：本地＝远端＝`3734715`；工作区干净。

## 一、怎么自己验证（四条命令，全部离线可跑）

```powershell
cd D:\km-v2

# 1) 18 项硬性要求逐条核验（源码特征 + 构建产物 + 真跑 git/预算脚本）
python scripts/verify_requirements.py

# 2) v3 单元测试与构建
cd frontend-v3; npx vitest run; npm run build; cd ..

# 3) v3 真浏览器 E2E（21 用例；本机复用已装 Chrome 免下载）
cd frontend-v3
$env:PW_USE_SYSTEM_CHROME='1'; npx playwright test; Remove-Item Env:\PW_USE_SYSTEM_CHROME
cd ..

# 4) 14 页巡检 + 可访问性（可指向任意基址）
python scripts/audit_pages.py
python scripts/audit_a11y.py
$env:KM_AUDIT_BASE='http://127.0.0.1:8100'; python scripts/audit_pages.py; Remove-Item Env:\KM_AUDIT_BASE
```

## 二、三个地址分别是什么（别混）

| 地址 | 是什么 | 用途 |
|------|--------|------|
| `http://127.0.0.1:8000` | **当前生产**（v2） | 你日常使用 |
| `http://127.0.0.1:8100` | **v3 的生产形态**（真实 dist + 真实后端） | 切换后就是这个样子；现在可用于对比 |
| `http://127.0.0.1:5175` | v3 vite dev（热更新） | 开发 |

## 三、交付内容

**14 个页面**：星表(home) · 学习统计 · 今日复习 · 智能录入 · 错题星表 · 知识点库 ·
生词本 · 公式背诵 · 真题库 · 模考记录 · 科目指南 · 自主练习 · 设置与数据 · 设计规格

**启动页**：静默 → 天文台校准（十字丝 + 24 角刻度 + 双向旋转双环 + 真实进度弧）→ 圆形遮罩揭幕。
实测时序：1.15s 静默 → 1.93s 校准 → 3.75s 揭幕(158vmax) → 4.01s 干净卸载。

**设计系统**：OKLCH 令牌（56 处）· 四条材质 · **六条动效原语**（漂移/沉降/红移/描绘/扫描/聚焦）·
13 个组件 · 活体规格页 `/design`。

## 四、逐条硬性要求 → 证据

见 `python scripts/verify_requirements.py` 的输出（18 项全 OK）。要点：
- 隐喻/排版/OKLCH/动效/WebGL/光标/磁吸/滚动/悬停/图标/零 emoji/零 CDN —— 均由源码客观特征核验
- 可访问性：14 个页面均含 h1、82 处 aria；对比度按 WCAG AA 实算（0 问题）
- reduced-motion：21 处降级规则；E2E 里有一条专门验证"降级后内容不丢"
- 60fps：rAF 20 处、will-change 8 处、动效只改 transform/opacity/filter

## 五、质量门禁（全部在 CI 里）

`backend-tests` · `frontend-test-build` · `frontend-v3-build`（Lint→Test→Build→**Bundle budget**→**Verify requirements**）·
`frontend-v3-e2e`（Playwright，/api 全打桩，**不需要后端**）· `frontend-e2e`

最近一次全绿：**run #79（`67b87a8`）5 个 job 全 success**。

## 六、并行安全（v3 期间 v2 未被触碰）

- v2 源码 `frontend/`：**改动 0 处**
- 稳定 tag：`v2-stable-2026-09-16`；冷备：`D:\temp\km-v2-backup\`
- 后端与数据库：**完全未改**；`contract_diff --check` 28 端点**无差异**（切换前后都会跑）
- 切换入口唯一：`scripts/serve_frontend.ps1 -Target v2|v3`；回滚一条命令

## 七、唯一剩下的动作

把 8000 的 `FRONTEND_DIST` 指到 v3：

```powershell
cd D:\km-v2
powershell -File scripts/serve_frontend.ps1 -Target v3   # 改 .env + 重启后端 + 探活
# 切换后立刻核对
python scripts/contract_diff.py --check docs/contract-baseline.json
$env:KM_AUDIT_BASE='http://127.0.0.1:8000'; python scripts/audit_pages.py; python scripts/audit_a11y.py; Remove-Item Env:\KM_AUDIT_BASE
# 回滚
powershell -File scripts/serve_frontend.ps1 -Target v2
```

**为什么没自动执行**：这会改变用户日常访问的页面（对外行为变更）。
用户的既有偏好是"大改动前先给步骤、确认后再动"，因此等一句确认。

**v2 何时删**：不建议现在删。等 v3 实际用过一段（覆盖"录入"与"复习"两条主流程）再谈归档。
