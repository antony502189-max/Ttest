import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

// Narrow source-contract tests complement the browser regression in delta-matrix
// and backend full-stack upload tests. No production network or media writes.
test('photo selection waits for processing and falls back to authenticated uploads if local storage fails', () => {
  const forms = readFileSync('src/components/forms.tsx', 'utf8')
  const media = readFileSync('src/api/media.ts', 'utf8')
  const storage = readFileSync('src/lib/media-storage.ts', 'utf8')
  expect(forms).toContain('photoBatchesRef.current += 1')
  expect(forms).toContain('onProcessingChange?.(true)')
  expect(forms).toContain('uploadImageFile(accepted[index])')
  expect(forms).toContain('cleanupUploadedMediaReference(reference)')
  expect(forms).toContain('inputRef.current.value = ""')
  expect(forms).not.toContain('file.size <= 12_000_000')
  expect(storage).toContain('MAX_LISTING_SOURCE_IMAGE_BYTES = 50 * 1024 * 1024')
  expect(storage).toContain('MAX_LISTING_IMAGE_UPLOAD_BYTES = 8 * 1024 * 1024')
  expect(storage).toContain("!['image/webp', 'image/png', 'image/jpeg'].includes(optimized.type)")
  expect(media).toContain("return api<MediaAssetDto>('/uploads', { method: 'POST', body, timeoutMs: 90_000 })")
})

test('temporary owner-uploaded photos use bearer authorization and cannot leak to public image srcsets', () => {
  const image = readFileSync('src/components/media-image.tsx', 'utf8')
  const client = readFileSync('src/api/client.ts', 'utf8')
  expect(image).toContain("url.searchParams.get('uploadPreview') === '1'")
  expect(image).toContain('fetchAuthenticatedMedia(source)')
  expect(image).toContain('!isUploadPreviewReference(source) && (thumb !== source || card !== source)')
  expect(client).toContain('Authorization: `Bearer ${accessToken}`')
})

test('create/edit remove temporary uploaded photos but preserve original published assets', () => {
  const create = readFileSync('src/pages/ListingCreatePage.tsx', 'utf8')
  const edit = readFileSync('src/pages/ListingEditPage.tsx', 'utf8')
  expect(create).toContain("else if (image.includes('uploadPreview=1')) void cleanupUploadedMediaReference(image)")
  expect(edit).toContain("if (!existing.images.includes(image))")
  expect(edit).toContain("else if (image.includes('uploadPreview=1')) void cleanupUploadedMediaReference(image)")
})

test('video picker preserves server error details and the existing 100 MB/60s contract', () => {
  const forms = readFileSync('src/components/forms.tsx', 'utf8')
  const storage = readFileSync('src/lib/media-storage.ts', 'utf8')
  expect(forms).toContain('mediaUploadError(uploadError, "vídeo")')
  expect(forms).toContain('uploadVideoFile(file)')
  expect(storage).toContain('MAX_LISTING_VIDEO_SECONDS = 60')
  expect(storage).toContain('MAX_LISTING_VIDEO_BYTES = 100 * 1024 * 1024')
})
