import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";

const EDGE =
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const PROFILE =
  "C:\\Users\\Administrator\\Documents\\Codex\\2026-08-08\\new-chat\\work\\edge-profile";

const child = spawn(
  EDGE,
  [
    "--headless",
    "--disable-gpu",
    "--remote-debugging-port=9222",
    `--user-data-dir=${PROFILE}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);

async function waitForTarget() {
  for (let i = 0; i < 40; i += 1) {
    try {
      const res = await fetch("http://127.0.0.1:9222/json/list");
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
const testUrl = process.env.TEST_URL || "http://localhost:5173/";
await send("Page.navigate", { url: testUrl });
await sleep(3500);

const cardCount = await evaluate(
  'document.querySelectorAll(".mistake-card").length',
);
console.log("cards:", cardCount);

await evaluate('document.querySelector(".mistake-card").click()');
await sleep(1500);

const dialogVisible = await evaluate(
  `(() => {
    const overlay = document.querySelector(".el-overlay:not([style*='display: none'])");
    return overlay ? overlay.innerText.includes("错题详情") : false;
  })()`,
);
const detailLoaded = await evaluate(
  '!!document.querySelector(".question-block")',
);
console.log("dialogVisible:", dialogVisible, "detailLoaded:", detailLoaded);

const deleteClicked = await evaluate(
  `(() => {
    const footer = document.querySelector(".el-dialog__footer");
    if (!footer) return false;
    const btn = [...footer.querySelectorAll("button")].find((b) =>
      b.textContent.includes("删除"),
    );
    if (!btn) return false;
    btn.click();
    return true;
  })()`,
);
console.log("deleteClicked:", deleteClicked);
await sleep(1200);

const messageBoxText = await evaluate(
  'document.querySelector(".el-message-box") ? document.querySelector(".el-message-box").innerText : ""',
);
console.log("messageBox:", messageBoxText);

const confirmClicked = await evaluate(
  `(() => {
    const box = document.querySelector(".el-message-box");
    if (!box) return false;
    const btn = [...box.querySelectorAll("button")].find((b) =>
      b.textContent.includes("删除"),
    );
    if (!btn) return false;
    btn.click();
    return true;
  })()`,
);
console.log("confirmClicked:", confirmClicked);
await sleep(2000);

const cardsAfter = await evaluate(
  'document.querySelectorAll(".mistake-card").length',
);
const countText = await evaluate(
  'document.querySelector(".count-tip") ? document.querySelector(".count-tip").innerText : ""',
);
console.log("cardsAfter:", cardsAfter, "countText:", countText);
console.log("runtimeErrors:", JSON.stringify(runtimeErrors));

child.kill();
process.exit(0);
