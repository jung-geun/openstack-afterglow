#!/usr/bin/env node
// Tag-driven version sync — CI 전용 (git add/commit 없음).
//
// 사용:
//   node scripts/apply-tag-version.js          # GITHUB_REF 환경변수에서 읽음
//   node scripts/apply-tag-version.js v1.14.0  # 직접 지정
//
// 동작:
//   1) tag 에서 semver 추출
//   2) root package.json version 갱신
//   3) scripts/sync-version.js 위임 → frontend/backend/uv.lock 전파

"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const ref = process.env.GITHUB_REF || "";
let version;
if (ref.startsWith("refs/tags/v")) {
	version = ref.slice("refs/tags/v".length);
} else if (process.argv[2]) {
	version = process.argv[2].replace(/^v/, "");
} else {
	console.error("apply-tag-version: GITHUB_REF=refs/tags/vX.Y.Z 또는 argv[2] 필요");
	process.exit(1);
}

if (!/^\d+\.\d+\.\d+/.test(version)) {
	console.error(`apply-tag-version: 잘못된 버전 형식: ${version}`);
	process.exit(1);
}

const root = path.resolve(__dirname, "..");
const rootPkgPath = path.join(root, "package.json");
const rootPkg = JSON.parse(fs.readFileSync(rootPkgPath, "utf-8"));

if (rootPkg.version === version) {
	console.log(`root package.json already at ${version} — no change needed`);
} else {
	console.log(`root package.json: ${rootPkg.version} → ${version}`);
	rootPkg.version = version;
	fs.writeFileSync(rootPkgPath, JSON.stringify(rootPkg, null, 2) + "\n");
}

const result = spawnSync("node", [path.join(__dirname, "sync-version.js")], {
	cwd: root,
	stdio: "inherit",
	env: process.env,
});

if (result.status !== 0) {
	process.exit(result.status ?? 1);
}
