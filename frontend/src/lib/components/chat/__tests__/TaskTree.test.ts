import { render } from '@testing-library/svelte';
import { expect, it } from 'vitest';
import TaskTree from '../TaskTree.svelte';

it('renders child tasks in durable call position order', () => {
	const { getByLabelText } = render(TaskTree, {
		tasks: [
			{ childRunId: 'second', agentId: 2, role: 'executor', position: 2, status: 'running' },
			{ childRunId: 'first', agentId: 1, role: 'researcher', position: 1, status: 'completed', summary: 'Found files' }
		]
	});
	expect(getByLabelText('하위 에이전트 작업').textContent).toMatch(/researcher.*executor/s);
});
