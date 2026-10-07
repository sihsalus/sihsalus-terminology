/* eslint-env node, es2020 */
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { signedExportDownload } from './signedExportDownload.js';

test('signed storage download omits API credentials and preserves the file', async t => {
  const url = 'https://storage.example.org/export.zip?signature=synthetic';
  const file = new Blob(['synthetic export'], { type: 'application/zip' });
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response(file, {
    headers: { 'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="export.zip"' },
  }));
  const result = await signedExportDownload({
    status: 200,
    data: { url },
    headers: { Authorization: 'Token synthetic-api-token', 'X-OCL-CLIENT': 'synthetic-client' },
  });
  assert.deepEqual(fetch.mock.calls[0].arguments, [url, { credentials: 'omit' }]);
  assert.equal(result.status, 200);
  assert.equal(await result.data.text(), 'synthetic export');
  assert.equal(result.headers['content-type'], 'application/zip');
  assert.equal(result.headers['content-disposition'], 'attachment; filename="export.zip"');
});

for(const status of [204, 208, 403]) {
  test(`API status ${status} does not attempt a storage download`, async t => {
    const fetch = t.mock.method(globalThis, 'fetch', async () => { throw new Error('Unexpected download'); });
    const response = { status };
    assert.equal(await signedExportDownload(response), response);
    assert.equal(fetch.mock.callCount(), 0);
  });
}

test('a missing signed URL does not attempt a storage download', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => { throw new Error('Unexpected download'); });
  await assert.rejects(signedExportDownload({ status: 200, data: {} }), /Missing export download URL/);
  assert.equal(fetch.mock.callCount(), 0);
});

test('storage errors reject before treating an error body as a file', async t => {
  const blob = t.mock.fn(() => { throw new Error('An error is not a download'); });
  t.mock.method(globalThis, 'fetch', async () => ({ ok: false, status: 403, blob }));
  await assert.rejects(signedExportDownload({ status: 200, data: { url: 'https://storage.example.org/export.zip' } }), /Export download failed \(403\)/);
  assert.equal(blob.mock.callCount(), 0);
});

test('network errors reject without reporting a successful download', async t => {
  t.mock.method(globalThis, 'fetch', async () => { throw new Error('Network failure'); });
  await assert.rejects(signedExportDownload({ status: 200, data: { url: 'https://storage.example.org/export.zip' } }), /Network failure/);
});
