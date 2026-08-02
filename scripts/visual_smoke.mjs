#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const artifacts = join(root, ".artifacts");
const profile = await mkdtemp(join(tmpdir(), "shlb-chrome-"));
const port = 9300 + (process.pid % 500);
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const password = (
  await readFile(join(root, ".secrets", "bootstrap_password"), "utf8")
).trim();

await mkdir(artifacts, { recursive: true });

const chrome = spawn(
  chromePath,
  [
    "--headless",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-sync",
    "--hide-scrollbars",
    "--ignore-certificate-errors",
    "--no-sandbox",
    "--no-first-run",
    "--remote-allow-origins=*",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "--window-size=1440,1000",
    "https://localhost:8443/login",
  ],
  { stdio: "ignore" },
);

const delay = (milliseconds) => new Promise((resolveDelay) => {
  setTimeout(resolveDelay, milliseconds);
});

async function pollJson(url, attempts = 50) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
    } catch {
      // Chrome is still starting.
    }
    await delay(100);
  }
  throw new Error(`Chrome debugging endpoint did not become ready: ${url}`);
}

let socket;
let nextId = 0;
const pending = new Map();

function send(method, params = {}) {
  const id = ++nextId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveCommand, rejectCommand) => {
    pending.set(id, { resolve: resolveCommand, reject: rejectCommand });
  });
}

async function evaluate(expression) {
  const response = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.text || "Browser expression failed");
  }
  return response.result?.value;
}

async function waitFor(expression, label, attempts = 80) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await evaluate(expression)) return;
    await delay(100);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

async function screenshot(name) {
  const result = await send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  const target = join(artifacts, name);
  await writeFile(target, Buffer.from(result.data, "base64"));
  return target;
}

try {
  await pollJson(`http://127.0.0.1:${port}/json/version`);
  const tabs = await pollJson(`http://127.0.0.1:${port}/json/list`);
  const page = tabs.find((tab) => tab.type === "page");
  if (!page?.webSocketDebuggerUrl) throw new Error("No debuggable page was found");

  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolveSocket, rejectSocket) => {
    socket.addEventListener("open", resolveSocket, { once: true });
    socket.addEventListener("error", rejectSocket, { once: true });
  });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const command = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) command.reject(new Error(message.error.message));
    else command.resolve(message.result);
  });

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-color-scheme", value: "light" }],
  });
  await waitFor(
    "document.readyState === 'complete' && document.querySelector('#email') !== null",
    "hydrated login form",
  );

  const loginAudit = await evaluate(`({
    title: document.querySelector('h2')?.textContent?.trim(),
    context: document.querySelector('.auth-context h1')?.textContent?.trim(),
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
    activeElement: document.activeElement?.tagName,
  })`);
  if (loginAudit.title !== "Sign in") throw new Error("Login title is missing");
  if (loginAudit.horizontalOverflow) throw new Error("Login page has horizontal overflow");
  const loginScreenshot = await screenshot("phase2-login.png");

  await evaluate(`(() => {
    const assign = (selector, value) => {
      const input = document.querySelector(selector);
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      ).set;
      setter.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    };
    assign("#email", "admin@shlb.local");
    assign("#password", ${JSON.stringify(password)});
    document.querySelector("form").requestSubmit();
    return true;
  })()`);
  await waitFor(
    "(location.pathname === '/app' || location.pathname === '/app/') && document.body.textContent.includes('PHASE 2 LIVE')",
    "authenticated Phase 2 shell",
    120,
  );
  await waitFor(
    "document.body.textContent.includes('Registry connected.')",
    "live registry boundary label",
  );

  const desktopAudit = await evaluate(`({
    path: location.pathname,
    pageTitle: document.querySelector('main h1')?.textContent?.trim(),
    rail: document.querySelector('.app-rail') !== null,
    liveLabel: document.body.textContent.includes('PHASE 2 LIVE'),
    registryBoundary: document.querySelector('.fixture-strip')?.textContent?.trim(),
    streamLabel: document.querySelector('.freshness-indicator')?.textContent?.trim(),
    userEnabled: !document.querySelector('.user-button')?.disabled,
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
  })`);
  if (!/^\/app\/?$/.test(desktopAudit.path)) throw new Error("Login did not route to /app");
  if (!desktopAudit.rail || !desktopAudit.liveLabel || !desktopAudit.userEnabled) {
    throw new Error("Authenticated shell state is incomplete");
  }
  if (!desktopAudit.registryBoundary?.includes("traffic evidence")) {
    throw new Error("Live registry/fixture evidence boundary is not visible");
  }
  if (desktopAudit.horizontalOverflow) {
    throw new Error("Desktop shell has horizontal overflow");
  }
  const desktopScreenshot = await screenshot("phase2-command-center.png");

  await send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await delay(250);
  const mobileAudit = await evaluate(`({
    safetyText: document.querySelector('.mobile-safety-strip')?.textContent?.trim(),
    menuVisible: getComputedStyle(document.querySelector('.mobile-menu')).display !== 'none',
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
  })`);
  if (!mobileAudit.safetyText?.includes("Read and acknowledge")) {
    throw new Error("Mobile safety boundary is missing");
  }
  if (!mobileAudit.menuVisible || mobileAudit.horizontalOverflow) {
    throw new Error("Mobile shell layout contract failed");
  }
  const mobileScreenshot = await screenshot("phase2-command-center-mobile.png");

  console.log(JSON.stringify({
    login: loginAudit,
    desktop: desktopAudit,
    mobile: mobileAudit,
    screenshots: [loginScreenshot, desktopScreenshot, mobileScreenshot],
  }, null, 2));
} finally {
  if (socket?.readyState === WebSocket.OPEN) socket.close();
  chrome.kill("SIGTERM");
  await rm(profile, { recursive: true, force: true });
}
