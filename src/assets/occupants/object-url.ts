const cachedObjectUrls = new Map<string, string>()

export function occupantObjectUrl(dataUri: string): string {
  const cached = cachedObjectUrls.get(dataUri)
  if (cached) return cached

  const match = /^data:([^;]+);base64,(.+)$/.exec(dataUri)
  if (!match) return dataUri

  try {
    const binary = window.atob(match[2])
    const bytes = new Uint8Array(binary.length)
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
    const objectUrl = URL.createObjectURL(new Blob([bytes], { type: match[1] }))
    cachedObjectUrls.set(dataUri, objectUrl)
    return objectUrl
  } catch {
    return dataUri
  }
}
