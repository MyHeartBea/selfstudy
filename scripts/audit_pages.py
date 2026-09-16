"""全页面巡检（含阶段 4 新增五页）。路由清单从 router.js 里解析，
避免手写清单与代码漂移 —— 新增页面后自动纳入巡检。
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import time
import urllib.request
from pathlib import Path

from cdp import WS, CHROME, PORT  # noqa: E402  (同目录下的极简 CDP 客户端)

# 基址可用环境变量覆盖：切换后指向生产端口即可复用同一套审计
#   KM_AUDIT_BASE=http://127.0.0.1:8000 python scripts/audit_pages.py
BASE = os.environ.get("KM_AUDIT_BASE", "http://127.0.0.1:5175")
ROUTER = Path(r"D:\km-v2\frontend-v3\src\app\router.js")

# 从 router.js 解析出所有具名路由（跳过重定向与 catch-all）
src = ROUTER.read_text(encoding='utf-8')
ROUTES = []
for m in re.finditer(r"path:\s*'([^']+)'[\s\S]{0,80}?component:", src):
    p = m.group(1)
    if p and not p.startswith('/:') and p not in ROUTES:
        ROUTES.append(p)

PROBE = """(function () {
  var main = document.querySelector('main');
  return {
    title: document.title,
    mainFound: !!main,
    children: main ? main.children.length : -1,
    textLen: (document.body.innerText || '').length,
    revealTotal: document.querySelectorAll('.reveal').length,
    revealIn: document.querySelectorAll('.reveal.in').length,
    errs: window.__errs || [],
    overflowX: document.documentElement.scrollWidth > innerWidth + 1,
    overlay: !!document.querySelector('vite-error-overlay')
  };
})()"""


def main():
    print("巡检路由:", ", ".join(ROUTES))
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}", "--no-first-run",
         "--no-default-browser-check", "--hide-scrollbars",
         "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         BASE + ROUTES[0]],
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
        ws.call("Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        ws.call("Page.addScriptToEvaluateOnNewDocument", {
            "source": (
                "window.__errs=[];"
                "window.addEventListener('error',function(e){window.__errs.push('ERR: '+e.message)});"
                "window.addEventListener('unhandledrejection',function(e){"
                "window.__errs.push('REJECT: '+String(e.reason&&e.reason.message||e.reason))});"
            )})

        bad = []
        for route in ROUTES:
            info = {}
            for attempt in range(2):
                ws.call("Page.navigate", {"url": BASE + route})
                time.sleep(5.0 if attempt == 0 else 8.0)
                r = ws.call("Runtime.evaluate", {"expression": PROBE, "returnByValue": True})
                info = r.get("result", {}).get("value") or {}
                if info.get("mainFound") and info.get("children", 0) > 0:
                    break
            ok = (info.get("mainFound") and info.get("children", 0) > 0
                  and info.get("textLen", 0) > 30 and not info.get("errs")
                  and not info.get("overflowX") and not info.get("overlay"))
            print(f"{'OK  ' if ok else 'FAIL'} {route:<12} children={info.get('children')} "
                  f"text={info.get('textLen')} reveal={info.get('revealIn')}/{info.get('revealTotal')} "
                  f"errs={info.get('errs')} overflowX={info.get('overflowX')}")
            if not ok:
                bad.append(route)

        print()
        print("未通过:", ", ".join(bad) if bad else f"全部 {len(ROUTES)} 个页面通过")
        ws.close()
        return 1 if bad else 0
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
