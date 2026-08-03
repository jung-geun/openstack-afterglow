import { REDUCED_MOTION_QUERY } from '$lib/design/tokens';

/** Returns false during SSR and in runtimes without media-query support. */
export function prefersReducedMotion(): boolean {
	return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
		? window.matchMedia(REDUCED_MOTION_QUERY).matches
		: false;
}

/** Returns an immediate Svelte/Web Animation duration when reduced motion is requested. */
export function motionDuration(durationMs: number): number {
	return prefersReducedMotion() ? 0 : durationMs;
}
