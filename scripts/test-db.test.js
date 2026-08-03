const assert = require("node:assert/strict");
const test = require("node:test");

const { localDatabaseUrl } = require("./test-db");

test("local DB tests use a database separate from the development schema", () => {
	assert.match(localDatabaseUrl, /\/afterglow_pytest$/);
	assert.doesNotMatch(localDatabaseUrl, /\/afterglow_test$/);
});
