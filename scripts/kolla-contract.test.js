const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const os = require("node:os")
const { spawnSync } = require("node:child_process")
const test = require("node:test")

const rootDir = path.resolve(__dirname, "..")

function readRepoFile(relativePath) {
	return fs.readFileSync(path.join(rootDir, relativePath), "utf8")
}

function runGlobalsNormalizer(normalizer, ...args) {
	const kollaPython = process.env.KOLLA_PYTHON
	if (kollaPython) {
		return spawnSync(kollaPython, [normalizer, ...args], { encoding: "utf8" })
	}
	return spawnSync(
		"uv",
		["run", "--project", path.join(rootDir, "backend"), "python", normalizer, ...args],
		{ encoding: "utf8" }
	)
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
	assert.match(defaults, /^lumen_external_postgres_url: ""$/m)
	assert.doesNotMatch(defaults, /lumen_external_postgres_host/)
	assert.doesNotMatch(defaults, /lumen_external_postgres_password/)
	assert.doesNotMatch(defaults, /enable_lumen_postgres/)
	assert.doesNotMatch(defaults, /lumen_memory_pgvector_(db|user|host|port)/)
	assert.match(defaults, /^lumen_memory_pgvector_url: ""$/m)
	assert.match(precheck, /lumen_postgres_mode in \['bundled', 'external'\]/)
	assert.match(precheck, /lumen_external_postgres_url must be a postgresql:\/\/ or postgres:\/\/ URL/)
	assert.match(precheck, /lumen_memory_pgvector_url must be a postgresql:\/\/ or postgres:\/\/ URL/)
	assert.match(lifecycle, /when: lumen_postgres_mode == 'bundled'/)
	assert.match(lifecycle, /lumen_postgres_mode == 'external'/)
	assert.match(lifecycle, /name: lumen_external_postgres_probe/)
	assert.match(lifecycle, /render_postgres_service\.py/)
	assert.match(lifecycle, /PGSERVICEFILE: \/tmp\/lumen-external-postgres\.conf/)
	assert.match(lifecycle, /PGSERVICE: external/)
	assert.doesNotMatch(lifecycle, /PG_URL:/)
	assert.doesNotMatch(lifecycle, /- "\{\{ lumen_external_postgres_url \}\}"/)
	assert.doesNotMatch(lifecycle, /lumen_memory_pgvector_host/)
})

test("Lumen external PostgreSQL renderer emits libpq service syntax", () => {
	const renderer = path.join(
		rootDir,
		"deploy/kolla/ansible/roles/lumen/files/render_postgres_service.py"
	)
	const result = spawnSync("python3", [renderer], {
		env: {
			...process.env,
			LUMEN_EXTERNAL_POSTGRES_URL:
				"postgresql://lumen%40user:pa%23ss@db.example:5433/lumen%2Fmemory?sslmode=require&application_name=afterglow"
		},
		encoding: "utf8"
	})

	assert.equal(result.status, 0, result.stderr)
	assert.deepEqual(JSON.parse(result.stdout), {
		service:
			"[external]\n" +
			"host=db.example\n" +
			"port=5433\n" +
			"user=lumen@user\n" +
			"password=pa#ss\n" +
			"dbname=lumen/memory\n" +
			"sslmode=require\n" +
			"application_name=afterglow\n"
	})
})

