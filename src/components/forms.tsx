import { useRef, useState, type ReactNode } from 'react'
import { GripVertical, ImagePlus, Trash2, UploadCloud } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { ListingStatus } from '@/types'

export function FormField({ label, htmlFor, description, error, children }: { label: string; htmlFor: string; description?: string; error?: string; children: ReactNode }) {
  return <Field data-invalid={error ? true : undefined}><FieldLabel htmlFor={htmlFor}>{label}</FieldLabel>{children}{description ? <FieldDescription>{description}</FieldDescription> : null}{error ? <FieldError role="alert">{error}</FieldError> : null}</Field>
}

export function ConfirmDialog({ trigger, title, description, confirmLabel = 'Confirmar', destructive = false, onConfirm }: { trigger: ReactNode; title: string; description: string; confirmLabel?: string; destructive?: boolean; onConfirm: () => void }) {
  return <AlertDialog><AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{title}</AlertDialogTitle><AlertDialogDescription>{description}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancelar</AlertDialogCancel><AlertDialogAction data-variant={destructive ? 'destructive' : undefined} onClick={onConfirm}>{confirmLabel}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
}

const statusClass: Record<ListingStatus, string> = { Borrador: 'status-draft', Pendiente: 'status-pending', Publicado: 'status-published', Oculto: 'status-hidden', Finalizado: 'status-ended', Rechazado: 'status-rejected' }
export function StatusBadge({ status }: { status: ListingStatus }) { return <Badge variant="outline" className={cn('status-badge', statusClass[status])}><span aria-hidden="true" />{status}</Badge> }

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return <div className="stepper" aria-label={`Paso ${current + 1} de ${steps.length}: ${steps[current]}`}><div className="stepper__summary"><span>Paso {current + 1} de {steps.length}</span><strong>{steps[current]}</strong></div><Progress value={((current + 1) / steps.length) * 100} aria-label={`Progreso de publicación: paso ${current + 1} de ${steps.length}`} /><ol>{steps.map((step, index) => <li key={step} className={cn(index === current && 'is-current', index < current && 'is-complete')} aria-current={index === current ? 'step' : undefined}><span>{index + 1}</span>{step}</li>)}</ol></div>
}

const demoImages = [
  'https://images.unsplash.com/photo-1522771753035-1a1a4e54f87f?auto=format&fit=crop&w=700&q=80',
  'https://images.unsplash.com/photo-1560185008-b033106af5c3?auto=format&fit=crop&w=700&q=80',
  'https://images.unsplash.com/photo-1560448075-bb485b067938?auto=format&fit=crop&w=700&q=80',
]

export function ImageUploader() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [images, setImages] = useState(demoImages)
  return <div className="image-uploader"><button type="button" className="upload-dropzone" onClick={() => inputRef.current?.click()}><UploadCloud /><strong>Añade fotos luminosas y horizontales</strong><span>JPG o PNG · hasta 10 MB por foto</span></button><input ref={inputRef} className="sr-only" type="file" accept="image/*" multiple onChange={() => setImages((current) => [...current, demoImages[current.length % demoImages.length]])} /><div className="upload-grid">{images.map((image, index) => <div key={`${image}-${index}`}><img src={image} alt={`Foto del anuncio ${index + 1}`} />{index === 0 ? <span className="cover-label">Portada</span> : null}<button type="button" aria-label={`Mover foto ${index + 1}`}><GripVertical /></button><button type="button" aria-label={`Eliminar foto ${index + 1}`} onClick={() => setImages((current) => current.filter((_, itemIndex) => itemIndex !== index))}><Trash2 /></button></div>)}<Button variant="outline" type="button" onClick={() => inputRef.current?.click()}><ImagePlus data-icon="inline-start" />Añadir</Button></div></div>
}

export function AdminTable({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return <div className="admin-table-wrap"><Table><TableHeader><TableRow>{headers.map((header) => <TableHead key={header}>{header}</TableHead>)}</TableRow></TableHeader><TableBody>{rows.map((row, index) => <TableRow key={index}>{row.map((cell, cellIndex) => <TableCell key={cellIndex}>{cell}</TableCell>)}</TableRow>)}</TableBody></Table></div>
}
