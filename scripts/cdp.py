"""极简 CDP 客户端（Chrome DevTools Protocol over WebSocket）。

来源：本项目审计脚本长期用的临时工具，现固化为仓库资产。
用途：scripts/audit_pages.py 与 scripts/audit_a11y.py 靠它驱动无头 Chrome。
要求：本机装有 Chrome，路径见下方 CHROME 常量（可用环境变量 CHROME_PATH 覆盖）。
"""

"""用无头 Chrome 打开样张，抓全页截图 + 桌面/手机两档 + 控制台报错。

只依赖标准库：手搓 CDP WebSocket 客户端（Playwright/Puppeteer 不可用）。
"""
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request

import os

CHROME = os.environ.get("CHROME_PATH") or os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
PAGE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\km-v2-art-direction.html"
OUT = r"D:\temp\km-art"
os.makedirs(OUT, exist_ok=True)
PORT = 9333

class WS:
    """极简 WebSocket 客户端（文本帧足够，CDP 不用二进制）。"""

    def __init__(self, url):
        _, rest = url.split("://", 1)
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
        self.msg_id = 0

    def _recv(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError("连接关闭")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, payload: str):
        data = payload.encode()
        header = bytearray([0x81])
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def recv(self):
        b1, b2 = self._recv(2)
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._recv(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._recv(8))[0]
        if b2 & 0x80:
            mask = self._recv(4)
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._recv(length)))
        else:
            payload = self._recv(length)
        return payload.decode("utf-8", "replace")

    def call(self, method, params=None, timeout=60):
        self.msg_id += 1
        mid = self.msg_id
        self.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(self.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method} 失败: {msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(method)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def main():
    url = "file:///" + PAGE.replace("\\", "/")
    proc = subprocess.Popen(
        [
            CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
            "--no-first-run", "--no-default-browser-check", "--disable-gpu",
            "--hide-scrollbars", "--allow-file-access-from-files", url,
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        targets = None
        for _ in range(40):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as r:
                    targets = json.load(r)
                if any(t.get("type") == "page" for t in targets):
                    break
            except Exception:
                continue
        page = next(t for t in targets if t["type"] == "page")
        ws = WS(page["webSocketDebuggerUrl"])
        ws.call("Page.enable")
        ws.call("Runtime.enable")
        ws.call("Console.enable")

        report = {"console": [], "errors": []}
        ws.call("Runtime.evaluate", {"expression": "1", "returnByValue": True})

        modes = [
            ("desktop", 1440, 900, False, "light"),
            ("mobile", 390, 844, True, "light"),
            ("desktop-dark", 1440, 900, False, "dark"),
        ]
        for name, w, h, mobile, scheme in modes:
            ws.call("Emulation.setDeviceMetricsOverride",
                    {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": mobile})
            ws.call("Emulation.setEmulatedMedia",
                    {"features": [{"name": "prefers-color-scheme", "value": scheme}]})
            ws.call("Page.reload", {"ignoreCache": True})
            time.sleep(1.6)

            # **关键**：先滚完全页再测量。动画多由 IntersectionObserver 在进入视口时触发；
            # 不滚动就会测到"全 0"的初始态，然后误判样式坏了（这个坑踩过两次）。
            # 注意：`html{scroll-behavior:smooth}` 会让 scrollTo 变成平滑滚动，脚本里的
            # 130ms 间隔根本滚不到位 —— 所以这里先临时关掉平滑，滚完再恢复。
            scrolled = ws.call("Runtime.evaluate", {
                "expression": """(async () => {
                  const html = document.documentElement;
                  const prev = html.style.scrollBehavior;
                  html.style.scrollBehavior = 'auto';
                  const step = Math.round(window.innerHeight * 0.6);
                  let hops = 0, maxY = 0;
                  for (let y = 0; y < document.body.scrollHeight + window.innerHeight; y += step) {
                    window.scrollTo(0, y);
                    await new Promise(r => requestAnimationFrame(() => setTimeout(r, 90)));
                    hops++;
                    maxY = Math.max(maxY, Math.round(window.scrollY));
                  }
                  window.scrollTo(0, 0);
                  await new Promise(r => requestAnimationFrame(() => setTimeout(r, 500)));
                  html.style.scrollBehavior = prev;
                  return { hops, maxY, backTo: Math.round(window.scrollY) };
                })()""",
                "awaitPromise": True,
                "returnByValue": True,
            })
            time.sleep(1.4)
            print(f"[{name}] 滚动诊断: {json.dumps(scrolled.get('result', {}).get('value'))}")

            # 再滚到底并**停在那里**：这样截图反映的是"用户读到深处"的真实状态
            # （深度读数是滚动驱动的，停在顶部只会拍到 0.0）。
            ws.call("Runtime.evaluate", {
                "expression": """(async () => {
                  const html = document.documentElement;
                  const prev = html.style.scrollBehavior;
                  html.style.scrollBehavior = 'auto';
                  window.scrollTo(0, document.body.scrollHeight);
                  await new Promise(r => requestAnimationFrame(() => setTimeout(r, 700)));
                  html.style.scrollBehavior = prev;
                  return Math.round(window.scrollY);
                })()""",
                "awaitPromise": True,
                "returnByValue": True,
            })
            time.sleep(0.8)

            probe = ws.call("Runtime.evaluate", {
                "expression": """(() => {
                  const all = (s) => [...document.querySelectorAll(s)];
                  const box = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().height) : null; };
                  // 通用探针：不假设页面里有某个特定类名，只报告"实际存在什么、尺寸多少"
                  const sections = all('section').map(s => ({
                    id: s.id || null,
                    h: Math.round(s.getBoundingClientRect().height),
                    text: (s.querySelector('h1,h2,.giant')?.textContent || '').trim().slice(0, 22)
                  }));
                  const animated = all('[data-count]').map(e => e.textContent);
                  const empty = all('div,section,svg').filter(e => {
                    const r = e.getBoundingClientRect();
                    return r.height > 80 && r.width > 200 && e.children.length === 0 && !e.textContent.trim();
                  }).length;
                  return {
                    title: document.title,
                    body_h: document.body.scrollHeight,
                    sections,
                    counters: animated,
                    core_strata: all('.stratum').length,
                    marker_beds: all('.stratum.marker').length,
                    specimens: all('.specimen').length,
                    samples: all('.sample').length,
                    density_cells: all('.density i').length,
                    load_bars_first4: all('.load span').slice(0,4).map(s => s.style.height),
                    panels: all('.panel').length,
                    panels_drawn: all('.panel.is-in').length,
                    tac: all('.tac').length,
                    log_drawn: !!document.querySelector('.panel.is-in .log-svg .ln'),
                    rail_fill: document.querySelector('#railBar i')?.style.height || '(无)',
                    depth_text: (document.querySelector('#railDepth') || {}).textContent || null,
                    empty_tall_blocks: empty,
                    theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
                    overflow_x: document.documentElement.scrollWidth > window.innerWidth + 1,
                    scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth,
                    body_color: getComputedStyle(document.body).color,
                    body_bg: getComputedStyle(document.body).backgroundColor
                  };
                })()""",
                "returnByValue": True,
            })
            if "value" not in probe.get("result", {}):
                print("PROBE 失败：", json.dumps(probe, ensure_ascii=False)[:900])
                report[name] = {"probe_error": probe}
            else:
                report[name] = probe["result"]["value"]

            shot = ws.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            path = os.path.join(OUT, f"art-{name}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            if isinstance(report[name], dict):
                report[name]["screenshot"] = path

            # 分屏截图：整页高图在聊天里会被压缩到看不清细节，
            # 所以按滚动位置抓若干张"视口"图，横向拼成一张审阅图。
            strips = []
            for k in range(3):
                frac = k / 2.0
                ws.call("Runtime.evaluate", {
                    "expression": f"""(async () => {{
                      const html = document.documentElement;
                      const prev = html.style.scrollBehavior;
                      html.style.scrollBehavior = 'auto';
                      const max = document.body.scrollHeight - window.innerHeight;
                      window.scrollTo(0, Math.round(max * {frac}));
                      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 600)));
                      html.style.scrollBehavior = prev;
                      return Math.round(window.scrollY);
                    }})()""",
                    "awaitPromise": True, "returnByValue": True,
                })
                time.sleep(0.7)
                s = ws.call("Page.captureScreenshot", {"format": "png"})
                strips.append(base64.b64decode(s["data"]))
                with open(os.path.join(OUT, f"art-{name}-s{k}.png"), "wb") as f:
                    f.write(strips[-1])
            report[name]["strips"] = [os.path.join(OUT, f"art-{name}-s{k}.png") for k in range(3)]
            try:
                from PIL import Image
                ims = [Image.open(os.path.join(OUT, f"art-{name}-s{k}.png")).convert("RGB") for k in range(3)]
                W = sum(i.width for i in ims) + 24
                H = max(i.height for i in ims)
                canvas = Image.new("RGB", (W, H), (10, 11, 12))
                x = 0
                for im in ims:
                    canvas.paste(im, (x, 0))
                    x += im.width + 12
                tiled = os.path.join(OUT, f"art-{name}-tiled.png")
                canvas.save(tiled)
                report[name]["tiled"] = tiled
            except Exception as exc:
                report[name]["tiled_error"] = str(exc)

        ws.close()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
