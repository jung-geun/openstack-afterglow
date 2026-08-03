import { describe, expect, it } from 'vitest';

import { completeChatAttachment, toInputParts } from '../chatAttachments';

describe('toInputParts', () => {
	it('submits only completed opaque asset identifiers', () => {
		expect(
			toInputParts([
				{ assetId: 'asset-clean', mime: 'image/png', name: 'clean.png', status: 'done' },
				{ assetId: 'asset-uploading', mime: 'image/png', name: 'pending.png', status: 'uploading' },
				{ mime: 'image/png', name: 'missing.png', status: 'done' }
			])
		).toEqual([{ type: 'image', asset_id: 'asset-clean' }]);
	});
});

it('marks a scanned image upload ready for the next run', () => {
	expect(
		completeChatAttachment(
			{ mime: 'image/png', name: 'pending.png', status: 'uploading', previewUrl: 'blob:preview' },
			{ id: 'asset-clean', mime_type: 'image/png', name: 'clean.png' }
		)
	).toEqual({
		assetId: 'asset-clean',
		mime: 'image/png',
		name: 'clean.png',
		previewUrl: 'blob:preview',
		status: 'done'
	});
});

it('maps a completed PDF to a document input', () => {
	expect(
		toInputParts([
			{ assetId: 'asset-document', mime: 'application/pdf', name: 'report.pdf', status: 'done' }
		])
	).toEqual([{ type: 'document', asset_id: 'asset-document' }]);
});
