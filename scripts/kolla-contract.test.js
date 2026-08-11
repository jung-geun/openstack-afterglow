const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const test = require("node:test")

const rootDir = path.resolve(__dirname, "..")

function readRepoFile(relativePath) {
	return fs.readFileSync(path.join(rootDir, relativePath), "utf8")
}

test("Afterglow health checks use probe tools present in published images", () => {
	const defaults = readRepoFile("deploy/kolla/ansible/roles/afterglow/defaults/main.yml")

	assert.match(
		defaults,
		/healthcheck:\n\s+test: \["CMD", "python", "-c", "from urllib\.request import urlopen;/
	)
	assert.match(
		defaults,
		/healthcheck:\n\s+test: \["CMD", "wget", "-q", "-O", "\/dev\/null", "http:\/\//
	)
	assert.doesNotMatch(defaults, /test: \["CMD", "curl", "-f", "http:\/\{\{ afterglow_/)
})

test("Lumen PostgreSQL modes keep bundled resources separate from external connection inputs", () => {
	const defaults = readRepoFile("deploy/kolla/ansible/roles/lumen/defaults/main.yml")
	const precheck = readRepoFile("deploy/kolla/ansible/roles/lumen/tasks/precheck.yml")
	const lifecycle = readRepoFile("deploy/kolla/ansible/roles/lumen/tasks/preconditions_postgres.yml")

	assert.match(defaults, /^lumen_postgres_mode: "external"$/m)
	assert.match(defaults, /^lumen_external_postgres_host: ""$/m)
	assert.match(defaults, /^lumen_external_postgres_password: ""$/m)
	assert.doesNotMatch(defaults, /enable_lumen_postgres/)
	assert.match(precheck, /lumen_postgres_mode in \['bundled', 'external'\]/)
	assert.match(precheck, /lumen_external_postgres host, port, database, user, and password must be set/)
	assert.match(lifecycle, /when: lumen_postgres_mode == 'bundled'/)
	assert.match(lifecycle, /lumen_postgres_mode == 'external'/)
	assert.match(lifecycle, /name: lumen_external_postgres_probe/)
	assert.match(lifecycle, /PGPASSWORD: "{{ lumen_external_postgres_password }}"/)
	assert.match(lifecycle, /- "SELECT 1;"/)
})
