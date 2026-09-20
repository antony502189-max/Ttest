import { useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ImagePlus, RotateCw, Trash2, UploadCloud } from "lucide-react";
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

async function rotateImageFile(reference: string) {
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
    canvas.width = image.naturalHeight;
    canvas.height = image.naturalWidth;
    const context = canvas.getContext("2d");
    if (!context) throw new MediaStorageError("unavailable", "No se pudo girar la imagen.");

    context.translate(canvas.width / 2, canvas.height / 2);
    context.rotate(Math.PI / 2);
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
  error,
}: {
  images: string[];
  onChange: (images: string[]) => void;
  onRemove?: (image: string) => void;
  error?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const imagesRef = useRef(images);
  imagesRef.current = images;
  const [rotatingIndex, setRotatingIndex] = useState<number | null>(null);
  const [localError, setLocalError] = useState("");
  const readFiles = async (files: FileList | null) => {
    if (!files) return;
    const accepted = [...files]
      .filter((file) => acceptedImageTypes.includes(file.type as (typeof acceptedImageTypes)[number]) && file.size <= 12_000_000)
      .slice(0, Math.max(0, 8 - images.length));
    setLocalError(
      accepted.length !== files.length
        ? "Algunas fotos se omitieron: usa JPEG, PNG o WebP de hasta 12 MB (máximo 8)."
        : "",
    );
    try {
      const saved = await Promise.allSettled(accepted.map(saveMediaFile));
      const references = saved.flatMap((result) => result.status === "fulfilled" ? [result.value] : []);
      const failed = saved.find((result) => result.status === "rejected");
      if (failed?.status === "rejected") {
        await removeMediaReferences(references).catch(() => undefined);
        throw failed.reason;
      }
      onChange([...images, ...references]);
    } catch (uploadError) {
      setLocalError(uploadError instanceof MediaStorageError ? uploadError.message : "No se pudo leer o guardar una de las imágenes.");
    }
  };
  const rotate = async (index: number) => {
    if (rotatingIndex !== null) return;
    const previous = images[index];
    if (!previous) return;

    setRotatingIndex(index);
    try {
      const file = await rotateImageFile(previous);
      const reference = await saveMediaFile(file);
      const current = imagesRef.current;
      const currentIndex = current[index] === previous ? index : current.indexOf(previous);
      if (currentIndex < 0) {
        await removeMediaReferences([reference]).catch(() => undefined);
        return;
      }
      const next = [...current];
      next[currentIndex] = reference;
      onChange(next);
      onRemove?.(previous);
      setLocalError("");
    } catch (rotateError) {
      setLocalError(rotateError instanceof MediaStorageError ? rotateError.message : "No se pudo girar la imagen.");
    } finally {
      setRotatingIndex(null);
    }
  };
  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= images.length) return;
    const next = [...images];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };
  const makeCover = (index: number) =>
    onChange([
      images[index],
      ...images.filter((_, imageIndex) => imageIndex !== index),
    ]);
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
      <p className="image-uploader__edit-help">Puedes girar una foto, cambiar la portada y reordenar las imágenes sin volver a subir las demás.</p>
      <div className="upload-grid">
        {images.map((image, index) => (
          <div key={`${image}-${index}`}>
            <MediaImage src={image} alt={`Foto del anuncio ${index + 1}`} />
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
              disabled={rotatingIndex !== null}
              aria-busy={rotatingIndex === index ? true : undefined}
              onClick={() => void rotate(index)}
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
                onChange(images.filter((_, itemIndex) => itemIndex !== index));
                onRemove?.(image);
              }}
            >
              <Trash2 />
            </button>
          </div>
        ))}
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