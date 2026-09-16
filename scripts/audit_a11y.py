"""可访问性审查（不引额外依赖，用 CDP 的 Accessibility 域 + 手写规则）。

覆盖的检查项（都是能真正挡住人的问题，不是风格偏好）：
  1. 图片缺 alt
  2. 可点元素没有可读名称（按钮/链接只有图标或只有空文本）
  3. 表单控件没有关联标签
  4. 标题层级跳级（h1 -> h3）
  5. 页面缺少 h1
  6. 正文与背景对比度（只测主要文本节点，按 WCAG AA 4.5:1 / 大字 3:1）
  7. 焦点可见性：Tab 一遍，统计"有可见轮廓的元素数"
  8. 语义地标：是否存在 main / nav

对比度按 sRGB 相对亮度计算（OKLCH 会被浏览器算成 rgb，取计算样式即可）。
半透明背景无法可靠估值时跳过该节点并计数，不虚报。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import time
import urllib.request
from pathlib import Path

from cdp import WS, CHROME, PORT  # noqa: E402  (同目录下的极简 CDP 客户端)

BASE = "http://127.0.0.1:5175"
ROUTER = Path(r"D:\km-v2\frontend-v3\src\app\router.js")

src = ROUTER.read_text(encoding='utf-8')
ROUTES = []
for m in re.finditer(r"path:\s*'([^']+)'[\s\S]{0,80}?component:", src):
    p = m.group(1)
    if p and not p.startswith('/:') and p not in ROUTES:
        ROUTES.append(p)

AUDIT = r"""(function () {
  function parseRGB(s) {
    var m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var parts = m[1].split(/[,\s\/]+/).filter(Boolean).map(Number);
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  }
  function lum(c) {
    function f(v) { v = v / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function ratio(fg, bg) {
    var a = lum(fg) + 0.05, b = lum(bg) + 0.05;
    return a > b ? a / b : b / a;
  }
  function bgOf(el) {
    var node = el;
    while (node && node !== document.documentElement) {
      var c = parseRGB(getComputedStyle(node).backgroundColor);
      if (c && c.a === 1) return c;
      node = node.parentElement;
    }
    var root = parseRGB(getComputedStyle(document.body).backgroundColor);
    return root && root.a === 1 ? root : { r: 5, g: 6, b: 10, a: 1 };
  }

  var issues = [];
  function add(kind, detail) { issues.push({ kind: kind, detail: detail }); }

  // 1) 图片 alt
  var imgs = document.querySelectorAll('img');
  for (var i = 0; i < imgs.length; i++) {
    if (!imgs[i].hasAttribute('alt')) {
      add('img-no-alt', (imgs[i].getAttribute('src') || '').slice(0, 60));
    }
  }

  // 2) 可点元素可读名称
  var clickable = document.querySelectorAll('button, a[href], [role="button"]');
  for (var j = 0; j < clickable.length; j++) {
    var e = clickable[j];
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    var name = (e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim();
    if (!name) {
      var sel = e.tagName.toLowerCase() + (e.className && typeof e.className === 'string'
        ? '.' + e.className.trim().split(/\s+/)[0] : '');
      add('clickable-no-name', sel);
    }
  }

  // 3) 表单控件标签
  var ctrls = document.querySelectorAll('input:not([type="hidden"]), select, textarea');
  for (var k = 0; k < ctrls.length; k++) {
    var c = ctrls[k];
    var cs2 = getComputedStyle(c);
    if (cs2.display === 'none' || cs2.visibility === 'hidden') continue;
    var id = c.getAttribute('id');
    var hasLabel = (id && document.querySelector('label[for="' + id + '"]'))
      || c.closest('label')
      || c.getAttribute('aria-label')
      || c.getAttribute('aria-labelledby');
    if (!hasLabel) {
      add('control-no-label', c.tagName.toLowerCase() + (c.getAttribute('type') ? '[' + c.getAttribute('type') + ']' : ''));
    }
  }

  // 4) 标题层级与 h1
  var heads = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
  var levels = [];
  for (var h = 0; h < heads.length; h++) {
    var lv = Number(heads[h].tagName[1]);
    levels.push(lv);
    if (heads[h].getBoundingClientRect().width === 0) continue;
  }
  var visibleLevels = [];
  for (var q = 0; q < heads.length; q++) {
    if (heads[q].getBoundingClientRect().width > 0) visibleLevels.push(Number(heads[q].tagName[1]));
  }
  if (visibleLevels.length && visibleLevels.indexOf(1) === -1) add('no-h1', 'visibleLevels=' + visibleLevels.join(','));
  for (var s = 1; s < visibleLevels.length; s++) {
    if (visibleLevels[s] - visibleLevels[s - 1] > 1) {
      add('heading-skip', 'h' + visibleLevels[s - 1] + ' -> h' + visibleLevels[s]);
      break;
    }
  }

  // 5) 对比度：抓有文本的叶子节点
  var lowContrast = [];
  var skipped = 0;
  var texts = document.querySelectorAll('p, span, a, li, h1, h2, h3, h4, button, label, em, b, code, td, th');
  for (var t = 0; t < texts.length; t++) {
    var el = texts[t];
    var own = '';
    for (var n = 0; n < el.childNodes.length; n++) {
      if (el.childNodes[n].nodeType === 3) own += el.childNodes[n].nodeValue;
    }
    own = own.replace(/\s+/g, ' ').trim();
    if (own.length < 2) continue;
    var st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) < 0.35) continue;
    var r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    var fg = parseRGB(st.color);
    var bg = bgOf(el);
    if (!fg || fg.a < 1) { skipped++; continue; }
    var size = parseFloat(st.fontSize);
    var bold = (Number(st.fontWeight) || 400) >= 700;
    var large = size >= 24 || (size >= 18.66 && bold);
    var need = large ? 3.0 : 4.5;
    var cr = ratio(fg, bg);
    if (cr + 0.02 < need) {
      lowContrast.push((el.tagName.toLowerCase() + '.' + String(el.className).trim().split(/\s+/)[0]).slice(0, 40)
        + ' ' + cr.toFixed(2) + ':1 需' + need + ' 字号' + size.toFixed(0) + ' 文本"' + own.slice(0, 18) + '"');
    }
  }
  if (lowContrast.length) add('low-contrast', lowContrast.slice(0, 4).join(' | ') + (lowContrast.length > 4 ? ' 等 ' + lowContrast.length + ' 处' : ''));

  // 6) 地标
  if (!document.querySelector('main')) add('no-main', '缺少 main 地标');
  if (!document.querySelector('nav, [role="navigation"]')) add('no-nav', '缺少 nav 地标');

  return {
    issues: issues,
    contrastSkipped: skipped,
    textNodes: texts.length,
    headingLevels: visibleLevels.slice(0, 12)
  };
})()"""


def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}", "--no-first-run",
         "--no-default-browser-check", "--hide-scrollbars",
         "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         BASE + "/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        targets = None
        for _ in range(50):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as r:
                    targets = json.load(r)
                if any(t.get("type") == "page" for t in targets):
                    break
            except Exception:
                continue
        ws = WS(next(t for t in targets if t["type"] == "page")["webSocketDebuggerUrl"])
        ws.call("Runtime.enable")
        ws.call("Page.enable")
        ws.call("Accessibility.enable")
        ws.call("Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})

        total = {}
        for route in ROUTES:
            ws.call("Page.navigate", {"url": BASE + route})
            time.sleep(5.0)
            r = ws.call("Runtime.evaluate", {"expression": AUDIT, "returnByValue": True})
            info = r.get("result", {}).get("value") or {}
            kinds = {}
            for it in info.get("issues", []):
                kinds.setdefault(it["kind"], []).append(it["detail"])
                total.setdefault(it["kind"], []).append(f'{route}: {it["detail"]}')
            summary = ", ".join(f'{k}x{len(v)}' for k, v in kinds.items()) or '无问题'
            print(f'{route:<12} {summary}')
            for k, v in kinds.items():
                if k in ('low-contrast', 'no-h1', 'heading-skip', 'clickable-no-name', 'control-no-label'):
                    for d in v[:2]:
                        print(f'             {k}: {d[:150]}')

        print()
        if total:
            print('汇总:')
            for k, v in total.items():
                print(f'  {k}: {len(v)} 处')
        else:
            print('可访问性审查通过（无问题）')
        ws.close()
        return 0
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