test("Kolla installer safely patches the standard playbook import", () => {
	const patcher = path.join(rootDir, "deploy/kolla/patch_stock_site.py")
	const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "afterglow-kolla-site-"))
	const sitePath = path.join(temporaryDirectory, "site.yml")
	const original = "---\n- import_playbook: gather-facts.yml\n"

	try {
		fs.writeFileSync(sitePath, original)
		for (const action of ["install", "install", "remove"]) {
			const result = spawnSync("python3", [patcher, action, sitePath], { encoding: "utf8" })
			assert.equal(result.status, 0, result.stderr)
		}
		assert.equal(fs.readFileSync(sitePath, "utf8"), original)
		const globalsPath = path.join(temporaryDirectory, "globals.yml")
		const pluginGlobalsPath = path.join(temporaryDirectory, "afterglow-globals.yml")
		const backupPath = path.join(temporaryDirectory, "globals.yml.before-afterglow-dedup")
		const stockGlobals = "kolla_base: true\n"
		const pluginGlobals = "enable_afterglow: true\n"
		fs.writeFileSync(globalsPath, `${stockGlobals}\n---\n${pluginGlobals}`)
		fs.writeFileSync(pluginGlobalsPath, pluginGlobals)
		const normalizer = path.join(rootDir, "deploy/kolla/normalize_stock_globals.py")
		const normalization = runGlobalsNormalizer(normalizer, globalsPath, pluginGlobalsPath, backupPath)
		assert.equal(normalization.status, 0, normalization.stderr)
		assert.equal(fs.readFileSync(globalsPath, "utf8"), stockGlobals)
		assert.equal(fs.readFileSync(backupPath, "utf8"), `${stockGlobals}\n---\n${pluginGlobals}`)
		const uninstall = readRepoFile("deploy/kolla/uninstall.sh")
		const installer = readRepoFile("deploy/kolla/install.sh")
		assert.match(installer, /for inventory_vars_dir in group_vars host_vars/)
		assert.match(uninstall, /default group_vars/)
		assert.match(uninstall, /default host_vars/)
		assert.match(uninstall, /MULTINODE_INVENTORY="\$KOLLA_CONFIG_DIR\/multinode"/)
		assert.ok(
			uninstall.indexOf("patch_stock_site.py\" remove") <
				uninstall.indexOf('afterglow-site.yml" "aggregate afterglow-site.yml playbook"')
		)
		assert.match(readRepoFile("deploy/kolla/install.sh"), /globals\.d/)
		assert.match(readRepoFile("deploy/kolla/install.sh"), /patch_stock_site\.py" install/)
		assert.match(uninstall, /patch_stock_site\.py" remove/)
	} finally {
		fs.rmSync(temporaryDirectory, { recursive: true, force: true })
	}
})

test("Kolla helper refusals preserve stock files", () => {
	const patcher = path.join(rootDir, "deploy/kolla/patch_stock_site.py")
	const normalizer = path.join(rootDir, "deploy/kolla/normalize_stock_globals.py")
	const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "afterglow-kolla-refusal-"))
	const sitePath = path.join(temporaryDirectory, "site.yml")
	const globalsPath = path.join(temporaryDirectory, "globals.yml")
	const pluginGlobalsPath = path.join(temporaryDirectory, "afterglow-globals.yml")
	const backupPath = path.join(temporaryDirectory, "globals.yml.before-afterglow-dedup")
	const malformedSite = "# END openstack-afterglow plugin\n# BEGIN openstack-afterglow plugin\n"
	const mismatchedGlobals = "kolla_base: true\n\n---\nenable_afterglow: false\n"

	try {
		fs.writeFileSync(sitePath, malformedSite)
		const patchResult = spawnSync("python3", [patcher, "remove", sitePath], { encoding: "utf8" })
		assert.equal(patchResult.status, 1, patchResult.stderr)
		assert.match(patchResult.stderr, /managed marker is malformed/)
		assert.equal(fs.readFileSync(sitePath, "utf8"), malformedSite)

		fs.writeFileSync(globalsPath, mismatchedGlobals)
		fs.writeFileSync(pluginGlobalsPath, "enable_afterglow: true\n")
		const normalizeResult = runGlobalsNormalizer(
			normalizer,
			globalsPath,
			pluginGlobalsPath,
			backupPath
		)
		assert.equal(normalizeResult.status, 1, normalizeResult.stderr)
		assert.match(normalizeResult.stderr, /trailing document does not exactly match plugin globals/)
		assert.equal(fs.readFileSync(globalsPath, "utf8"), mismatchedGlobals)
		assert.equal(fs.existsSync(backupPath), false)
	} finally {
		fs.rmSync(temporaryDirectory, { recursive: true, force: true })
	}
})

test("Plugin lifecycle dispatchers preserve stock actions and tag isolation", () => {
	for (const service of ["afterglow", "waygate", "drover", "lumen"]) {
		const dispatcher = readRepoFile(`deploy/kolla/ansible/roles/${service}/tasks/main.yml`)
		assert.doesNotMatch(dispatcher, /tags: always/)
		assert.match(dispatcher, /'config_validate', 'stop', 'deploy-containers', 'check'/)
		assert.match(dispatcher, /when: kolla_action \| default\('deploy'\) in \[.*'config'\]/)
	}
	const pluginSite = readRepoFile("deploy/kolla/site.yml")
	const afterglowPull = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/pull.yml")

	assert.match(pluginSite, /kolla_action \| default\('deploy'\) in \['deploy', 'reconfigure', 'upgrade', 'config'\]/)
	assert.match(pluginSite, /kolla_action \| default\('deploy'\) in \['deploy', 'reconfigure', 'upgrade'\]/)
	assert.match(afterglowPull, /not \(afterglow_source_mode \| default\(false\) \| bool\)/)
})

