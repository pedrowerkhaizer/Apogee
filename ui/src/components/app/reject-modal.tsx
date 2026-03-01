'use client'

import { useState, useTransition } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'

interface RejectModalProps {
  open: boolean
  onClose: () => void
  onConfirm: (reason: string) => void
  title?: string
}

export function RejectModal({ open, onClose, onConfirm, title }: RejectModalProps) {
  const [reason, setReason] = useState('')
  const [pending, startTransition] = useTransition()

  function handleConfirm() {
    startTransition(() => {
      onConfirm(reason)
      setReason('')
      onClose()
    })
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-bg-elevated border-border-default max-w-md">
        <DialogHeader>
          <DialogTitle className="text-content-primary">Rejeitar tópico</DialogTitle>
          {title && <p className="text-sm text-content-secondary mt-1">"{title}"</p>}
        </DialogHeader>
        <div className="space-y-2">
          <Label className="text-content-secondary">Motivo (opcional)</Label>
          <Textarea
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Ex: muito similar a um vídeo recente..."
            className="bg-bg-base border-border-default text-content-primary resize-none"
            rows={3}
          />
        </div>
        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={pending}
          >
            {pending ? 'Rejeitando...' : 'Confirmar rejeição'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
