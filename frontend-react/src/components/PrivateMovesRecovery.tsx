import { useEffect, useState } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from '@/lib/toast'
import { listPrivateMoves, recoverPrivateMove, type PrivateMove } from '@/lib/privateMoveActions'

/** Only the signed-in book owner can see these move records or retry recovery. */
export function PrivateMovesRecovery() {
  const [moves, setMoves] = useState<PrivateMove[]>([])
  const [recovering, setRecovering] = useState<number | null>(null)

  useEffect(() => {
    let alive = true
    void listPrivateMoves().then((rows) => {
      if (alive) setMoves(rows)
    }).catch(() => {
      // The library page stays usable if recovery history is unavailable.
    })
    return () => { alive = false }
  }, [])

  const outstanding = moves.filter((move) => move.state !== 'completed' && move.state !== 'rolled_back')
  if (outstanding.length === 0) return null

  async function recover(move: PrivateMove) {
    setRecovering(move.id)
    try {
      const updated = await recoverPrivateMove(move.id)
      setMoves((prev) => prev.map((row) => row.id === move.id ? updated : row))
      if (updated.state === 'completed') {
        toast.success('Private book move recovered')
      } else if (updated.state === 'rolled_back') {
        toast.info('Incomplete private copy removed; original shared book preserved')
      } else {
        toast.error('This move still needs manual review; no book was deleted')
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not recover the private book move')
    } finally {
      setRecovering(null)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2 text-xs">
      <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
      <span>{outstanding.length} interrupted private book move(s) on your account.</span>
      {outstanding.map((move) => (
        <Button
          key={move.id}
          size="sm"
          variant="outline"
          disabled={recovering !== null}
          onClick={() => { void recover(move) }}
        >
          <RotateCcw className="size-3.5" />
          {recovering === move.id ? 'Recovering…' : `Recover move #${move.id}`}
        </Button>
      ))}
    </div>
  )
}