test("Plugin services derive data-plane and OpenStack topology from Kolla variables", () => {
	const afterglowDefaults = readRepoFile("deploy/kolla/ansible/roles/afterglow/defaults/main.yml")
	const afterglowConfig = readRepoFile("deploy/kolla/ansible/roles/afterglow/templates/afterglow.kolla.conf.j2")
	const afterglowDatabase = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/preconditions_db.yml")

	assert.match(afterglowDefaults, /afterglow_database_address: "\{\{ database_address \}\}"/)
	assert.match(afterglowDefaults, /afterglow_database_admin_user: "\{\{ database_user \}\}"/)
	assert.match(afterglowDefaults, /afterglow_valkey_password: "\{\{ valkey_master_password \| default\(''\) \}\}"/)
	assert.match(afterglowDefaults, /afterglow_keystone_auth_url: "\{\{ keystone_internal_url \}\}"/)
	assert.match(afterglowDefaults, /afterglow_keystone_project_domain_name: "\{\{ default_project_domain_name \}\}"/)
	assert.match(afterglowDefaults, /afterglow_keystone_user_domain_name: "\{\{ default_user_domain_name \}\}"/)
	assert.match(afterglowDefaults, /afterglow_keystone_region_name: "\{\{ openstack_region_name \}\}"/)
	assert.match(afterglowConfig, /auth_url = "\{\{ afterglow_keystone_auth_url \}\}"/)
	assert.match(afterglowConfig, /project_domain_name = "\{\{ afterglow_keystone_project_domain_name \}\}"/)
	assert.match(afterglowDatabase, /login_host: "\{\{ afterglow_database_address \}\}"/)

	for (const service of ["drover", "waygate", "lumen"]) {
		const defaults = readRepoFile(`deploy/kolla/ansible/roles/${service}/defaults/main.yml`)
		const template = readRepoFile(`deploy/kolla/ansible/roles/${service}/templates/${service}.conf.j2`)
		const database = readRepoFile(`deploy/kolla/ansible/roles/${service}/tasks/preconditions_db.yml`)

		assert.match(defaults, new RegExp(`${service}_database_address: "\\{\\{ database_address \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_database_port: "\\{\\{ database_port \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_database_admin_user: "\\{\\{ database_user \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_valkey_host: "\\{\\{ 'api' \\| kolla_address\\(groups\\['valkey'\\]\\[0\\]\\) \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_valkey_port: "\\{\\{ redis_port \\| default\\(6379\\) \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_valkey_password: "\\{\\{ valkey_master_password`))
		assert.match(defaults, new RegExp(`${service}_keystone_auth_url: "\\{\\{ keystone_internal_url \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_keystone_project_domain_name: "\\{\\{ default_project_domain_name \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_keystone_user_domain_name: "\\{\\{ default_user_domain_name \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_keystone_region_name: "\\{\\{ openstack_region_name \\}\\}"`))
		assert.match(defaults, new RegExp(`${service}_keystone_interface: "internal"`))
		assert.match(template, new RegExp(`${service === "lumen" ? "keystone_auth_url" : "auth_url"} = "\\{\\{ ${service}_keystone_auth_url \\}\\}"`))
		assert.match(template, new RegExp(`${service === "lumen" ? "database_url" : "url"} = "\\{\\{ ${service}_database_url \\}\\}"`))
		assert.match(database, new RegExp(`login_host: "\\{\\{ ${service}_database_address \\}\\}"`))
	}
})

