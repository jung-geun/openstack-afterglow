/**
 * Owns the browser's attachment to a durable chat run.
 *
 * Detaching aborts only the local SSE reader. The durable worker is independent
 * and continues until it reaches a terminal journal state or receives an
 * explicit cancel request elsewhere.
 */
export function createChatRunAttachment() {
	let generation = 0;
	const controllers = new Set<AbortController>();

	return {
		get generation() {
			return generation;
		},
		isCurrent(candidate: number): boolean {
			return candidate === generation;
		},
		attach(controller: AbortController, candidate: number): boolean {
			if (candidate !== generation) {
				controller.abort();
				return false;
			}
			controllers.add(controller);
			return true;
		},
		release(controller: AbortController) {
			controllers.delete(controller);
		},
		detach(): number {
			generation += 1;
			for (const controller of controllers) controller.abort();
			controllers.clear();
			return generation;
		}
	};
}
