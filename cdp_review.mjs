import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";

const EDGE =
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const PROFILE =
  "C:\\Users\\Administrator\\Documents\\Codex\\2026-08-08\\new-chat\\work\\edge-profile-review";

const child = spawn(
  EDGE,
  [
    "--headless",
    "--disable-gpu",
    "--remote-debugging-port=9223",
    `--user-data-dir=${PROFILE}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);

async function waitForTarget() {
  for (let i = 0; i < 40; i += 1) {
    try {
      const res = await fetch("http://127.0.0.1:9223/json/list");
      const targets = await res.json();
      const page = targets.find((item) => item.type === "page");
      if (page) return page;
    } catch (err) {
      // Edge 尚未就绪
    }
    await sleep(300);
  }
  throw new Error("Edge debug target not available");
}

const page = await waitForTarget();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.onopen = resolve;
  ws.onerror = () => reject(new Error("websocket error"));
});

let msgId = 0;
const pending = new Map();
const runtimeErrors = [];

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(JSON.stringify(msg.error)));
    else resolve(msg.result);
  } else if (msg.method === "Runtime.exceptionThrown") {
    runtimeErrors.push(
      msg.params.exceptionDetails.text +
        " " +
        (msg.params.exceptionDetails.exception?.description || ""),
    );
  } else if (msg.method === "Runtime.consoleAPICalled") {
    const text = (msg.params.args || [])
      .map((arg) => arg.value ?? arg.description ?? "")
      .join(" ");
    if (msg.params.type === "error") runtimeErrors.push(text);
  }
};

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const res = await send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  return res.result?.value;
}

await send("Page.enable");
await send("Runtime.enable");
await send("Page.navigate", { url: "http://localhost:5173/review" });
await sleep(3500);

const hasCard = await evaluate('!!document.querySelector(".review-card")');
console.log("reviewCard:", hasCard);

const clickedOption = await evaluate(
  `(() => {
    const opt = document.querySelector(".review-option");
    if (!opt) return false;
    opt.click();
    return true;
  })()`,
);
console.log("clickedOption:", clickedOption);

const confirmText = await evaluate(
  `(() => {
    const btn = [...document.querySelectorAll(".review-footer button")].find((b) =>
      b.textContent.includes("确认答案"),
    );
    if (!btn) return "";
    btn.click();
    return btn.textContent.trim();
  })()`,
);
console.log("confirm:", confirmText);
await sleep(1000);

const analysisShown = await evaluate(
  '!!document.querySelector(".analysis-block")',
);
console.log("analysisShown:", analysisShown);

const nextText = await evaluate(
  `(() => {
    const btn = [...document.querySelectorAll(".review-footer button")].find((b) =>
      b.textContent.includes("下一题"),
    );
    if (!btn) return "";
    btn.click();
    return btn.textContent.trim();
  })()`,
);
console.log("next:", nextText);
await sleep(1500);

const stillCard = await evaluate(
  '!!document.querySelector(".review-card")',
);
const progressText = await evaluate(
  'document.querySelector(".count-tip") ? document.querySelector(".count-tip").innerText : ""',
);
console.log("afterNext:", stillCard, progressText);

await send("Page.navigate", { url: "http://localhost:5173/capture" });
await sleep(2500);
const captureOk = await evaluate(
  'document.body.innerText.includes("智能录入") && document.body.innerText.includes("AI 解析")',
);
console.log("capturePage:", captureOk);
console.log("runtimeErrors:", JSON.stringify(runtimeErrors));

child.kill();
process.exit(0);