test("Drover, Waygate, and Lumen public hostnames are routed by Kolla's external HAProxy frontend without disturbing internal endpoints", () => {
	const sample = readRepoFile("deploy/kolla/globals.afterglow.sample.yml")
	for (const service of ["drover", "waygate", "lumen"]) {
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
		assert.ok(
			precheck.includes(
				`- (${service}_public_endpoint_url | regex_replace('/$', '')) == ('https://' ~ ${service}_public_haproxy_fqdn)`
			)
		)
		assert.match(loadbalancer, new RegExp(`${service}-public\\.cfg`))
		assert.match(loadbalancer, /external-frontend-map/)
		assert.match(loadbalancer, new RegExp(`project_services: "\\{\\{ ${service}_haproxy_services \\}\\}"`))
	}

	for (const service of ["drover", "waygate", "lumen"]) {
		assert.match(sample, new RegExp(`^${service}_public_haproxy_enabled: true$`, "m"))
		assert.match(sample, new RegExp(`^${service}_public_haproxy_fqdn: "${service}\\.dmslab\\.re\\.kr"$`, "m"))
	}
})


test("Afterglow hands operator TOML to containers without surrendering Kolla-owned settings", () => {
	const defaults = readRepoFile("deploy/kolla/ansible/roles/afterglow/defaults/main.yml")
	const configTask = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/config.yml")
	const bootstrap = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/bootstrap_service.yml")
	const start = readRepoFile("deploy/kolla/ansible/roles/afterglow/tasks/start.yml")
	const finalConfig = readRepoFile("deploy/kolla/ansible/roles/afterglow/templates/afterglow.kolla.conf.j2")
	const sample = readRepoFile("deploy/kolla/globals.afterglow.sample.yml")
	const sanitizer = readRepoFile("deploy/kolla/ansible/roles/afterglow/files/sanitize_operator_config.py")
	const readme = readRepoFile("deploy/kolla/README.md")

	assert.match(defaults, /^afterglow_operator_config_source: ""$/m)
	assert.match(defaults, /^afterglow_operator_config_name: "afterglow\.operator\.conf"$/m)
	assert.match(defaults, /^afterglow_kolla_config_name: "afterglow\.zz-kolla\.conf"$/m)
	assert.match(defaults, /^afterglow_operator_config_staging_path: "\/tmp\/\{\{ afterglow_operator_config_name \}\}\.sanitized"$/m)
	assert.equal((defaults.match(/:\/app\/\{\{ afterglow_operator_config_name \}\}:ro/g) || []).length, 3)
	assert.equal((defaults.match(/:\/app\/\{\{ afterglow_kolla_config_name \}\}:ro/g) || []).length, 3)
	assert.match(configTask, /Config \| Stage and validate sanitized operator configuration/)
	assert.match(configTask, /sanitize_operator_config\.py/)
	assert.match(configTask, /Config \| Clear stale sanitized operator configuration staging file/)
	assert.match(configTask, /afterglow_operator_config_staging_path/)
	assert.match(configTask, /Config \| Remove sanitized operator configuration staging file/)
	assert.match(configTask, /Config \| Copy operator configuration override/)
	assert.match(configTask, /- "\{\{ ansible_playbook_python \}\}"/)
	assert.match(configTask, /src: afterglow\.kolla\.conf\.j2/)
	assert.match(sanitizer, /tomllib\.loads\(sanitized\)/)
	assert.match(sanitizer, /builder\.ssh_private_key must not be staged/)
	assert.match(bootstrap, /afterglow_operator_config_name/)
	assert.match(bootstrap, /afterglow_kolla_config_name/)
	assert.match(start, /Stat Afterglow configuration layers/)
	assert.match(start, /afterglow_config_stats\.results \| map\(attribute='stat\.checksum'\) \| join\(':'\)/)
	assert.equal((start.match(/config_hash:/g) || []).length, 1)
	assert.match(readme, /\/etc\/kolla\/config\/afterglow\/afterglow\.conf/)
	assert.match(readme, /raw file is never mounted into a container/)
	assert.match(readme, /install -m 0600 -o .* \.\/afterglow\.conf \/etc\/kolla\/config\/afterglow\/afterglow\.conf/)
	assert.match(finalConfig, /^\[openstack\]$/m)
	assert.match(finalConfig, /^\[union\]$/m)
	assert.match(finalConfig, /metadata_store_share_id/)
	assert.match(finalConfig, /^\[cors\]$/m)
	assert.doesNotMatch(finalConfig, /^\[gitlab_oidc\]$/m)
	assert.match(sample, /^afterglow_operator_config_source: "\/etc\/kolla\/config\/afterglow\/afterglow\.conf"$/m)
})