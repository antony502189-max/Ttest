import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, GripVertical, ImagePlus, RotateCw, Trash2, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiBlob } from "@/api/client";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { acceptedImageTypes, getMediaBlob, isMediaReference, MediaStorageError, removeMediaReferences, saveMediaFile } from "@/lib/media-storage";
import { MediaImage } from "@/components/media-image";
import type { ListingStatus } from "@/types";
import "@/listing-edit-comfort.css";

export function FormField({
  label,
  htmlFor,
  description,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  description?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={htmlFor}>{label}</FieldLabel>
      {children}
      {description ? (
        <FieldDescription id={`${htmlFor}-description`}>
          {description}
        </FieldDescription>
      ) : null}
      {error ? (
        <FieldError id={`${htmlFor}-error`} role="alert">
          {error}
        </FieldError>
      ) : null}
    </Field>
  );
}

export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel = "Confirmar",
  destructive = false,
  onConfirm,
}: {
  trigger: ReactNode;
  title: string;
  description: string;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            data-variant={destructive ? "destructive" : undefined}
            onClick={onConfirm}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

const statusClass: Record<ListingStatus, string> = {
  Borrador: "status-draft",
  Pendiente: "status-pending",
  Publicado: "status-published",
  Oculto: "status-hidden",
  Finalizado: "status-ended",
  Rechazado: "status-rejected",
};
export function StatusBadge({ status }: { status: ListingStatus }) {
  return (
    <Badge
      variant="outline"
      className={cn("status-badge", statusClass[status])}
    >
      <span aria-hidden="true" />
      {status}
    </Badge>
  );
}

export function Stepper({
  steps,
  current,
  maxVisited = current,
  onStep,
}: {
  steps: string[];
  current: number;
  maxVisited?: number;
  onStep?: (step: number) => void;
}) {
  return (
    <div
      className="stepper"
      aria-label={`Paso ${current + 1} de ${steps.length}: ${steps[current]}`}
    >
      <div className="stepper__summary">
        <span>
          Paso {current + 1} de {steps.length}
        </span>
        <strong>{steps[current]}</strong>
      </div>
      <Progress
        value={((current + 1) / steps.length) * 100}
        aria-label={`Progreso de publicación: paso ${current + 1} de ${steps.length}`}
      />
      <ol>
        {steps.map((step, index) => (
          <li
            key={step}
            className={cn(
              index === current && "is-current",
              index < current && "is-complete",
            )}
            aria-current={index === current ? "step" : undefined}
          >
            <button
              type="button"
              disabled={!onStep || index > maxVisited}
              onClick={() => onStep?.(index)}
            >
              <span>{index + 1}</span>
              {step}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

async function imageBlob(reference: string) {
  if (isMediaReference(reference)) {
    const blob = await getMediaBlob(reference);
    if (!blob) throw new MediaStorageError("read", "No se pudo leer la imagen.");
    return blob;
  }

  const pathname = new URL(reference, window.location.origin).pathname;
  const apiMediaPath = pathname.match(/^\/api\/v1(\/media\/[0-9a-f-]{36})$/i)?.[1];
  const blob = apiMediaPath
    ? await apiBlob(apiMediaPath)
    : await fetch(reference, { credentials: "include" }).then((response) => {
        if (!response.ok) throw new MediaStorageError("read", "No se pudo leer la imagen.");
        return response.blob();
      });
  if (!blob.type.startsWith("image/")) throw new MediaStorageError("type", "El archivo no es una imagen válida.");
  return blob;
}

const normalizeQuarterTurns = (turns: number) => ((turns % 4) + 4) % 4;

async function rotateImageFile(reference: string, quarterTurns = 1) {
  const turns = normalizeQuarterTurns(quarterTurns);
  if (!turns) throw new MediaStorageError("read", "La imagen ya está en su orientación original.");
  const blob = await imageBlob(reference);
  const objectUrl = URL.createObjectURL(blob);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new MediaStorageError("read", "No se pudo abrir la imagen."));
      element.src = objectUrl;
    });
    if (!image.naturalWidth || !image.naturalHeight) {
      throw new MediaStorageError("read", "No se pudo abrir la imagen.");
    }

    const canvas = document.createElement("canvas");
    const swapsSides = turns % 2 === 1;
    canvas.width = swapsSides ? image.naturalHeight : image.naturalWidth;
    canvas.height = swapsSides ? image.naturalWidth : image.naturalHeight;
    const context = canvas.getContext("2d");
    if (!context) throw new MediaStorageError("unavailable", "No se pudo girar la imagen.");

    context.translate(canvas.width / 2, canvas.height / 2);
    context.rotate((Math.PI / 2) * turns);
    context.drawImage(image, -image.naturalWidth / 2, -image.naturalHeight / 2);

    const rotated = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (result) => result ? resolve(result) : reject(new MediaStorageError("read", "No se pudo guardar la imagen girada.")),
        "image/webp",
        0.92,
      );
    });
    const extension = rotated.type === "image/png" ? "png" : rotated.type === "image/jpeg" ? "jpg" : "webp";
    return new File([rotated], `listing-image-rotated.${extension}`, { type: rotated.type || "image/webp" });
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export function ImageUploader({
  images,
  onChange,
  onRemove,
  onProcessingChange,
  error,
}: {
  images: string[];
  onChange: (images: string[]) => void;
  onRemove?: (image: string) => void;
  onProcessingChange?: (processing: boolean) => void;
  error?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const imagesRef = useRef(images);
  imagesRef.current = images;
  const rotationQueueRef = useRef(new Map<string, number>());
  const rotationTimersRef = useRef(new Map<string, number>());
  const rotatingReferencesRef = useRef(new Set<string>());
  const busyReferencesRef = useRef(new Set<string>());
  const [previewTurns, setPreviewTurns] = useState<Record<string, number>>({});
  const [localError, setLocalError] = useState("");
  const photoDragRef = useRef<{
    reference: string;
    sourceIndex: number;
    pointerId: number;
    pointerType: string;
    startX: number;
    startY: number;
    offsetX: number;
    offsetY: number;
    targetIndex: number;
    active: boolean;
    card: HTMLDivElement;
    sourceRect: { left: number; top: number; right: number; bottom: number };
  } | null>(null);
  const photoDragTimerRef = useRef<number | null>(null);
  const touchMovePreventerRef = useRef<((event: TouchEvent) => void) | null>(null);
  const [photoDrag, setPhotoDrag] = useState<{
    sourceIndex: number;
    offsetX: number;
    offsetY: number;
    targetIndex: number;
  } | null>(null);

  useEffect(() => () => {
    rotationTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    rotationTimersRef.current.clear();
    if (photoDragTimerRef.current !== null) window.clearTimeout(photoDragTimerRef.current);
    if (touchMovePreventerRef.current) {
      document.removeEventListener("touchmove", touchMovePreventerRef.current, true);
      touchMovePreventerRef.current = null;
    }
  }, []);

  const reportBusy = (reference: string, busy: boolean) => {
    const wasBusy = busyReferencesRef.current.size > 0;
    if (busy) busyReferencesRef.current.add(reference);
    else busyReferencesRef.current.delete(reference);
    const isBusy = busyReferencesRef.current.size > 0;
    if (wasBusy !== isBusy) onProcessingChange?.(isBusy);
  };

  const setPreview = (reference: string, turns: number) => {
    const normalized = normalizeQuarterTurns(turns);
    setPreviewTurns((current) => {
      const next = { ...current };
      if (normalized) next[reference] = normalized;
      else delete next[reference];
      return next;
    });
  };

  const cancelPendingRotation = (reference: string) => {
    const timer = rotationTimersRef.current.get(reference);
    if (timer !== undefined) window.clearTimeout(timer);
    rotationTimersRef.current.delete(reference);
    rotationQueueRef.current.delete(reference);
    setPreview(reference, 0);
    if (!rotatingReferencesRef.current.has(reference)) reportBusy(reference, false);
  };

  function scheduleRotation(reference: string) {
    const currentTimer = rotationTimersRef.current.get(reference);
    if (currentTimer !== undefined) window.clearTimeout(currentTimer);
    const timer = window.setTimeout(() => {
      rotationTimersRef.current.delete(reference);
      void flushRotation(reference);
    }, 280);
    rotationTimersRef.current.set(reference, timer);
  }

  async function flushRotation(reference: string) {
    if (rotatingReferencesRef.current.has(reference)) return;
    const turns = normalizeQuarterTurns(rotationQueueRef.current.get(reference) ?? 0);
    if (!turns) {
      rotationQueueRef.current.delete(reference);
      setPreview(reference, 0);
      reportBusy(reference, false);
      return;
    }

    rotationQueueRef.current.set(reference, 0);
    rotatingReferencesRef.current.add(reference);
    try {
      const file = await rotateImageFile(reference, turns);
      const nextReference = await saveMediaFile(file);
      const current = imagesRef.current;
      const currentIndex = current.indexOf(reference);
      if (currentIndex < 0) {
        await removeMediaReferences([nextReference]).catch(() => undefined);
        rotationQueueRef.current.delete(reference);
        setPreview(reference, 0);
        reportBusy(reference, false);
        return;
      }

      const next = [...current];
      next[currentIndex] = nextReference;
      imagesRef.current = next;
      onChange(next);
      onRemove?.(reference);

      const remainingTurns = normalizeQuarterTurns(rotationQueueRef.current.get(reference) ?? 0);
      rotationQueueRef.current.delete(reference);
      busyReferencesRef.current.delete(reference);
      setPreviewTurns((currentPreview) => {
        const updated = { ...currentPreview };
        delete updated[reference];
        if (remainingTurns) updated[nextReference] = remainingTurns;
        return updated;
      });

      if (remainingTurns) {
        rotationQueueRef.current.set(nextReference, remainingTurns);
        busyReferencesRef.current.add(nextReference);
        scheduleRotation(nextReference);
      }
      onProcessingChange?.(busyReferencesRef.current.size > 0);
      setLocalError("");
    } catch (rotateError) {
      rotationQueueRef.current.delete(reference);
      setPreview(reference, 0);
      reportBusy(reference, false);
      setLocalError(rotateError instanceof MediaStorageError ? rotateError.message : "No se pudo girar la imagen.");
    } finally {
      rotatingReferencesRef.current.delete(reference);
    }
  }

  const readFiles = async (files: FileList | null) => {
    if (!files) return;
    const current = imagesRef.current;
    const accepted = [...files]
      .filter((file) => acceptedImageTypes.includes(file.type as (typeof acceptedImageTypes)[number]) && file.size <= 12_000_000)
      .slice(0, Math.max(0, 8 - current.length));
    setLocalError(
      accepted.length !== files.length
        ? "Algunas fotos se omitieron: usa JPEG, PNG o WebP de hasta 12 MB (máximo 8)."
        : "",
    );
    try {
      const saved = new Array<PromiseSettledResult<string>>(accepted.length);
      let cursor = 0;
      const worker = async () => {
        while (true) {
          const index = cursor++;
          if (index >= accepted.length) return;
          try {
            saved[index] = { status: "fulfilled", value: await saveMediaFile(accepted[index]) };
          } catch (reason) {
            saved[index] = { status: "rejected", reason };
          }
        }
      };
      await Promise.all(
        Array.from({ length: Math.min(2, accepted.length) }, () => worker()),
      );
      const references = saved.flatMap((result) => result.status === "fulfilled" ? [result.value] : []);
      const failed = saved.find((result) => result.status === "rejected");
      if (failed?.status === "rejected") {
        await removeMediaReferences(references).catch(() => undefined);
        throw failed.reason;
      }
      const next = [...imagesRef.current, ...references];
      imagesRef.current = next;
      onChange(next);
    } catch (uploadError) {
      setLocalError(uploadError instanceof MediaStorageError ? uploadError.message : "No se pudo leer o guardar una de las imágenes.");
    }
  };

  const rotate = (index: number) => {
    const reference = imagesRef.current[index];
    if (!reference) return;

    const queued = normalizeQuarterTurns((rotationQueueRef.current.get(reference) ?? 0) + 1);
    rotationQueueRef.current.set(reference, queued);
    setPreviewTurns((current) => {
      const next = { ...current };
      const visibleTurns = normalizeQuarterTurns((current[reference] ?? 0) + 1);
      if (visibleTurns) next[reference] = visibleTurns;
      else delete next[reference];
      return next;
    });
    reportBusy(reference, true);

    if (rotatingReferencesRef.current.has(reference)) return;
    if (!queued) {
      const timer = rotationTimersRef.current.get(reference);
      if (timer !== undefined) window.clearTimeout(timer);
      rotationTimersRef.current.delete(reference);
      rotationQueueRef.current.delete(reference);
      reportBusy(reference, false);
      return;
    }
    scheduleRotation(reference);
  };
  const move = (index: number, direction: -1 | 1) => {
    const current = imagesRef.current;
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const next = [...current];
    [next[index], next[target]] = [next[target], next[index]];
    imagesRef.current = next;
    onChange(next);
  };

  const movePhotoTo = (sourceIndex: number, targetIndex: number) => {
    const current = imagesRef.current;
    if (sourceIndex < 0 || sourceIndex >= current.length || targetIndex < 0 || targetIndex >= current.length || sourceIndex === targetIndex) return;
    const next = [...current];
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);
    imagesRef.current = next;
    onChange(next);
  };

  const removeTouchMovePreventer = () => {
    if (!touchMovePreventerRef.current) return;
    document.removeEventListener("touchmove", touchMovePreventerRef.current, true);
    touchMovePreventerRef.current = null;
  };

  const resetPhotoDrag = () => {
    if (photoDragTimerRef.current !== null) {
      window.clearTimeout(photoDragTimerRef.current);
      photoDragTimerRef.current = null;
    }
    const drag = photoDragRef.current;
    if (drag?.card.hasPointerCapture(drag.pointerId)) drag.card.releasePointerCapture(drag.pointerId);
    photoDragRef.current = null;
    removeTouchMovePreventer();
    setPhotoDrag(null);
  };

  const photoIndexAtPoint = (
    grid: HTMLElement,
    x: number,
    y: number,
    fallback: number,
    sourceIndex: number,
    sourceRect: { left: number; top: number; right: number; bottom: number },
  ) => {
    if (x >= sourceRect.left && x <= sourceRect.right && y >= sourceRect.top && y <= sourceRect.bottom) return fallback;
    const cards = [...grid.querySelectorAll<HTMLElement>("[data-photo-index]")];
    let nearestIndex = fallback;
    let nearestDistance = Number.POSITIVE_INFINITY;
    cards.forEach((card) => {
      const index = Number(card.dataset.photoIndex);
      if (index === sourceIndex) return;
      if (!Number.isInteger(index)) return;
      const rect = card.getBoundingClientRect();
      if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
        nearestIndex = index;
        nearestDistance = -1;
        return;
      }
      if (nearestDistance < 0) return;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const distance = Math.hypot(x - centerX, y - centerY);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = index;
      }
    });
    return nearestIndex;
  };

  const beginPhotoDrag = (event: React.PointerEvent<HTMLDivElement>, reference: string, index: number) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if ((event.target as HTMLElement).closest("button, a, input")) return;

    resetPhotoDrag();
    const card = event.currentTarget;
    const pointerId = event.pointerId;
    card.setPointerCapture(pointerId);
    const rect = card.getBoundingClientRect();
    photoDragRef.current = {
      reference,
      sourceIndex: index,
      pointerId,
      pointerType: event.pointerType,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: 0,
      offsetY: 0,
      targetIndex: index,
      active: false,
      card,
      sourceRect: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom },
    };

    const delay = event.pointerType === "mouse" ? 120 : 280;
    photoDragTimerRef.current = window.setTimeout(() => {
      const drag = photoDragRef.current;
      if (!drag || drag.pointerId !== pointerId || drag.sourceIndex !== index) return;
      drag.active = true;
      photoDragTimerRef.current = null;
      if (drag.pointerType !== "mouse") {
        const preventTouchMove = (touchEvent: TouchEvent) => touchEvent.preventDefault();
        touchMovePreventerRef.current = preventTouchMove;
        document.addEventListener("touchmove", preventTouchMove, { passive: false, capture: true });
      }
      setPhotoDrag({
        sourceIndex: drag.sourceIndex,
        offsetX: drag.offsetX,
        offsetY: drag.offsetY,
        targetIndex: drag.targetIndex,
      });
    }, delay);
  };

  const updatePhotoDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = photoDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    const offsetX = event.clientX - drag.startX;
    const offsetY = event.clientY - drag.startY;
    drag.offsetX = offsetX;
    drag.offsetY = offsetY;

    if (!drag.active) {
      if (drag.pointerType !== "mouse" && Math.hypot(offsetX, offsetY) > 9) resetPhotoDrag();
      return;
    }

    event.preventDefault();
    const grid = drag.card.parentElement;
    if (!grid) return;
    drag.targetIndex = photoIndexAtPoint(
      grid,
      event.clientX,
      event.clientY,
      drag.sourceIndex,
      drag.sourceIndex,
      drag.sourceRect,
    );
    setPhotoDrag({
      sourceIndex: drag.sourceIndex,
      offsetX,
      offsetY,
      targetIndex: drag.targetIndex,
    });
  };

  const finishPhotoDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = photoDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const shouldMove = drag.active;
    const sourceIndex = drag.sourceIndex;
    const targetIndex = drag.targetIndex;
    resetPhotoDrag();
    if (shouldMove) movePhotoTo(sourceIndex, targetIndex);
  };
  const makeCover = (index: number) => {
    const current = imagesRef.current;
    const next = [
      current[index],
      ...current.filter((_, imageIndex) => imageIndex !== index),
    ];
    imagesRef.current = next;
    onChange(next);
  };
  return (
    <div className="image-uploader">
      <button
        type="button"
        className="upload-dropzone"
        aria-describedby={error ? "publish-images-error" : undefined}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void readFiles(event.dataTransfer.files);
        }}
      >
        <UploadCloud />
        <strong>Añade fotos luminosas y horizontales</strong>
        <span>Arrastra o selecciona JPEG, PNG o WebP · máximo 8</span>
      </button>
      <input
        id="publish-images"
        ref={inputRef}
        className="sr-only"
        type="file"
        aria-label="Añadir fotos del anuncio"
        accept="image/jpeg,image/png,image/webp"
        multiple
        onChange={(event) => void readFiles(event.target.files)}
      />
      {error ? (
        <p id="publish-images-error" className="field-error" role="alert">
          {error}
        </p>
      ) : null}
      {localError ? (
        <p className="field-error" role="status">
          {localError}
        </p>
      ) : null}
      <p className="image-uploader__edit-help">Mantén pulsada una foto y arrástrala para cambiar el orden. La primera será la portada; el giro se procesa en segundo plano.</p>
      <div className="upload-grid">
        {images.map((image, index) => {
          const dragging = photoDrag?.sourceIndex === index;
          const dropTarget = Boolean(photoDrag && photoDrag.sourceIndex !== index && photoDrag.targetIndex === index);
          return (
          <div
            key={`${image}-${index}`}
            className={cn("upload-photo-card", dragging && "is-dragging", dropTarget && "is-drop-target")}
            data-photo-index={index}
            data-photo-reference={image}
            aria-grabbed={dragging ? true : undefined}
            style={dragging ? { transform: `translate3d(${photoDrag.offsetX}px, ${photoDrag.offsetY}px, 0) scale(1.025)` } : undefined}
            onPointerDown={(event) => beginPhotoDrag(event, image, index)}
            onPointerMove={updatePhotoDrag}
            onPointerUp={finishPhotoDrag}
            onPointerCancel={() => resetPhotoDrag()}
            onContextMenu={(event) => { if (photoDragRef.current?.active) event.preventDefault(); }}
          >
            <span className="upload-photo-drag-hint" aria-hidden="true"><GripVertical /></span>
            <MediaImage
              src={image}
              variant="thumb"
              alt={`Foto del anuncio ${index + 1}`}
              draggable={false}
              className={previewTurns[image] ? "photo-rotation-preview" : undefined}
              data-preview-rotation={previewTurns[image] ? String(previewTurns[image] * 90) : undefined}
              style={previewTurns[image] ? { transform: `rotate(${previewTurns[image] * 90}deg)` } : undefined}
            />
            {index === 0 ? (
              <span className="cover-label">Portada</span>
            ) : (
              <button
                type="button"
                className="make-cover"
                onClick={() => makeCover(index)}
              >
                Usar como portada
              </button>
            )}
            <button
              type="button"
              className="rotate-image"
              aria-label={`Girar foto ${index + 1} 90 grados`}
              title={`Girar foto ${index + 1} 90 grados`}
              aria-busy={busyReferencesRef.current.has(image) ? true : undefined}
              onClick={() => rotate(index)}
            >
              <RotateCw aria-hidden="true" />
              <span>Girar</span>
            </button>
            <span className="upload-reorder">
              <button
                type="button"
                disabled={index === 0}
                aria-label={`Subir foto ${index + 1} en el orden`}
                title={`Subir foto ${index + 1} en el orden`}
                onClick={() => move(index, -1)}
              >
                <ArrowUp aria-hidden="true" />
              </button>
              <button
                type="button"
                disabled={index === images.length - 1}
                aria-label={`Bajar foto ${index + 1} en el orden`}
                title={`Bajar foto ${index + 1} en el orden`}
                onClick={() => move(index, 1)}
              >
                <ArrowDown aria-hidden="true" />
              </button>
            </span>
            <button
              type="button"
              aria-label={`Eliminar foto ${index + 1}`}
              onClick={() => {
                cancelPendingRotation(image);
                const next = imagesRef.current.filter((_, itemIndex) => itemIndex !== index);
                imagesRef.current = next;
                onChange(next);
                onRemove?.(image);
              }}
            >
              <Trash2 />
            </button>
          </div>
          )
        })}
        {images.length < 8 ? (
          <Button
            variant="outline"
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            <ImagePlus data-icon="inline-start" />
            Añadir
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export function AdminTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="admin-table-wrap">
      <Table>
        <TableHeader>
          <TableRow>
            {headers.map((header) => (
              <TableHead key={header}>{header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={index}>
              {row.map((cell, cellIndex) => (
                <TableCell key={cellIndex}>{cell}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}