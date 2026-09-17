import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const exportRoot = resolve("out");
assert.equal(existsSync(exportRoot), true, "run `npm run build` before checking exported links");

function walk(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    return statSync(path).isDirectory() ? walk(path) : path.endsWith(".html") ? [path] : [];
  });
}

const intentionalDataPlaneRoutes = new Set(["/public", "/auth", "/catalog", "/checkout"]);
const unresolved = new Set();

for (const file of walk(exportRoot)) {
  const html = readFileSync(file, "utf8");
  for (const match of html.matchAll(/href="(\/[^"]*)"/g)) {
    const rawHref = match[1];
    const pathname = rawHref.split(/[?#]/)[0];
    if (pathname.startsWith("/_next") || intentionalDataPlaneRoutes.has(pathname)) continue;
    const relative = pathname === "/"
      ? "index.html"
      : `${pathname.replace(/^\//, "").replace(/\/$/, "")}/index.html`;
    if (!existsSync(join(exportRoot, relative))) unresolved.add(`${file} -> ${rawHref}`);
  }
}

assert.deepEqual([...unresolved], [], `unresolved internal links:\n${[...unresolved].join("\n")}`);
console.log("Verified exported internal links and intentional HAProxy application routes.");
