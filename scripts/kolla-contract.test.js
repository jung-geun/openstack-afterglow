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

test("Afterglow public endpoint controls every browser-facing origin", () => {
	const defaults = readRepoFile("deploy/kolla/ansible/roles/afterglow/defaults/main.yml")
	const precheck = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/precheck.yml")
	const config = readRepoFile("deploy/kolla/ansible/roles/afterglow/templates/afterglow.conf.j2")
	const sample = readRepoFile("deploy/kolla/globals.afterglow.sample.yml")

	assert.match(defaults, /^afterglow_public_endpoint_url: /m)
	assert.match(defaults, /ORIGIN: "\{\{ afterglow_public_endpoint_url \}\}"/)
	assert.match(defaults, /afterglow_instance_health_callback_base_url: "\{\{ afterglow_public_endpoint_url \}\}"/)
	assert.match(precheck, /afterglow_public_endpoint_url must be an absolute HTTP\(S\) origin/)
	assert.match(config, /frontend_base_url = "\{\{ afterglow_public_endpoint_url \}\}"/)
	assert.match(config, /origins = "\{\{ afterglow_public_endpoint_url \}\}"/)
	assert.match(config, /redirect_uri = "\{\{ afterglow_public_endpoint_url \}\}\/auth\/gitlab\/callback"/)
	assert.match(sample, /^afterglow_public_api_base: "https:\/\/cloud\.dmslab\.re\.kr"$/m)
	assert.match(sample, /^afterglow_public_endpoint_url: "https:\/\/cloud\.dmslab\.re\.kr"$/m)
	assert.doesNotMatch(defaults, /afterglow_external_url/)
})

test("Afterglow public hostname is routed by Kolla's external HAProxy frontend", () => {
	const defaults = readRepoFile("deploy/kolla/ansible/roles/afterglow/defaults/main.yml")
	const precheck = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/precheck.yml")
	const loadbalancer = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/loadbalancer.yml")
	const router = readRepoFile("deploy/kolla/ansible/roles/afterglow/templates/afterglow-public.cfg.j2")
	const sample = readRepoFile("deploy/kolla/globals.afterglow.sample.yml")

	assert.match(defaults, /^afterglow_public_haproxy_enabled: false$/m)
	assert.match(defaults, /^afterglow_public_haproxy_fqdn: ""$/m)
	assert.match(defaults, /afterglow_haproxy_services: "\{\{ afterglow_services \| combine\(afterglow_public_haproxy_services, recursive=True\) \}\}"/)
	assert.match(defaults, /afterglow-public:\n\s+group: afterglow/)
	assert.match(precheck, /Validate Kolla public route hostname/)
	assert.match(loadbalancer, /afterglow-public\.cfg/)
	assert.match(loadbalancer, /delegate_to: "\{\{ groups\['deployment'\]\[0\] \}\}"/)
	assert.match(loadbalancer, /mode: "0755"/)
	assert.match(loadbalancer, /mode: "0644"/)
	assert.match(loadbalancer, /external-frontend-map/)
	assert.match(loadbalancer, /project_services: "\{\{ afterglow_haproxy_services \}\}"/)
	assert.match(router, /backend afterglow-public_back/)
	assert.match(router, /frontend afterglow-public-router_front/)
	assert.match(router, /use_backend afterglow-api_back if \{ path_beg \/api\/ \}/)
	assert.match(router, /default_backend afterglow-frontend_back/)
	assert.match(sample, /^afterglow_public_haproxy_enabled: true$/m)
	assert.match(sample, /^afterglow_public_haproxy_fqdn: "cloud\.dmslab\.re\.kr"$/m)
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

test("Drover, Waygate, and Lumen public hostnames are routed by Kolla's external HAProxy frontend without disturbing internal endpoints", () => {
	for (const [service, port] of [
		["drover", "8011"],
		["waygate", "8010"],
		["lumen", "8012"],
	]) {
		const defaults = readRepoFile(`deploy/kolla/ansible/roles/${service}/defaults/main.yml`)
		const precheck = readRepoFile(`deploy/kolla/ansible/roles/${service}/tasks/precheck.yml`)
		const loadbalancer = readRepoFile(`deploy/kolla/ansible/roles/${service}/tasks/loadbalancer.yml`)

		assert.match(defaults, new RegExp(`^${service}_public_haproxy_enabled: false$`, "m"))
		assert.match(defaults, new RegExp(`^${service}_public_haproxy_fqdn: ""$`, "m"))
		assert.match(
			defaults,
			new RegExp(`${service}_haproxy_services: "\\{\\{ ${service}_services \\| combine\\(${service}_public_haproxy_services, recursive=True\\) \\}\\}"`)
		)
		assert.match(defaults, new RegExp(`${service}-public:\\n\\s+group: ${service}`))
		assert.match(defaults, new RegExp(`external_fqdn: "\\{\\{ ${service}_public_haproxy_fqdn \\}\\}"`))
		assert.match(defaults, new RegExp(`port: "\\{\\{ ${service}_api_port \\}\\}"`))
		// The internal <service>-api entry must remain non-external so
		// internal/admin Keystone endpoints keep the internal VIP listener.
		assert.match(defaults, new RegExp(`${service}-api:\\n\\s+enabled: "\\{\\{ enable_${service}_api \\| bool \\}\\}"\\n\\s+external: false`))

		assert.match(precheck, new RegExp(`Validate ${service[0].toUpperCase()}${service.slice(1)} public route hostname`))
		assert.match(loadbalancer, new RegExp(`${service}-public\\.cfg`))
		assert.match(loadbalancer, /external-frontend-map/)
		assert.match(loadbalancer, new RegExp(`project_services: "\\{\\{ ${service}_haproxy_services \\}\\}"`))
	}
})
