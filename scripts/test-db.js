#!/usr/bin/env node
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const rootDir = path.resolve(__dirname, "..");
const testTargetPath = path.join(__dirname, "test-target.js");
const localDatabaseUrl = "mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_pytest";
const localCheckpointerUrl = "postgresql://afterglow:dev@127.0.0.1:5433/afterglow_checkpoints";

function run(command, args, options = {}) {
	const result = spawnSync(command, args, {
		cwd: rootDir,
		stdio: "inherit",
		...options
	});
	if (result.error) {
		console.error(result.error.message);
		return 1;
	}
	return result.status === null ? 1 : result.status;
}

function ensureLocalTestDatabase() {
	return run("docker", [
		"compose",
		"exec",
		"-T",
		"mariadb",
		"mariadb",
		"-uroot",
		"-pdev",
		"-e",
		"CREATE DATABASE IF NOT EXISTS afterglow_pytest; GRANT ALL PRIVILEGES ON afterglow_pytest.* TO 'afterglow'@'%'; FLUSH PRIVILEGES;"
	]);
}

function main(argv) {
	const noStart = argv.includes("--no-start");
	const targetArgs = argv.filter((arg) => arg !== "--no-start");
	const autoStartLocalServices = !noStart && !process.env.AFTERGLOW_TEST_DATABASE_URL;
	const databaseUrl = process.env.AFTERGLOW_TEST_DATABASE_URL || localDatabaseUrl;
	const checkpointerUrl =
		process.env.AFTERGLOW_TEST_CHECKPOINTER_POSTGRES_URL ||
		(autoStartLocalServices ? localCheckpointerUrl : "");

	if (autoStartLocalServices) {
		console.log("Starting local MariaDB and PostgreSQL test profiles...");
		const composeExitCode = run("docker", [
			"compose",
			"--profile",
			"test",
			"up",
			"-d",
			"--wait",
			"mariadb",
			"postgres"
		]);
		if (composeExitCode !== 0) return composeExitCode;
	}
	if (!process.env.AFTERGLOW_TEST_DATABASE_URL) {
		const databaseExitCode = ensureLocalTestDatabase();
		if (databaseExitCode !== 0) return databaseExitCode;
	}
	console.log(`Running DB tests against ${databaseUrl.replace(/:[^:@/]+@/, ":***@")}`);
	return run(process.execPath, [testTargetPath, "db", ...targetArgs], {
		env: {
			...process.env,
			AFTERGLOW_TEST_DATABASE_URL: databaseUrl,
			AFTERGLOW_TEST_CHECKPOINTER_POSTGRES_URL: checkpointerUrl
		}
	});
}

if (require.main === module) {
	process.exit(main(process.argv.slice(2)));
}

module.exports = { localDatabaseUrl, localCheckpointerUrl, main, run };
