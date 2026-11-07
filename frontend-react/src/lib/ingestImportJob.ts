export interface IngestImportJob {
  running: boolean
  total: number
  processed: number
  imported: number
  failed: Array<{ id: number; title: string; error: string }>
  current: number | null
  started_at: string | null
  finished_at: string | null
  cancelled: boolean
}

// The multi-user API intentionally returns only { running: false } when
// there is no job owned by this reader. Keep that privacy boundary while
// giving the view a consistent idle shape (including failed.length).
export function normalizeIngestImportJob(job: Partial<IngestImportJob>): IngestImportJob {
  return {
    running: false,
    total: 0,
    processed: 0,
    imported: 0,
    current: null,
    started_at: null,
    finished_at: null,
    cancelled: false,
    ...job,
    failed: Array.isArray(job.failed) ? job.failed : [],
  }
}
