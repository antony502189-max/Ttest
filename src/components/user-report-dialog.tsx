import { useState } from 'react'
import { CircleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { createRemoteReport } from '@/api/reports'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import type { Listing } from '@/types'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

export function UserReportDialog({
  listing,
  open,
  onOpenChange,
}: {
  listing: Listing
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [reason, setReason] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    if (!reason || submitting) return
    setSubmitting(true)
    try {
      if (!mockMode) {
        await createRemoteReport(listing.id, reason, comment, 'user')
      }
      toast.success('Denuncia sobre el anunciante enviada')
      setReason('')
      setComment('')
      onOpenChange(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo enviar la denuncia')
    } finally {
      setSubmitting(false)
    }
  }

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Denunciar a {listing.owner.name}</DialogTitle>
        <DialogDescription>
          La denuncia se asociará al anunciante y usará «{listing.title}» como contexto. No compartiremos tu identidad con el anunciante.
        </DialogDescription>
      </DialogHeader>
      <fieldset className="report-options">
        <legend>Motivo</legend>
        {['Posible fraude', 'Spam o comportamiento abusivo', 'Identidad sospechosa', 'Contenido discriminatorio', 'Otro motivo'].map((item) => <label key={item}>
          <input type="radio" name="user-report" value={item} checked={reason === item} onChange={(event) => setReason(event.target.value)} />
          {item}
        </label>)}
      </fieldset>
      <label className="field-label">Comentario opcional<Textarea rows={3} maxLength={4000} value={comment} onChange={(event) => setComment(event.target.value)} /></label>
      <DialogFooter>
        <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancelar</Button>
        <Button disabled={!reason || submitting} onClick={() => { void submit() }}><CircleAlert /> {submitting ? 'Enviando…' : 'Enviar denuncia'}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
}
