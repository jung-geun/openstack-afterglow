const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const test = require("node:test")

const rootDir = path.resolve(__dirname, "..")
const claudeWorkflow = fs.readFileSync(path.join(rootDir, ".github", "workflows", "claude.yml"), "utf8")

test("Claude workflow accepts explicit conversation mentions without automated review triggers", () => {
	assert.match(claudeWorkflow, /^  issue_comment:\s*$/m)
	assert.match(claudeWorkflow, /^  issues:\s*$/m)
	assert.match(claudeWorkflow, /github\.event_name == 'issue_comment'.*'@claude'/)
	assert.match(claudeWorkflow, /github\.event_name == 'issues'.*'@claude'/)

	assert.doesNotMatch(claudeWorkflow, /^  pull_request_review:\s*$/m)
	assert.doesNotMatch(claudeWorkflow, /^  pull_request_review_comment:\s*$/m)
	assert.doesNotMatch(claudeWorkflow, /github\.event_name == 'pull_request_review(?:_comment)?'/)
})
