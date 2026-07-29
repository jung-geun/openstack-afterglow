#!/usr/bin/env node
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const rootDir = path.resolve(__dirname, "..");
const testTargetPath = path.join(__dirname, "test-target.js");
const localDatabaseUrl = "mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test";

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

function main(argv) {
	const noStart = argv.includes("--no-start");
	const targetArgs = argv.filter((arg) => arg !== "--no-start");
	const databaseUrl = process.env.AFTERGLOW_TEST_DATABASE_URL || localDatabaseUrl;

	if (!noStart && !process.env.AFTERGLOW_TEST_DATABASE_URL) {
		console.log("Starting local MariaDB test profile...");
		const composeExitCode = run("docker", ["compose", "--profile", "test", "up", "-d", "--wait", "mariadb"]);
		if (composeExitCode !== 0) return composeExitCode;
	}

	console.log(`Running DB tests against ${databaseUrl.replace(/:[^:@/]+@/, ":***@")}`);
	return run(process.execPath, [testTargetPath, "db", ...targetArgs], {
		env: {
			...process.env,
			AFTERGLOW_TEST_DATABASE_URL: databaseUrl
		}
	});
}

if (require.main === module) {
	process.exit(main(process.argv.slice(2)));
}

module.exports = { localDatabaseUrl, main, run };
