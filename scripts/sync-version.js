#!/usr/bin/env node
// 루트 package.json version → frontend/package.json, backend/pyproject.toml, backend/uv.lock
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const rootPkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf-8"));
const version = rootPkg.version;

if (!/^\d+\.\d+\.\d+/.test(version)) {
	console.error(`invalid version in root package.json: ${version}`);
	process.exit(1);
}

// 1) frontend/package.json
const fePath = path.join(root, "frontend/package.json");
const fe = JSON.parse(fs.readFileSync(fePath, "utf-8"));
fe.version = version;
fs.writeFileSync(fePath, JSON.stringify(fe, null, "\t") + "\n");

// 2) backend/pyproject.toml — 최상위 [project] 블록의 version 한 줄만 치환
const pyPath = path.join(root, "backend/pyproject.toml");
const py = fs.readFileSync(pyPath, "utf-8");
if (!/^version\s*=\s*"[^"]*"/m.test(py)) {
	console.error("backend/pyproject.toml: version line not found");
	process.exit(1);
}
const patched = py.replace(/^(version\s*=\s*)"[^"]*"/m, `$1"${version}"`);
fs.writeFileSync(pyPath, patched);

// 3) backend/uv.lock 갱신 — pyproject version 필드가 바뀌었으므로 재생성 필요
try {
	execSync("uv lock --quiet", { cwd: path.join(root, "backend"), stdio: "inherit" });
} catch {
	console.error("uv lock 실패 — uv 가 설치되어 있어야 합니다");
	process.exit(1);
}

console.log(`✓ version synced to ${version}`);
