import assert from 'node:assert/strict'
import test from 'node:test'
import { normalizeIngestImportJob } from '../src/lib/ingestImportJob.ts'

test('privacy-scoped idle response supports Import page rendering', () => {
  const job = normalizeIngestImportJob({ running: false })
  assert.equal(job.failed.length, 0)
  assert.equal(job.total, 0)
  assert.equal(job.imported, 0)
  assert.equal(job.current, null)
  assert.equal(job.running, false)
  assert.equal(!job.running && job.failed.length > 0, false)
})

test('preserves real job progress and failures instead of hiding them', () => {
  const response = {
    running: true, total: 3, processed: 2, imported: 1,
    failed: [{ id: 8, title: 'Synthetic book', error: 'Import failed' }],
    current: 9, started_at: '2026-11-07T19:00:00', finished_at: null,
    cancelled: false,
  }
  assert.deepEqual(normalizeIngestImportJob(response), response)
  const idle = normalizeIngestImportJob({ running: false })
  assert.deepEqual(idle.failed, [])
})
