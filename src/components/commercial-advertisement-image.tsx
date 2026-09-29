import { useEffect, useState } from 'react'
import { Megaphone } from 'lucide-react'
import { fetchAuthenticatedMedia } from '@/api/client'

export function CommercialAdvertisementImage({ path, title }: { path: string; title: string }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let active = true
    let objectUrl = ''
    void fetchAuthenticatedMedia(path).then((blob) => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    }).catch(() => { if (active) setUrl('') })
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [path])
  return <div className="commercial-ad__visual">{url ? <img src={url} alt={title} loading="lazy" /> : <Megaphone aria-label={title} />}</div>
}
