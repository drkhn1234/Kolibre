import { authHeaders } from './auth'
import { withBackendUrl } from './api'

export interface PrivateMove {
  id: number
  source_library: string
  source_book_id: number
  target_library: string
  target_book_id: number | null
  state: 'copying' | 'ready' | 'source_deleted' | 'needs_review' | 'rolled_back' | 'completed'
  failure_code: string | null
}

async function requestPrivateMove(path: string, method: 'GET' | 'POST') {
  const response = await fetch(withBackendUrl(path), {
    method,
    headers: await authHeaders(),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(detail?.detail ?? `Move request failed (HTTP ${response.status})`)
  }
  return response.json() as Promise<unknown>
}

export async function listPrivateMoves(): Promise<PrivateMove[]> {
  return await requestPrivateMove('/api/kolibre/library-transfer/private-moves', 'GET') as PrivateMove[]
}

export async function recoverPrivateMove(moveId: number): Promise<PrivateMove> {
  return await requestPrivateMove(
    `/api/kolibre/library-transfer/private-moves/${encodeURIComponent(moveId)}/recover`,
    'POST',
  ) as PrivateMove
}
